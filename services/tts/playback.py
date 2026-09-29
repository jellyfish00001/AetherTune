"""TTS playback adapter。

播放是 generation 之後的獨立階段。沒有明確的 output name + host_api 時，
adapter 會拒絕；不會把音訊悄悄送到系統預設喇叭。
"""

from __future__ import annotations

import time
import wave
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Event, RLock, Thread
from typing import Any


class PlaybackError(RuntimeError):
    """播放 route、音訊檔或 sounddevice 失敗。"""


class PlaybackCancelled(PlaybackError):
    """播放期間收到 stop/interrupt。"""


@dataclass(frozen=True)
class PlaybackResult:
    duration_seconds: float
    output_name: str
    host_api: str
    frames_written: int
    route_status: str = "WAITING"
    playback_verified: bool = False
    stopped: bool = False
    first_audio_at: str | None = None
    underrun_count: int = 0
    source_sample_rate: int | None = None
    source_channels: int | None = None
    rendered_sample_rate: int | None = None
    rendered_channels: int | None = None


def resolve_route(route: Any) -> dict[str, str]:
    """驗證 request route，保留 explicit endpoint 身分。"""

    if not isinstance(route, dict):
        raise PlaybackError("ROUTE_FAILED: request metadata.route 必須是 object")
    output = route.get("output")
    host_api = route.get("host_api")
    if not isinstance(output, str) or not output.strip():
        raise PlaybackError("DEVICE_NOT_FOUND: 必須明確指定 route.output")
    if not isinstance(host_api, str) or not host_api.strip():
        raise PlaybackError("DEVICE_NOT_FOUND: 必須明確指定 route.host_api")
    # route profile 是外部／手動 rack 的宣告；目前 evidence 仍 WAITING，不能
    # 轉成 LIVE 或假稱 post-FX 已自動套用。
    route_profile_id = route.get("route_profile_id", "seed-vc-virtual-route")
    rack_profile_id = route.get("rack_profile_id", "seed-vc-neutral")
    if not isinstance(route_profile_id, str) or not route_profile_id.strip():
        raise PlaybackError("ROUTE_FAILED: route_profile_id 不可為空")
    if not isinstance(rack_profile_id, str) or not rack_profile_id.strip():
        raise PlaybackError("ROUTE_FAILED: rack_profile_id 不可為空")
    return {
        "output": output.strip(),
        "host_api": host_api.strip(),
        "rack_profile_id": rack_profile_id.strip(),
        "route_profile_id": route_profile_id.strip(),
    }


def list_audio_devices(*, timeout_seconds: float = 3.0) -> dict[str, list[dict[str, Any]]]:
    """列出 PortAudio 端點，供 UI 選擇與播放路由相同的精確名稱／Host API。"""

    done = Event()
    outcome: dict[str, Any] = {"value": None, "error": None}

    def enumerate_devices() -> None:
        try:
            import sounddevice as sd

            hostapis = sd.query_hostapis()
            devices = sd.query_devices()
            defaults = sd.default.device
            default_input = int(defaults[0])
            default_output = int(defaults[1])
            inputs: list[dict[str, Any]] = []
            outputs: list[dict[str, Any]] = []
            for index, device in enumerate(devices):
                host_api = str(hostapis[int(device["hostapi"])]["name"])
                name = str(device["name"])
                input_channels = int(device.get("max_input_channels", 0))
                output_channels = int(device.get("max_output_channels", 0))
                if input_channels >= 1:
                    inputs.append({"name": name, "host_api": host_api, "channels": input_channels, "is_default": index == default_input})
                if output_channels >= 2:
                    outputs.append({"name": name, "host_api": host_api, "channels": output_channels, "is_default": index == default_output})
            for items in (inputs, outputs):
                counts: dict[tuple[str, str], int] = {}
                for item in items:
                    key = (item["host_api"], item["name"])
                    counts[key] = counts.get(key, 0) + 1
                for item in items:
                    item["selectable"] = counts[(item["host_api"], item["name"])] == 1
            outcome["value"] = {"inputs": inputs, "outputs": outputs}
        except BaseException as exc:
            outcome["error"] = exc
        finally:
            done.set()

    probe = Thread(target=enumerate_devices, name="aethertune-device-list", daemon=True)
    probe.start()
    if not done.wait(timeout=max(0.1, float(timeout_seconds))):
        raise PlaybackError("DEVICE_INIT_TIMEOUT: PortAudio 裝置列舉逾時")
    if outcome["error"] is not None:
        raise PlaybackError(f"DEVICE_NOT_FOUND: 無法讀取 audio endpoints：{outcome['error']}") from outcome["error"]
    return outcome["value"]


