"""AetherTune Manual TTS JSONL service。

此 service 是 UI/Rust 與 CosyVoice2/Breeze runner 之間的窄 bridge：

* stdin 每行一個 command，stdout 只送 ``speech_ack`` 與 ``speech_snapshot``。
* generation 與 playback 分離；runner 目前只支援 non-streaming WAV。
* queue、profile、route、transcript 都在服務端 snapshot，前端不能繞過邊界。
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
import threading
import time
import uuid
from collections import OrderedDict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

# 兼容直接以 ``python services/tts/service.py`` 執行；Rust 會用
# ``python -m services.tts.service``，兩者都要導向同一個 package。
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from services.engines.postfx import validate_postfx
from services.tts.postfx import render_postfx
from services.tts.snapshot import project_profile, project_queue
from services.tts.validation import ALLOWED_ENGINES, ALLOWED_SOURCES, INTERRUPT_POLICIES, validate_request

if __package__ in (None, ""):
    from services.tts.adapters import (
        BaseGenerationAdapter,
        GenerationCancelled,
        GenerationError,
        GenerationResult,
        default_adapters,
    )
    from services.tts.playback import PlaybackCancelled, PlaybackError, PlaybackResult, MonitoredPlayback, list_audio_devices, resolve_route
    from services.tts.storage import TranscriptStore, utc_now
else:
    from .adapters import (
        BaseGenerationAdapter,
        GenerationCancelled,
        GenerationError,
        GenerationResult,
        default_adapters,
    )
    from .playback import PlaybackCancelled, PlaybackError, PlaybackResult, MonitoredPlayback, list_audio_devices, resolve_route
    from .storage import TranscriptStore, utc_now


def _error(code: str, message: str, **extra: Any) -> dict[str, Any]:
    result = {"code": code, "message": message}
    result.update(extra)
    return result


def _now_epoch_ms() -> int:
    return int(time.time() * 1000)


def _parse_iso_ms(value: str) -> float:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1000
    except (TypeError, ValueError):
        return float(_now_epoch_ms())


def _short_exception(exc: BaseException) -> tuple[str, str]:
    text = str(exc)
    if ":" in text:
        code, message = text.split(":", 1)
        if code.isupper() and len(code) <= 48:
            return code, message.strip()
    if isinstance(exc, PlaybackError):
        return "ROUTE_FAILED", text
    if isinstance(exc, GenerationError):
        return "BACKEND_CRASH", text
    return "BACKEND_CRASH", text or exc.__class__.__name__


def _load_profiles(root: Path) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    directory = root / "contracts" / "voices"
    profiles: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}
    if not directory.is_dir():
        return profiles, by_id
    for path in sorted(directory.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        profile_id = data.get("id")
        name = data.get("name")
        engines = data.get("engines")
        if not isinstance(profile_id, str) or not isinstance(name, str) or not isinstance(engines, list):
            continue
        if profile_id in by_id:
            continue
        snapshot = copy.deepcopy(data)
        snapshot["profile_path"] = str(path)
        # profile metadata 是 reference transcript 的人工審核 gate；不把 draft
        # 文字誤報為 verified，只將狀態原樣呈現給 UI。
        profiles.append(snapshot)
        by_id[profile_id] = snapshot
    return profiles, by_id


class SpeechService:
    """單一 worker 維持嚴格 FIFO，且 command ack 不等待生成。"""

    def __init__(
        self,
        root: Path,
        *,
        adapters: Mapping[str, Any] | None = None,
        playback: Any | None = None,
        emit: Callable[[dict[str, Any]], None] | None = None,
        session_id: str | None = None,
    ) -> None:
        self.root = root.resolve()
        self.session_id = session_id or str(uuid.uuid4())
        self._emit = emit
        self._lock = threading.RLock()
        self._condition = threading.Condition(self._lock)
        self._requests: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
        self._pending: deque[str] = deque()
        self._current_id: str | None = None
        self._current_cancel: threading.Event | None = None
        self._current_adapter: Any | None = None
        self._current_started_monotonic: float | None = None
        self._shutdown_requested = False
        self._worker_done = threading.Event()
        self._state = "IDLE"
        # Process-group cleanup failure is a safety stop: keeping a pending
        # request alive here could start another GPU runner while the previous
        # ownership is still unverified.  clear_queue and shutdown remain
        # available so the UI can recover or exit explicitly.
        self._cleanup_blocked = False
        self._playback_blocked = False
        self._settings = {"interrupt_policy": "queue", "enter_to_send": True}
        self._profiles, self._profiles_by_id = _load_profiles(self.root)
        self._adapters = dict(adapters or default_adapters(self.root))
        self._playback = playback or MonitoredPlayback()
        self._playback_startup_error: dict[str, str] | None = None
        prepare = getattr(self._playback, "prepare", None)
        if callable(prepare):
            try:
                # Audio dependencies/PortAudio are initialized before the
                # generation worker accepts work.  A broken driver becomes a
                # readable submit error instead of blocking the first TTS job.
                prepare()
            except Exception as exc:
                code, message = _short_exception(exc)
                self._playback_startup_error = {"code": code, "message": message}
                self._state = "ERROR"
        self._store = TranscriptStore(self.root, self.session_id)
        self._settings.update(self._store.load_settings())
        # settings table may contain stale/invalid values from an older service;
        # keep protocol defaults at the boundary rather than leaking invalid UI state.
        if self._settings["interrupt_policy"] not in INTERRUPT_POLICIES:
            self._settings["interrupt_policy"] = "queue"
        if not isinstance(self._settings["enter_to_send"], bool):
            self._settings["enter_to_send"] = True
        self._worker = threading.Thread(target=self._worker_loop, name="aethertune-tts", daemon=True)
        self._worker.start()

    # ---------- externally visible protocol ----------

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            playback_open_blocked = self._read_playback_open_blocked()
            current_id = self._current_id
            state = self._state
            queue = project_queue(self._requests, current_id, self._pending)
        readiness = self.engine_readiness()
        return {
            "type": "speech_snapshot",
            "snapshot": {
                "session_id": self.session_id,
                "state": state,
                "audio_blocked": bool(
                    self._playback_blocked
                    or self._playback_startup_error is not None
                    or playback_open_blocked
                ),
                "current_request_id": current_id,
                "queue": queue,
                "transcript": self._store.list_transcripts(),
                "profiles": [project_profile(profile) for profile in self._profiles],
                "settings": copy.deepcopy(self._settings),
                "recent_phrases": [item["text"] for item in self._store.recent_phrases()],
                "favorites": [item["text"] for item in self._store.favorites()],
                "mic_enabled": False,
                "capabilities": {
                    "microphone": "WAITING",
                    "manual_text": "implemented",
                    "agent_reply": "PLANNED",
                },
                "engine_readiness": readiness,
            },
        }

    def engine_readiness(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for engine_id in sorted(ALLOWED_ENGINES):
            adapter = self._adapters.get(engine_id)
            if adapter is None:
                result[engine_id] = {
                    "engine_id": engine_id,
                    "ready": False,
                    "preflight_valid": False,
                    "state": "WAITING",
                    "errors": [{"code": "BACKEND_UNAVAILABLE", "message": "adapter 未註冊"}],
                    "supports_streaming_tts": False,
                }
                continue
            try:
                value = adapter.readiness() if hasattr(adapter, "readiness") else {
                    "engine_id": engine_id,
                    "preflight_valid": True,
                    "state": "WAITING",
                    "errors": [],
                    "supports_streaming_tts": False,
                }
                value = dict(value)
                # `ready` 容易被 UI 解讀成音訊 ready；只輸出 preflight_valid，
                # 並把 actual route/playback 維持 WAITING。
                value.pop("ready", None)
                value.setdefault("engine_id", engine_id)
                value.setdefault("preflight_valid", not bool(value.get("errors")))
                value.setdefault("state", "WAITING")
                value["audio_state"] = "WAITING"
                value["supports_streaming_tts"] = False
                result[engine_id] = value
            except Exception as exc:
                code, message = _short_exception(exc)
                result[engine_id] = {
                    "engine_id": engine_id,
                    "preflight_valid": False,
                    "state": "WAITING",
                    "errors": [{"code": code, "message": message}],
                    "audio_state": "WAITING",
                    "supports_streaming_tts": False,
                }
        return result

    def _read_playback_open_blocked(self) -> bool:
        """Read an adapter's native-open safety flag without assuming a class."""

        try:
            return bool(getattr(self._playback, "open_blocked", False))
        except Exception:
            return False

    def handle_command(self, command: Mapping[str, Any]) -> dict[str, Any]:
        """處理一行 JSON command，回傳立即 ack；generation 由 worker 處理。"""

        command_id = command.get("command_id") if isinstance(command, Mapping) else None
        if not isinstance(command_id, str) or not command_id.strip():
            command_id = str(uuid.uuid4())
        action = command.get("action") if isinstance(command, Mapping) else None
        if not isinstance(action, str):
            return self._ack(command_id, False, error=_error("COMMAND_INVALID", "action 必須是字串"))
        try:
            result = self._dispatch(action, command)
            return self._ack(command_id, True, result=result)
        except ValueError as exc:
            code, message = _short_exception(exc)
            return self._ack(command_id, False, error=_error(code, message))
        except (GenerationError, PlaybackError) as exc:
            code, message = _short_exception(exc)
            return self._ack(command_id, False, error=_error(code, message))
        except Exception as exc:  # protocol boundary must not crash the service
            return self._ack(
                command_id,
                False,
                error=_error("COMMAND_INVALID", f"command failed: {exc.__class__.__name__}: {exc}"),
            )

    def close(self, *, timeout: float = 3.0) -> None:
        """Exit path：有界取消 current，保留 evidence，最多等待 worker timeout。"""

        with self._condition:
            self._shutdown_requested = True
            for request_id in list(self._pending):
                self._cancel_queued_locked(request_id, "SERVICE_SHUTDOWN")
            self._pending.clear()
            current = self._current_id
            self._condition.notify_all()
        if current is not None:
            self._cancel_current("service_shutdown")
        self._worker.join(timeout=max(0.1, float(timeout)))
        closed: set[int] = set()
        for adapter in self._adapters.values():
            if id(adapter) in closed:
                continue
            closed.add(id(adapter))
            close = getattr(adapter, "close", None)
            if callable(close):
                close()
        self._store.close()

    # ---------- command implementations ----------

    def _dispatch(self, action: str, command: Mapping[str, Any]) -> dict[str, Any]:
        if action == "audio_devices":
            return list_audio_devices()
        if action == "submit":
            return self._submit(command)
        if action == "stop_speaking":
            return self._stop_speaking()
        if action == "clear_queue":
            return self._clear_queue()
        if action in {"remove", "move_up", "move_down", "speak_now"}:
            return self._queue_command(action, command)
        if action == "settings":
            return self._update_settings(command)
        if action == "favorite":
            return self._favorite(command)
        if action == "status":
            self._emit_snapshot()
            snap = self.snapshot()["snapshot"]
            return {"state": snap["state"], "current_request_id": snap["current_request_id"]}
        if action == "shutdown":
            # shutdown 只能由 App Exit 呼叫；同一服務不接受 remote/agent shortcut
            # 的替代 action。close() 會在 main finally 以 bounded timeout 執行。
            with self._condition:
                self._shutdown_requested = True
                for request_id in list(self._pending):
                    self._cancel_queued_locked(request_id, "SERVICE_SHUTDOWN")
                self._pending.clear()
                self._condition.notify_all()
            self._cancel_current("service_shutdown")
            self._emit_snapshot()
            return {"shutting_down": True}
        raise ValueError(f"COMMAND_INVALID: 未知 action：{action}")

    def _submit(self, command: Mapping[str, Any]) -> dict[str, Any]:
        with self._lock:
            if self._read_playback_open_blocked():
                self._playback_blocked = True
            if self._cleanup_blocked:
                raise ValueError(
                    "SERVICE_BLOCKED: process-group cleanup was not verified; clear queue or shutdown required"
                )
            if self._playback_blocked:
                raise ValueError(
                    "AUDIO_BLOCKED: output stream open timed out; shutdown and restart service required"
                )
            if self._playback_startup_error is not None:
                startup = self._playback_startup_error
                raise ValueError(
                    f"AUDIO_INIT_FAILED: {startup['code']}: {startup['message']}"
                )
        validated = validate_request(
            command, profiles=self._profiles_by_id,
            default_policy=self._settings["interrupt_policy"],
            validate_postfx=validate_postfx, resolve_route=resolve_route,
        )
        engine_id, policy, enqueue = validated.engine_id, validated.policy, validated.enqueue
        readiness = self.engine_readiness().get(engine_id, {})
        if not readiness.get("preflight_valid", False):
            errors = readiness.get("errors") or [{"code": "MODEL_NOT_FOUND", "message": "engine preflight failed"}]
            first = errors[0]
            raise ValueError(f"{first.get('code', 'MODEL_NOT_FOUND')}: {first.get('message', first)}")
        request_id = str(uuid.uuid4())
        created_at = utc_now()
        record = {
            "id": request_id,
            "session_id": self.session_id,
            "text": validated.text.strip(),
            "engine_id": engine_id,
            "voice_profile_id": validated.profile_id,
            "source": validated.source,
            "interrupt_policy": policy,
            "metadata": validated.metadata,
            "created_at": created_at,
            "priority": validated.priority,
            "status": "queued",
            "metrics": {"request_created_at": created_at},
            "error": None,
            # profile snapshot 會跟著 queued request 保存，避免之後改 profile
            # 導致已排程 request 偷換聲線。
            "profile_snapshot": validated.profile,
            "route_snapshot": copy.deepcopy(validated.route),
            "_cancel_audit": None,
        }
        with self._condition:
            if self._read_playback_open_blocked():
                self._playback_blocked = True
            if self._shutdown_requested:
                raise ValueError("SERVICE_STOPPING: service 正在 shutdown")
            if self._cleanup_blocked:
                raise ValueError(
                    "SERVICE_BLOCKED: process-group cleanup was not verified; clear queue or shutdown required"
                )
            if self._playback_blocked:
                raise ValueError(
                    "AUDIO_BLOCKED: output stream open timed out; shutdown and restart service required"
                )
            if self._playback_startup_error is not None:
                startup = self._playback_startup_error
                raise ValueError(
                    f"AUDIO_INIT_FAILED: {startup['code']}: {startup['message']}"
                )
            if not enqueue and policy == "reject_new" and self._current_id is not None:
                raise ValueError("QUEUE_BUSY: interrupt_policy=reject_new 且已有 current speech")
            self._requests[request_id] = record
            self._safe_save_request(record)
            if enqueue:
                # Add to Queue 永遠 FIFO；interrupt policy 只影響 enqueue=false
                # 的 Speak Now，避免 UI 明確選擇 queue 卻意外打斷 current。
                self._pending.append(request_id)
            elif self._current_id is None:
                self._pending.appendleft(request_id)
            elif policy == "queue":
                self._pending.append(request_id)
            elif policy == "interrupt_current":
                self._cancel_current("speak_now")
                self._pending.appendleft(request_id)
            else:
                # reject_new with a current request was handled above; this is
                # defensive in case state changes between validation and lock.
                raise ValueError("QUEUE_BUSY: interrupt_policy=reject_new")
            if self._current_id is None:
                self._state = "QUEUED"
        # Publish QUEUED before waking the worker when this is the first
        # pending request.  That makes the state observable instead of racing
        # directly from IDLE to GENERATING in the same command turn.
        try:
            self._emit_snapshot()
        finally:
            with self._condition:
                self._condition.notify_all()
        return {"request_id": request_id, "status": "queued", "engine_id": engine_id}

    def _stop_speaking(self) -> dict[str, Any]:
        with self._lock:
            request_id = self._current_id
        if request_id is None:
            self._emit_snapshot()
            return {"current_request_id": None, "stopped": False}
        self._cancel_current("stop_speaking")
        self._emit_snapshot()
        return {"current_request_id": request_id, "stopped": True}

    def _clear_queue(self) -> dict[str, Any]:
        with self._condition:
            removed = list(self._pending)
            for request_id in removed:
                self._cancel_queued_locked(request_id, "QUEUE_CLEARED")
            self._pending.clear()
            self._condition.notify_all()
        self._emit_snapshot()
        return {"removed_request_ids": removed, "current_request_id": self._current_id}

    def _queue_command(self, action: str, command: Mapping[str, Any]) -> dict[str, Any]:
        request_id = command.get("id", command.get("request_id"))
        if not isinstance(request_id, str) or request_id not in self._requests:
            raise ValueError("QUEUE_INVALID: 找不到 request id")
        with self._condition:
            if request_id == self._current_id:
                raise ValueError("QUEUE_INVALID: current request 只能使用 stop_speaking")
            if request_id not in self._pending:
                raise ValueError("QUEUE_INVALID: request 不在 pending queue")
            index = list(self._pending).index(request_id)
            if action == "remove":
                self._pending.remove(request_id)
                self._cancel_queued_locked(request_id, "REMOVED")
            elif action == "move_up":
                if index > 0:
                    items = list(self._pending)
                    items[index - 1], items[index] = items[index], items[index - 1]
                    self._pending = deque(items)
            elif action == "move_down":
                if index < len(self._pending) - 1:
                    items = list(self._pending)
                    items[index + 1], items[index] = items[index], items[index + 1]
                    self._pending = deque(items)
            elif action == "speak_now":
                policy = self._requests[request_id].get("interrupt_policy", self._settings["interrupt_policy"])
                if self._current_id is not None and policy == "reject_new":
                    raise ValueError("QUEUE_BUSY: speak_now rejected by request interrupt_policy")
                self._pending.remove(request_id)
                self._pending.appendleft(request_id)
                if self._current_id is not None and policy == "interrupt_current":
                    # Keep the condition lock while selecting the current
                    # request, so worker completion cannot make cancellation
                    # target the newly-fronted request.
                    self._cancel_current("speak_now")
                if self._current_id is None:
                    self._state = "QUEUED"
            self._condition.notify_all()
        self._emit_snapshot()
        return {"request_id": request_id, "action": action, "pending_order": list(self._pending)}

    def _update_settings(self, command: Mapping[str, Any]) -> dict[str, Any]:
        value = command.get("settings", command)
        if not isinstance(value, Mapping):
            raise ValueError("SETTINGS_INVALID: settings 必須是 object")
        updates: dict[str, Any] = {}
        if "interrupt_policy" in value:
            policy = value["interrupt_policy"]
            if policy not in INTERRUPT_POLICIES:
                raise ValueError("SETTINGS_INVALID: interrupt_policy 不合法")
            updates["interrupt_policy"] = policy
        if "enter_to_send" in value:
            if not isinstance(value["enter_to_send"], bool):
                raise ValueError("SETTINGS_INVALID: enter_to_send 必須是 boolean")
            updates["enter_to_send"] = value["enter_to_send"]
        if not updates:
            raise ValueError("SETTINGS_INVALID: 沒有可更新的 settings")
        with self._lock:
            self._settings.update(updates)
        try:
            self._store.save_settings(self._settings)
        except Exception as exc:
            raise ValueError(f"SETTINGS_FAILED: 無法保存 settings：{exc}") from exc
        self._emit_snapshot()
        return {"settings": copy.deepcopy(self._settings)}

    def _favorite(self, command: Mapping[str, Any]) -> dict[str, Any]:
        text = command.get("text")
        if not isinstance(text, str):
            favorite = command.get("favorite")
            if isinstance(favorite, Mapping):
                text = favorite.get("text")
                pinned = favorite.get("pinned", True)
            else:
                pinned = True
        else:
            pinned = command.get("pinned", True)
        if not isinstance(text, str) or not isinstance(pinned, bool):
            raise ValueError("FAVORITE_INVALID: text/pinned 不合法")
        result = self._store.set_favorite(text, pinned)
        self._emit_snapshot()
        return {"favorite": result}

    # ---------- worker and lifecycle ----------

    def _worker_loop(self) -> None:
        try:
            while True:
                with self._condition:
                    while (
                        (not self._pending or self._cleanup_blocked or self._playback_blocked)
                        and not self._shutdown_requested
                    ):
                        self._condition.wait(timeout=0.25)
                    if self._shutdown_requested and not self._pending:
                        return
                    if self._cleanup_blocked:
                        # Do not consume pending requests while a previous WSL
                        # group has failed ownership cleanup verification.
                        # close()/shutdown clears pending and wakes this loop.
                        continue
                    if self._playback_blocked:
                        # A native OutputStream opener can remain unwinding
                        # after its bounded timeout.  Do not overlap another
                        # PortAudio stream; shutdown is the recovery boundary.
                        continue
                    request_id = self._pending.popleft()
                    record = self._requests[request_id]
                    record["status"] = "generating"
                    self._safe_save_request(record)
                    self._current_id = request_id
                    cancel_event = threading.Event()
                    self._current_cancel = cancel_event
                    self._current_adapter = self._adapters.get(record["engine_id"])
                    self._current_started_monotonic = time.perf_counter()
                    self._state = "GENERATING"
                self._emit_snapshot()
                self._run_one(record, cancel_event)
                with self._condition:
                    if self._read_playback_open_blocked():
                        # PlaybackCancelled can hide the original open timeout
                        # when Stop races the native opener.  The public flag
                        # preserves the safety stop after _run_one returns.
                        self._playback_blocked = True
                    if self._current_id == request_id:
                        self._current_id = None
                        self._current_cancel = None
                        self._current_adapter = None
                        self._current_started_monotonic = None
                    if self._cleanup_blocked or self._playback_blocked:
                        # A failed/unverified cancellation is terminal for this
                        # service instance until Exit; never start the next GPU
                        # request under uncertain process ownership.
                        self._state = "ERROR"
                    elif self._pending:
                        # A cancellation/failure can leave another request
                        # pending; never expose stale STOPPING between jobs.
                        self._state = "QUEUED"
                    elif self._state != "ERROR":
                        self._state = "IDLE"
                    self._condition.notify_all()
                self._emit_snapshot()
        finally:
            self._worker_done.set()

    def _run_one(self, record: dict[str, Any], cancel_event: threading.Event) -> None:
        request_id = record["id"]
        started_at = utc_now()
        job_dir = self.root / "artifacts" / "sessions" / self.session_id / "jobs" / request_id
        output_path = job_dir / f"{request_id}.wav"
        job_dir.mkdir(parents=True, exist_ok=True)
        evidence_path = self.root / "artifacts" / "sessions" / self.session_id / f"{request_id}.evidence.json"
        generation_result: GenerationResult | None = None
        playback_result: PlaybackResult | None = None
        try:
            record["metrics"]["generation_started_at"] = started_at
            self._safe_save_request(record)
            self._emit_snapshot()
            adapter = self._adapters[record["engine_id"]]
            # 兩個 TTS 模型可能同時佔用 GPU；切換引擎時先釋放舊 worker。
            for other_id, other in self._adapters.items():
                if other_id != record["engine_id"] and other is not adapter:
                    close = getattr(other, "close", None)
                    if callable(close):
                        close()
            generation_result = adapter.generate(record, output_path, job_dir, cancel_event)
            if cancel_event.is_set():
                raise GenerationCancelled("generation cancelled")
            record["metrics"].update(generation_result.metrics)
            # non-streaming runner 的完整 WAV 在此刻才成為可播放 buffer；
            # 這個時間是 generation TTFA，不能被 playback driver 的首個
            # OutputStream write 時間覆寫。
            generated_buffer_at = utc_now()
            record["metrics"]["first_audio_at"] = generated_buffer_at
            with self._lock:
                record["status"] = "ready"
                self._state = "BUFFERING"
            self._safe_save_request(record)
            self._emit_snapshot()
            route = record["route_snapshot"]
            playback_path, postfx_evidence = render_postfx(
                generation_result.audio_path, output_path.with_suffix(".postfx.wav"),
                record["metadata"]["postfx"], cancel_event,
            )
            record["metrics"].update(postfx_enabled=postfx_evidence["enabled"],
                                     postfx_seconds=postfx_evidence["seconds"],
                                     playback_audio_path=str(playback_path))
            record["metrics"]["playback_started_at"] = utc_now()
            with self._lock:
                record["status"] = "playing"
                self._state = "PLAYING"
            self._safe_save_request(record)
            self._emit_snapshot()
            playback_result = self._playback.play(playback_path, route, cancel_event)
            if cancel_event.is_set():
                raise PlaybackCancelled("playback cancelled")
            first_playback_audio_at = playback_result.first_audio_at
            ended_at = utc_now()
            record["metrics"].update(
                {
                    "first_playback_audio_at": first_playback_audio_at,
                    "ttfa_ms": round((_parse_iso_ms(generated_buffer_at) - _parse_iso_ms(record["created_at"])), 3),
                    # 以 durable request_created_at 到 playback completion
                    # 計算，包含 queue 等待；generation_started_at 另存以便
                    # 拆解 generation latency。
                    "total_response_ms": round(
                        _parse_iso_ms(ended_at) - _parse_iso_ms(record["created_at"]), 3
                    ),
                    "playback_seconds": playback_result.duration_seconds,
                    "route_status": playback_result.route_status,
                    "playback_verified": playback_result.playback_verified,
                    "output_name": playback_result.output_name,
                    "host_api": playback_result.host_api,
                    "underrun_count": playback_result.underrun_count,
                    "source_sample_rate": playback_result.source_sample_rate,
                    "source_channels": playback_result.source_channels,
                    "rendered_sample_rate": playback_result.rendered_sample_rate,
                    "rendered_channels": playback_result.rendered_channels,
                    "monitor_status": playback_result.monitor_status,
                    "monitor_error": playback_result.monitor_error,
                    "completed_at": ended_at,
                    "playback_completed_at": ended_at,
                }
            )
            with self._lock:
                record["status"] = "completed"
                record["error"] = None
            self._safe_save_request(record)
            evidence = dict(generation_result.evidence)
            evidence["postfx"] = postfx_evidence
            evidence["request_id"] = request_id
            evidence["route_resolution"] = {
                "requested": copy.deepcopy(route),
                "resolved_output": playback_result.output_name,
                "resolved_host_api": playback_result.host_api,
                "rack_profile_id": route.get("rack_profile_id"),
                "route_profile_id": route.get("route_profile_id"),
                "status": playback_result.route_status,
                "playback_verified": playback_result.playback_verified,
                "source_sample_rate": playback_result.source_sample_rate,
                "source_channels": playback_result.source_channels,
                "rendered_sample_rate": playback_result.rendered_sample_rate,
                "rendered_channels": playback_result.rendered_channels,
                "monitor": {
                    "status": playback_result.monitor_status,
                    "output": playback_result.monitor_output,
                    "host_api": playback_result.monitor_host_api,
                    "frames_written": playback_result.monitor_frames_written,
                    "underrun_count": playback_result.monitor_underrun_count,
                    "first_audio_at": playback_result.monitor_first_audio_at,
                    "error": playback_result.monitor_error,
                },
            }
            try:
                transcript = self._store.record_completed(
                    record,
                    started_at=started_at,
                    ended_at=ended_at,
                    metrics=record["metrics"],
                    route=route,
                )
            except Exception as exc:
                # Playback already completed.  Do not replay TTS or rewrite
                # the request as cancelled/failed merely because canonical
                # transcript persistence/export failed after the audio event.
                record["error"] = _error("TRANSCRIPT_STORAGE_FAILED", str(exc))
                self._safe_save_request(record)
                evidence["status"] = "completed"
                evidence["storage_error"] = record["error"]
                evidence["transcript"] = None
                self._safe_write_evidence(evidence_path, evidence)
                return
            evidence["transcript"] = {
                "id": transcript["id"],
                "speech_status": "completed",
                "source_type": "self",
                "provider": transcript["provider"],
                "transcript_provider": transcript["transcript_provider"],
                "source": transcript["source"],
            }
            self._safe_write_evidence(evidence_path, evidence)
        except (GenerationCancelled, PlaybackCancelled) as exc:
            with self._lock:
                record["status"] = "cancelled"
                record["error"] = self._cancel_error(record, exc)
                self._state = "IDLE"
            self._safe_save_request(record)
            self._safe_write_evidence(
                evidence_path,
                {
                    "request_id": request_id,
                    "status": "cancelled",
                    "error": record["error"],
                    "pid_audit": self._cancel_audit(record, exc),
                    "transcript": None,
                },
            )
        except (GenerationError, PlaybackError, OSError) as exc:
            code, message = _short_exception(exc)
            if code == "PLAYBACK_OPEN_TIMEOUT":
                with self._lock:
                    self._playback_blocked = True
            if cancel_event.is_set():
                with self._lock:
                    record["status"] = "cancelled"
                    record["error"] = self._cancel_error(record, exc)
                    self._state = "IDLE"
                self._safe_save_request(record)
                self._safe_write_evidence(
                    evidence_path,
                    {
                        "request_id": request_id,
                        "status": "cancelled",
                        "error": record["error"],
                        "pid_audit": self._cancel_audit(record, exc),
                        "transcript": None,
                    },
                )
                return
            with self._lock:
                record["status"] = "failed"
                record["error"] = _error(code, message)
                self._state = "ERROR"
            self._safe_save_request(record)
            evidence: dict[str, Any] = {
                "request_id": request_id,
                "status": "failed",
                "error": record["error"],
                "transcript": None,
            }
            if generation_result is not None:
                evidence.update(generation_result.evidence)
            else:
                evidence["model_fingerprint"] = self._safe_model_evidence(record["engine_id"])
            self._safe_write_evidence(evidence_path, evidence)
        except Exception as exc:
            with self._lock:
                record["status"] = "failed"
                record["error"] = _error("BACKEND_CRASH", f"unexpected: {exc}")
                self._state = "ERROR"
            self._safe_save_request(record)
            self._safe_write_evidence(
                evidence_path,
                {"request_id": request_id, "status": "failed", "error": record["error"], "transcript": None},
            )

    def _cancel_current(self, reason: str) -> dict[str, Any] | None:
        with self._lock:
            current_id = self._current_id
            cancel_event = self._current_cancel
            adapter = self._current_adapter
            record = self._requests.get(current_id) if current_id else None
            if cancel_event is not None and self._current_id == current_id:
                # Publish STOPPING before the worker can observe cancellation;
                # this closes the stop/finish race and prevents a stale state.
                self._state = "STOPPING"
        if cancel_event is None:
            return None
        cancel_event.set()
        audit = None
        if adapter is not None and hasattr(adapter, "cancel"):
            try:
                audit = adapter.cancel(reason)
            except Exception as exc:
                audit = {"event": "cancel_error", "reason": str(exc)}
        if hasattr(self._playback, "stop"):
            try:
                self._playback.stop()
            except Exception:
                pass
        if record is not None:
            with self._lock:
                record["_cancel_audit"] = audit
        return audit

    def _cancel_queued_locked(self, request_id: str, reason: str) -> None:
        record = self._requests[request_id]
        record["status"] = "cancelled"
        record["error"] = _error("CANCELLED", reason)
        record["metrics"] = {}
        self._safe_save_request(record)

    def _cancel_audit(self, record: Mapping[str, Any], exc: BaseException) -> Any:
        audit = record.get("_cancel_audit")
        if audit is not None:
            return audit
        # Adapter may include a JSON pid audit in GenerationCancelled text.
        try:
            data = json.loads(str(exc))
            if isinstance(data, dict) and "pid_audit" in data:
                return data["pid_audit"]
        except json.JSONDecodeError:
            pass
        return None

    def _cancel_error(self, record: Mapping[str, Any], exc: BaseException) -> dict[str, Any]:
        """保留取消結果；未驗證的 process cleanup 不可被標成成功。"""

        audit = self._cancel_audit(record, exc)
        event = self._cleanup_event(audit)
        if event in {"group_cancel_failed", "group_cancel_unverified"}:
            with self._lock:
                self._cleanup_blocked = True
            return _error(
                "CANCEL_CLEANUP_FAILED",
                "語音已取消，但背景程序清理未驗證；請重新啟動服務",
                cleanup_event=event,
                cleanup_verified=False,
                cleanup_blocked=True,
            )
        if event == "group_cancelled":
            return _error(
                "CANCELLED",
                "語音已取消，背景程序群組已清理",
                cleanup_event=event,
                cleanup_verified=True,
            )
        result = _error("CANCELLED", "語音已取消")
        if event is not None:
            result.update({"cleanup_event": event, "cleanup_verified": False})
        return result

    @staticmethod
    def _cleanup_event(audit: Any) -> str | None:
        """Find the strongest process cleanup outcome in nested pid audits."""

        events: list[str] = []

        def visit(value: Any) -> None:
            if isinstance(value, Mapping):
                event = value.get("event")
                if isinstance(event, str):
                    events.append(event)
                for key in ("events", "pid_audit", "audit", "cleanup"):
                    if key in value:
                        visit(value[key])
            elif isinstance(value, (list, tuple)):
                for item in value:
                    visit(item)

        visit(audit)
        for event in ("group_cancel_failed", "group_cancel_unverified", "group_cancelled"):
            if event in events:
                return event
        return events[0] if events else None

    def _safe_model_evidence(self, engine_id: str) -> dict[str, Any]:
        adapter = self._adapters.get(engine_id)
        if adapter is None:
            return {"engine_id": engine_id, "status": "unavailable"}
        try:
            readiness = adapter.readiness()
            return {"engine_id": engine_id, "preflight": readiness}
        except Exception as exc:
            return {"engine_id": engine_id, "error": str(exc)}

    @staticmethod
    def _write_evidence(path: Path, payload: Mapping[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    def _safe_write_evidence(self, path: Path, payload: Mapping[str, Any]) -> None:
        try:
            self._write_evidence(path, payload)
        except OSError:
            # transcript/queue state already lives in SQLite; evidence disk failure
            # must not kill the long-lived worker or erase a completed transcript.
            pass

    def _safe_save_request(self, record: Mapping[str, Any]) -> None:
        try:
            self._store.save_request(record)
        except Exception:
            # SQLite durability is best effort at the protocol edge; an already
            # accepted request must not terminate the queue worker on a transient
            # export/database error.
            pass

    @staticmethod
    def _ack(command_id: str, accepted: bool, *, result: Any | None = None, error: Any | None = None) -> dict[str, Any]:
        ack: dict[str, Any] = {
            "type": "speech_ack",
            "command_id": command_id,
            "accepted": accepted,
        }
        if result is not None:
            ack["result"] = result
        if error is not None:
            ack["error"] = error
        return ack

    def _emit_snapshot(self) -> None:
        if self._emit is not None:
            self._emit(self.snapshot())


TTSOrchestrator = SpeechService


_STDOUT_LOCK = threading.Lock()


def _emit_stdout(event: dict[str, Any]) -> None:
    with _STDOUT_LOCK:
        print(json.dumps(event, ensure_ascii=False, default=str), flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AetherTune Manual TTS JSONL service")
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args(argv)
    service = SpeechService(args.root, emit=_emit_stdout)
    _emit_stdout(service.snapshot())
    try:
        should_break = False
        for line in __import__("sys").stdin:
            if not line.strip():
                continue
            value: Any = None
            try:
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ValueError("command 必須是 JSON object")
                ack = service.handle_command(value)
            except (json.JSONDecodeError, ValueError) as exc:
                ack = SpeechService._ack(
                    str(uuid.uuid4()), False, error=_error("COMMAND_INVALID", str(exc))
                )
            _emit_stdout(ack)
            if isinstance(value, dict) and value.get("action") == "shutdown":
                should_break = True
            if should_break:
                break
    finally:
        service.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