class SoundDevicePlayback:
    """以 soundfile + sounddevice OutputStream 播放明確的 endpoint。"""

    def __init__(
        self,
        *,
        chunk_frames: int = 960,
        watchdog_grace_seconds: float = 10.0,
        stream_open_timeout_seconds: float = 3.0,
    ) -> None:
        self.chunk_frames = max(256, int(chunk_frames))
        self.watchdog_grace_seconds = max(0.0, float(watchdog_grace_seconds))
        self.stream_open_timeout_seconds = max(0.1, float(stream_open_timeout_seconds))
        self.target_sample_rate = 48000
        self.target_channels = 2
        self._stream = None
        self._stream_lock = RLock()
        self._modules: tuple[Any, Any, Any, Any] | None = None
        self._open_blocked = False

    @property
    def open_blocked(self) -> bool:
        """True after a native stream opener timed out and may still unwind."""

        with self._stream_lock:
            return self._open_blocked

    def _load_modules(self) -> tuple[Any, Any, Any, Any]:
        """Load audio dependencies once, before the worker handles a request."""

        with self._stream_lock:
            if self._modules is not None:
                return self._modules
            try:
                import sounddevice as sd
                import soundfile as sf
                import numpy as np
                from scipy.signal import resample_poly
            except ImportError as exc:  # pragma: no cover - machine dependency
                raise PlaybackError(
                    "DEVICE_NOT_FOUND: soundfile/sounddevice/numpy/scipy 未安裝"
                ) from exc
            self._modules = (sd, sf, np, resample_poly)
            return self._modules

    def prepare(self, *, timeout_seconds: float = 3.0) -> None:
        """Prewarm imports and PortAudio before the service worker starts.

        Python imports run on the caller thread so the first request does not
        pay lazy import cost.  Device enumeration is bounded in a daemon
        helper because a broken Windows driver must become a readable startup
        error rather than hold the JSONL worker forever.
        """

        sd, _sf, _np, _resample_poly = self._load_modules()
        done = Event()
        outcome: dict[str, BaseException | None] = {"error": None}

        def enumerate_devices() -> None:
            try:
                sd.query_hostapis()
                sd.query_devices()
            except BaseException as exc:  # propagate to the caller below
                outcome["error"] = exc
            finally:
                done.set()

        probe = Thread(target=enumerate_devices, name="aethertune-audio-init", daemon=True)
        probe.start()
        if not done.wait(timeout=max(0.1, float(timeout_seconds))):
            raise PlaybackError("DEVICE_INIT_TIMEOUT: PortAudio endpoint enumeration timed out")
        error = outcome["error"]
        if error is not None:
            raise PlaybackError(f"DEVICE_NOT_FOUND: 無法初始化 audio endpoints：{error}") from error

    def stop(self) -> None:
        with self._stream_lock:
            stream = self._stream
        if stream is not None:
            try:
                stream.abort()
            except Exception:
                # stop path 不能因 driver 已經退出而遮蔽原本的 cancellation。
                pass

    def _resolve_device(self, route: dict[str, str], sd: Any) -> tuple[int, dict]:
        try:
            hostapis = sd.query_hostapis()
            devices = sd.query_devices()
        except Exception as exc:  # pragma: no cover - driver dependent
            raise PlaybackError(f"DEVICE_NOT_FOUND: 無法讀取 audio endpoints：{exc}") from exc
        matches = []
        for index, device in enumerate(devices):
            try:
                api_name = hostapis[device["hostapi"]]["name"]
                if (
                    device["name"] == route["output"]
                    and api_name == route["host_api"]
                    and int(device.get("max_output_channels", 0)) >= self.target_channels
                ):
                    matches.append((index, device))
            except (KeyError, TypeError, ValueError):
                continue
        if len(matches) != 1:
            raise PlaybackError(
                "DEVICE_NOT_FOUND: output name + host_api 必須唯一；"
                f"output={route['output']!r}, host_api={route['host_api']!r}, matches={len(matches)}"
            )
        return matches[0]

    def play(
        self,
        audio_path: Path,
        route: dict[str, str],
        cancel_event: Event,
    ) -> PlaybackResult:
        route = resolve_route(route)
        if not audio_path.is_file():
            raise PlaybackError(f"ROUTE_FAILED: 找不到 generated WAV：{audio_path}")
        with self._stream_lock:
            if self._open_blocked:
                raise PlaybackError(
                    "AUDIO_BLOCKED: previous output stream open timed out; restart service before retry"
                )
        sd, sf, np, resample_poly = self._load_modules()
        try:
            audio, sample_rate = sf.read(str(audio_path), dtype="float32", always_2d=True)
        except Exception as exc:  # pragma: no cover - file/codec dependent
            raise PlaybackError(f"ROUTE_FAILED: 無法讀取 generated WAV：{exc}") from exc
        if getattr(audio, "size", 0) == 0 or int(getattr(audio, "shape", [0])[0]) == 0:
            raise PlaybackError("ROUTE_FAILED: generated WAV 沒有 frame")
        if not bool(np.isfinite(audio).all()):
            raise PlaybackError("ROUTE_FAILED: generated WAV 含 NaN/Infinity")
        if not bool(np.any(np.abs(audio) > 0)):
            raise PlaybackError("ROUTE_FAILED: generated WAV 為全零")
        source_sample_rate = int(sample_rate)
        source_channels = int(audio.shape[1])
        rendered = audio
        if source_sample_rate != self.target_sample_rate:
            import math

            divisor = math.gcd(source_sample_rate, self.target_sample_rate)
            rendered = resample_poly(
                rendered,
                self.target_sample_rate // divisor,
                source_sample_rate // divisor,
                axis=0,
            ).astype("float32", copy=False)
        if source_channels == 1:
            rendered = np.repeat(rendered, self.target_channels, axis=1)
        elif source_channels >= self.target_channels:
            rendered = rendered[:, : self.target_channels]
        else:
            raise PlaybackError(f"ROUTE_FAILED: 不支援 {source_channels} channel WAV")
        if rendered.size == 0 or not bool(np.isfinite(rendered).all()):
            raise PlaybackError("ROUTE_FAILED: rendered audio 含非有限樣本")
        if not bool(np.any(np.abs(rendered) > 0)):
            raise PlaybackError("ROUTE_FAILED: rendered audio 為全零")
        rendered_sample_rate = self.target_sample_rate
        rendered_channels = self.target_channels
        device_index, device = self._resolve_device(route, sd)
        channels = rendered_channels
        # 以 resolved device index 建立 stream；route 的 exact name + host_api 已
        # 在 _resolve_device 核對，故不會落到 sounddevice 的 default device。
        watchdog_fired = Event()
        watchdog_done = Event()
        try:
            callback_stop = getattr(sd, "CallbackStop", None)
            callback_abort = getattr(sd, "CallbackAbort", None)
            callback_lock = RLock()
            callback_state = {
                "offset": 0,
                "first_audio_at": None,
                "underrun_count": 0,
                "callback_error": None,
                "completed": False,
            }
            finished = Event()

            def finished_callback() -> None:
                finished.set()

            def callback(outdata, frames, time_info, status) -> None:
                del time_info
                try:
                    # Always clear the complete PortAudio buffer first.  This
                    # prevents stale samples when the final callback is short.
                    outdata.fill(0)
                    with callback_lock:
                        if bool(getattr(status, "output_underflow", False)):
                            callback_state["underrun_count"] += 1
                        if cancel_event.is_set() or watchdog_fired.is_set():
                            if callback_abort is not None:
                                raise callback_abort
                            return
                        offset = int(callback_state["offset"])
                        remaining = len(rendered) - offset
                        count = min(int(frames), max(0, remaining))
                        if count > 0:
                            outdata[:count, :channels] = rendered[offset : offset + count, :channels]
                            if callback_state["first_audio_at"] is None:
                                callback_state["first_audio_at"] = datetime.now(
                                    timezone.utc
                                ).isoformat(timespec="milliseconds").replace("+00:00", "Z")
                            callback_state["offset"] = offset + count
                        if callback_state["offset"] >= len(rendered):
                            callback_state["completed"] = True
                            if callback_stop is not None:
                                raise callback_stop
                except BaseException as exc:  # callback errors cross thread boundary
                    known = tuple(item for item in (callback_stop, callback_abort) if item is not None)
                    if known and isinstance(exc, known):
                        raise
                    with callback_lock:
                        callback_state["callback_error"] = exc
                    if callback_abort is not None:
                        raise callback_abort from exc
                    raise

            open_done = Event()
            open_cancel = Event()
            open_outcome: dict[str, Any] = {"stream": None, "error": None}

            def open_stream() -> None:
                try:
                    candidate = sd.OutputStream(
                        device=device_index,
                        samplerate=rendered_sample_rate,
                        channels=channels,
                        blocksize=self.chunk_frames,
                        dtype="float32",
                        callback=callback,
                        finished_callback=finished_callback,
                    )
                    if open_cancel.is_set():
                        try:
                            candidate.abort()
                        finally:
                            close = getattr(candidate, "close", None)
                            if callable(close):
                                close()
                    else:
                        open_outcome["stream"] = candidate
                        with self._stream_lock:
                            self._stream = candidate
                except BaseException as exc:  # propagate to the caller below
                    open_outcome["error"] = exc
                finally:
                    open_done.set()

            opener = Thread(target=open_stream, name="aethertune-audio-open", daemon=True)
            opener.start()
            if not open_done.wait(timeout=self.stream_open_timeout_seconds):
                open_cancel.set()
                self.stop()
                with self._stream_lock:
                    # A native open thread may still be unwinding.  Do not
                    # start another OutputStream on the same endpoint from
                    # this service instance; process exit is the recovery
                    # boundary when the driver did not provide cancellation.
                    self._open_blocked = True
                raise PlaybackError(
                    "PLAYBACK_OPEN_TIMEOUT: output stream did not open within "
                    f"{self.stream_open_timeout_seconds:.3f}s"
                )
            opener.join(timeout=0.1)
            if open_outcome["error"] is not None:
                raise open_outcome["error"]
            stream = open_outcome["stream"]
            if stream is None:
                raise PlaybackError("ROUTE_FAILED: output stream open returned no stream")
        except Exception as exc:  # pragma: no cover - driver dependent
            if cancel_event.is_set():
                raise PlaybackCancelled("playback cancelled while opening output") from exc
            if isinstance(exc, PlaybackError):
                raise
            raise PlaybackError(f"ROUTE_FAILED: 無法開啟 output stream：{exc}") from exc
        frames_written = 0
        stopped = False
        underrun_count = 0
        first_audio_at = None
        watchdog_timeout = (len(rendered) / float(rendered_sample_rate)) + self.watchdog_grace_seconds

        def abort_if_stalled() -> None:
            if not watchdog_done.wait(timeout=max(0.1, watchdog_timeout)):
                watchdog_fired.set()
                self.stop()

        watchdog = Thread(target=abort_if_stalled, name="aethertune-playback-watchdog", daemon=True)
        watchdog.start()
        stopped = False
        try:
            try:
                with stream:
                    hard_deadline = time.monotonic() + watchdog_timeout + 1.0
                    cancel_deadline: float | None = None
                    while not finished.wait(timeout=0.05):
                        now = time.monotonic()
                        if cancel_event.is_set():
                            stopped = True
                            if cancel_deadline is None:
                                cancel_deadline = now + 2.0
                            self.stop()
                            if now >= cancel_deadline:
                                break
                        elif watchdog_fired.is_set():
                            self.stop()
                        if now >= hard_deadline:
                            break
            except (PlaybackCancelled, PlaybackError):
                raise
            except Exception as exc:  # pragma: no cover - driver dependent
                if cancel_event.is_set():
                    stopped = True
                    raise PlaybackCancelled("playback cancelled by output driver") from exc
                if watchdog_fired.is_set():
                    raise PlaybackError(
                        f"PLAYBACK_TIMEOUT: output stream exceeded {watchdog_timeout:.3f}s watchdog"
                    ) from exc
                raise PlaybackError(f"ROUTE_FAILED: output stream failed：{exc}") from exc
        finally:
            watchdog_done.set()
            watchdog.join(timeout=1.0)
            with self._stream_lock:
                if self._stream is stream:
                    self._stream = None
        with callback_lock:
            frames_written = int(callback_state["offset"])
            first_audio_at = callback_state["first_audio_at"]
            underrun_count = int(callback_state["underrun_count"])
            callback_error = callback_state["callback_error"]
            completed = bool(callback_state["completed"])
        if cancel_event.is_set():
            raise PlaybackCancelled("playback cancelled")
        if watchdog_fired.is_set() or not finished.is_set():
            raise PlaybackError(
                f"PLAYBACK_TIMEOUT: output callback exceeded {watchdog_timeout:.3f}s watchdog"
            )
        if callback_error is not None:
            raise PlaybackError(f"ROUTE_FAILED: output callback failed：{callback_error}") from callback_error
        if not completed or frames_written < len(rendered):
            raise PlaybackError("ROUTE_FAILED: output callback finished before all frames were rendered")
        return PlaybackResult(
            duration_seconds=(len(rendered) / float(rendered_sample_rate)),
            output_name=route["output"],
            host_api=route["host_api"],
            frames_written=frames_written,
            route_status="WAITING",
            playback_verified=False,
            stopped=stopped,
            first_audio_at=first_audio_at,
            underrun_count=underrun_count,
            source_sample_rate=source_sample_rate,
            source_channels=source_channels,
            rendered_sample_rate=rendered_sample_rate,
            rendered_channels=rendered_channels,
        )


class NullPlayback:
    """測試用 playback；明示不代表實際 audio route。"""

    def __init__(self, *, seconds: float = 0.0) -> None:
        self.seconds = max(0.0, float(seconds))
        self.calls: list[dict] = []
        self.stop_calls = 0

    def stop(self) -> None:
        self.stop_calls += 1

    def play(self, audio_path: Path, route: dict[str, str], cancel_event: Event) -> PlaybackResult:
        route = resolve_route(route)
        self.calls.append({"audio_path": str(audio_path), "route": dict(route)})
        deadline = time.monotonic() + self.seconds
        while time.monotonic() < deadline:
            if cancel_event.is_set():
                raise PlaybackCancelled("fake playback cancelled")
            time.sleep(min(0.005, max(0.0, deadline - time.monotonic())))
        return PlaybackResult(
            duration_seconds=self.seconds,
            output_name=route["output"],
            host_api=route["host_api"],
            frames_written=1,
            route_status="WAITING",
            playback_verified=False,
            first_audio_at=datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            underrun_count=0,
        )


__all__ = [
    "PlaybackCancelled",
    "PlaybackError",
    "PlaybackResult",
    "NullPlayback",
    "SoundDevicePlayback",
    "resolve_route",
]
