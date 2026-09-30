"""CosyVoice2/Breeze TTS generation adapters。

兩個 adapter 都只產生 WAV；播放由 :mod:`playback` 獨立處理。現有 runner
是 non-streaming，所以 ``supports_streaming_tts`` 明確固定為 False。
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
import wave
import copy
import uuid
from dataclasses import dataclass
from pathlib import Path
from threading import Event, RLock
from typing import Any, Mapping

from .wsl_job import WslJob, WslJobError, to_wsl_path


def copy_readiness(value: Mapping[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(dict(value))


class GenerationError(RuntimeError):
    """TTS runner 失敗或 assets 不完整。"""


class GenerationCancelled(GenerationError):
    """generation 收到 stop/interrupt。"""


@dataclass(frozen=True)
class GenerationResult:
    audio_path: Path
    metrics: dict[str, Any]
    evidence: dict[str, Any]


def _digest_file(path: Path, *, full_limit: int | None = 8 * 1024 * 1024) -> tuple[str, str]:
    """回傳完整或明示模式的 digest；model evidence 會傳 None 做完整 hash。"""

    size = path.stat().st_size
    digest = hashlib.sha256()
    if full_limit is None or size <= full_limit:
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest(), "full"
    with path.open("rb") as stream:
        digest.update(stream.read(1024 * 1024))
        stream.seek(max(0, size - 1024 * 1024))
        digest.update(stream.read(1024 * 1024))
    return digest.hexdigest(), "head_tail"


def _load_runner_manifest(output_path: Path) -> dict[str, Any]:
    """讀取 runner 與 output WAV 同名的 JSON evidence。"""

    manifest_path = output_path.with_suffix(".json")
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"path": str(manifest_path), "status": "MISSING"}
    except (OSError, json.JSONDecodeError) as exc:
        return {"path": str(manifest_path), "status": "INVALID", "error": str(exc)}
    if not isinstance(payload, dict):
        return {"path": str(manifest_path), "status": "INVALID", "error": "manifest must be object"}
    return {"path": str(manifest_path), "status": "PRESENT", "manifest": payload}


def model_fingerprint(root: Path, engine_id: str, manifest: Mapping[str, Any]) -> dict[str, Any]:
    """以 paths、size、mtime 與 hash 產生可追溯的 model fingerprint。

    這裡不把「path exists」誤寫成 ready：每一筆 evidence 同時列出 file size、
    hash mode/hash 與 aggregate fingerprint；model paths 以完整 SHA-256 計算。
    """

    entries: list[dict[str, Any]] = []
    model_paths = manifest.get("modelPaths") or [
        rel for rel in manifest.get("requiredPaths", []) if str(rel).replace("\\", "/").startswith("models/")
    ]
    for rel in model_paths:
        path = root / str(rel)
        try:
            if path.is_dir():
                candidates = sorted(
                    p
                    for p in path.rglob("*")
                    if p.is_file() and ".cache" not in p.parts
                )
            elif path.is_file():
                candidates = [path]
            else:
                entries.append({"path": str(rel), "exists": False})
                continue
        except OSError as exc:
            entries.append({"path": str(rel), "exists": False, "error": str(exc)})
            continue
        for item in candidates:
            stat = item.stat()
            file_hash, hash_mode = _digest_file(item, full_limit=None)
            entry = {
                "path": str(item.relative_to(root)).replace("\\", "/"),
                "exists": True,
                "bytes": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
                "hash_mode": hash_mode,
            }
            if hash_mode == "full":
                entry["sha256"] = file_hash
            else:
                # 首尾 digest 不是完整內容 hash，欄位名稱刻意區分，避免把
                # performance fingerprint 誤報成官方完整 model SHA-256。
                entry["fingerprint_sha256"] = file_hash
            entries.append(entry)
    canonical = json.dumps(entries, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    aggregate = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return {
        "engine_id": engine_id,
        "aggregate_sha256": aggregate,
        "files": entries,
        "hash_policy": "full SHA-256 for every file under modelPaths; cached by size+mtime",
    }


def _readiness(root: Path, engine_id: str, manifest: Mapping[str, Any], distro: str = "Ubuntu") -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    paths: list[dict[str, Any]] = []
    for rel in manifest.get("requiredPaths", []):
        path = root / str(rel)
        normalized_rel = str(rel).replace("\\", "/")
        is_wsl_python = path.name == "python" and normalized_rel.startswith("tools/venvs/")
        error_code: str | None = None
        error_message: str | None = None
        if is_wsl_python:
            # 先 probe WSL，不能先呼叫 pathlib.exists()：Linux symlink 會在
            # Windows 端觸發 WinError 1920。
            try:
                probe = subprocess.run(
                    ["wsl.exe", "-d", distro, "--", "test", "-x", to_wsl_path(path)],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                    # WSL first invocation may initialise the distro/binfmt and
                    # takes several seconds on this Windows host. A short
                    # timeout would be a false MODEL_NOT_FOUND.
                    timeout=15,
                )
                exists = probe.returncode == 0
            except subprocess.TimeoutExpired as exc:
                exists = False
                error_code = "ENV_PROBE_TIMEOUT"
                error_message = str(exc)
            except OSError as exc:
                exists = False
                error_code = "ENV_UNAVAILABLE"
                error_message = str(exc)
        else:
            try:
                exists = path.is_file() if path.suffix else path.exists()
                if path.name in {"python", "python.exe"} or path.suffix:
                    exists = path.is_file()
            except OSError as exc:
                exists = False
                error_message = str(exc)
        paths.append({"path": str(rel), "exists": exists})
        if not exists:
            item = {"code": error_code or "MODEL_NOT_FOUND", "path": str(rel)}
            if error_message:
                item["message"] = error_message
            errors.append(item)
    return {
        "engine_id": engine_id,
        "preflight_valid": not errors,
        "state": "VALIDATED" if not errors else "WAITING",
        "errors": errors,
        "supports_streaming_tts": False,
        "paths": paths,
    }


def _profile_reference(request: Mapping[str, Any], engine_id: str) -> dict[str, str]:
    snapshot = request.get("profile_snapshot")
    if not isinstance(snapshot, dict):
        raise GenerationError("REFERENCE_INVALID: request 缺少 profile snapshot")
    references = snapshot.get("references")
    if not isinstance(references, dict):
        raise GenerationError("REFERENCE_INVALID: voice profile 沒有 references")
    reference = references.get(engine_id)
    if not isinstance(reference, dict):
        raise GenerationError(f"REFERENCE_INVALID: profile 不支援 {engine_id}")
    audio = reference.get("audio_path")
    text = reference.get("text_path")
    if not isinstance(audio, str) or not audio.strip():
        raise GenerationError("REFERENCE_INVALID: reference audio path 不可為空")
    if not isinstance(text, str) or not text.strip():
        raise GenerationError("REFERENCE_INVALID: reference text path 不可為空")
    return {"audio_path": audio, "text_path": text}


def _write_text_file(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


class BaseGenerationAdapter:
    supports_streaming_tts = False

    def __init__(self, root: Path, engine_id: str, distro: str = "Ubuntu") -> None:
        self.root = root.resolve()
        self.engine_id = engine_id
        self.distro = distro
        self._active_job: WslJob | None = None
        self._job_lock = RLock()
        self._fingerprint_cache: tuple[tuple[Any, ...], dict[str, Any]] | None = None
        self._readiness_cache: tuple[float, dict[str, Any]] | None = None

    def manifest(self) -> dict[str, Any]:
        path = self.root / "contracts" / "engines" / f"{self.engine_id}.json"
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise GenerationError(f"MODEL_NOT_FOUND: 無法讀取 engine manifest：{path}") from exc

    def readiness(self) -> dict[str, Any]:
        now = time.monotonic()
        # WSL cold-start probe can take several seconds; cache long enough for
        # UI polling and command ACKs without spawning a probe each snapshot.
        if self._readiness_cache is not None and now - self._readiness_cache[0] < 30.0:
            return copy_readiness(self._readiness_cache[1])
        value = _readiness(self.root, self.engine_id, self.manifest(), self.distro)
        self._readiness_cache = (now, value)
        return copy_readiness(value)

    def cancel(self, reason: str = "cancelled") -> dict[str, Any] | None:
        with self._job_lock:
            job = self._active_job
        return job.cancel(reason) if job is not None else None

    def _wait_job(self, job: WslJob, cancel_event: Event) -> dict[str, Any]:
        while job.poll() is None:
            if cancel_event.is_set():
                job.cancel("generation_cancelled")
                break
            time.sleep(0.03)
        try:
            code = job.wait(timeout=5 if cancel_event.is_set() else 15)
        except subprocess.TimeoutExpired as exc:
            raise GenerationCancelled("generation cancellation timeout; pid audit retained") from exc
        audit = job.audit()
        if cancel_event.is_set():
            raise GenerationCancelled(json.dumps({"returncode": code, "pid_audit": audit}, ensure_ascii=False))
        if code not in (0, None):
            raise GenerationError(
                f"BACKEND_CRASH: {self.engine_id} runner exit={code}; "
                f"stdout={job.stdout_path}; stderr={job.stderr_path}"
            )
        return audit

    def _cached_model_fingerprint(self, manifest: Mapping[str, Any]) -> dict[str, Any]:
        """同一模型 snapshot 只計算一次 fingerprint；stat 變更會失效。"""

        signature: list[tuple[str, int, int]] = []
        model_paths = manifest.get("modelPaths") or [
            rel for rel in manifest.get("requiredPaths", [])
            if str(rel).replace("\\", "/").startswith("models/")
        ]
        for rel in model_paths:
            path = (self.root / str(rel)).resolve()
            try:
                if path.is_dir():
                    paths = sorted(p for p in path.rglob("*") if p.is_file() and ".cache" not in p.parts)
                elif path.is_file():
                    paths = [path]
                else:
                    paths = []
            except OSError:
                paths = []
            for item in paths:
                try:
                    stat = item.stat()
                    signature.append((str(item), stat.st_size, stat.st_mtime_ns))
                except OSError:
                    continue
        key = tuple(signature)
        if self._fingerprint_cache is not None and self._fingerprint_cache[0] == key:
            return self._fingerprint_cache[1]
        value = model_fingerprint(self.root, self.engine_id, manifest)
        self._fingerprint_cache = (key, value)
        return value

    @staticmethod
    def _ensure_job_stopped(job: WslJob, cancel_event: Event) -> dict[str, Any]:
        """所有 exception path 都 bounded cleanup，避免 orphan runner。"""

        if job.poll() is None:
            cancel_event.set()
            try:
                job.cancel("adapter_finally_cleanup")
            except Exception:
                pass
            try:
                job.wait(timeout=3)
            except Exception:
                pass
        return job.audit()

    def _finish_result(
        self,
        *,
        request: Mapping[str, Any],
        output_path: Path,
        started: float,
        audit: dict[str, Any],
        runner: dict[str, Any],
    ) -> GenerationResult:
        if not output_path.is_file() or output_path.stat().st_size <= 44:
            raise GenerationError(f"BACKEND_CRASH: runner 沒有產生非空 WAV：{output_path}")
        try:
            with wave.open(str(output_path), "rb") as stream:
                frames = stream.getnframes()
                sample_rate = stream.getframerate()
                channels = stream.getnchannels()
        except (OSError, wave.Error) as exc:
            raise GenerationError(f"BACKEND_CRASH: generated WAV 無法讀取：{exc}") from exc
        if frames <= 0 or sample_rate <= 0 or channels <= 0:
            raise GenerationError("BACKEND_CRASH: generated WAV frame metadata 無效")
        elapsed = time.perf_counter() - started
        manifest = self.manifest()
        fingerprint = self._cached_model_fingerprint(manifest)
        output_hash = _digest_file(output_path, full_limit=None)[0]
        runner_manifest = _load_runner_manifest(output_path)
        metrics = {
            "generation_latency_ms": round(elapsed * 1000, 3),
            "output_seconds": round(frames / sample_rate, 6),
            "sample_rate": sample_rate,
            "channels": channels,
            "first_audio_at": None,
            "supports_streaming_tts": False,
        }
        evidence = {
            "engine_id": self.engine_id,
            "request_id": request.get("id"),
            "runner": runner,
            "model_fingerprint": fingerprint,
            "output": {
                "path": str(output_path),
                "bytes": output_path.stat().st_size,
                "sha256": output_hash,
            },
            # tools/*-infer.py writes runtime/device/output_validation/RTF to
            # this adjacent manifest; retain it verbatim for each request.
            "runner_manifest": runner_manifest,
            "pid_audit": audit,
            "stdout": audit.get("stdout"),
            "stderr": audit.get("stderr"),
        }
        return GenerationResult(audio_path=output_path, metrics=metrics, evidence=evidence)


class ResidentGenerationAdapter(BaseGenerationAdapter):
    """同一 speech service 內保留一個受 WSL process-group 管理的模型。"""

    def __init__(self, root: Path, engine_id: str, distro: str = "Ubuntu") -> None:
        super().__init__(root, engine_id, distro)
        self._warm_job: WslJob | None = None
        self._mailbox: Path | None = None

    def _worker_command(self, mailbox: Path) -> list[str]:
        if self.engine_id == "cosyvoice":
            environment = [
                "-u", "CUDA_VISIBLE_DEVICES",
                f"PYTHONPATH={to_wsl_path(self.root / 'tools/external/CosyVoice')}:{to_wsl_path(self.root / 'tools/external/CosyVoice/third_party/Matcha-TTS')}",
                "HF_HUB_OFFLINE=1", "TRANSFORMERS_OFFLINE=1",
            ]
            python = self.root / "tools/venvs/cosyvoice-wsl/bin/python"
            model = self.root / "models/speech-reconstruction/cosyvoice"
        else:
            environment = [
                f"PYTHONPATH={to_wsl_path(self.root / 'tools/external/breeze-tts')}",
                f"PATH={to_wsl_path(self.root / 'artifacts/sox-local/usr/bin')}:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
                f"LD_LIBRARY_PATH={to_wsl_path(self.root / 'artifacts/sox-local/usr/lib/x86_64-linux-gnu')}:/usr/lib/x86_64-linux-gnu:/lib/x86_64-linux-gnu",
                "HF_HUB_OFFLINE=1", "TRANSFORMERS_OFFLINE=1",
            ]
            python = self.root / "tools/venvs/breeze-tts-wsl/bin/python"
            model = self.root / "models/speech-reconstruction/breeze-tts-2"
        return ["env", *environment, to_wsl_path(python), "-u",
                to_wsl_path(self.root / "tools/tts-resident-worker.py"),
                "--engine", self.engine_id, "--model-dir", to_wsl_path(model),
                "--mailbox", to_wsl_path(mailbox)]

    def _request_payload(self, request: Mapping[str, Any], output_path: Path, job_dir: Path) -> dict[str, Any]:
        reference = _profile_reference(request, self.engine_id)
        for key in ("audio_path", "text_path"):
            if not (self.root / reference[key]).is_file():
                raise GenerationError(f"REFERENCE_INVALID: 找不到 {reference[key]}")
        text_file = job_dir / "tts-text.txt"
        _write_text_file(text_file, str(request["text"]))
        payload: dict[str, Any] = {
            "id": str(request["id"]), "output": to_wsl_path(output_path),
            "text_file": to_wsl_path(text_file),
        }
        if self.engine_id == "cosyvoice":
            payload.update({
                "prompt_audio": to_wsl_path(self.root / reference["audio_path"]),
                "prompt_text_file": to_wsl_path(self.root / reference["text_path"]),
            })
        else:
            metadata = request.get("metadata") if isinstance(request.get("metadata"), dict) else {}
            cfg_scale = metadata.get("cfg_scale", 1.0)
            seed = metadata.get("seed", 42)
            attention = metadata.get("attention_implementation", "eager")
            if not isinstance(cfg_scale, (int, float)) or isinstance(cfg_scale, bool):
                raise GenerationError("PARAMETER_INVALID: cfg_scale 必須是數字")
            if not isinstance(seed, int) or isinstance(seed, bool):
                raise GenerationError("PARAMETER_INVALID: seed 必須是整數")
            if attention not in ("eager", "flash_attention_2"):
                raise GenerationError("PARAMETER_INVALID: attention_implementation 不合法")
            payload.update({
                "reference_audio": to_wsl_path(self.root / reference["audio_path"]),
                "reference_text_file": to_wsl_path(self.root / reference["text_path"]),
                "instruction": metadata.get("instruction") if isinstance(metadata.get("instruction"), str) else "",
                "cfg_scale": float(cfg_scale), "seed": seed,
                "fast_all": bool(metadata.get("fast_all", False)),
                "attention_implementation": attention,
            })
        return payload

    def _ensure_worker(self, job_dir: Path) -> tuple[WslJob, Path]:
        with self._job_lock:
            if self._warm_job is not None and self._warm_job.poll() is None and self._mailbox is not None:
                return self._warm_job, self._mailbox
            if self._warm_job is not None:
                self._warm_job.wait(timeout=2)
            mailbox = job_dir.parent.parent / "workers" / self.engine_id / uuid.uuid4().hex
            (mailbox / "requests").mkdir(parents=True)
            (mailbox / "results").mkdir(parents=True)
            job = WslJob(root=self.root, job_dir=mailbox, command=self._worker_command(mailbox), distro=self.distro)
            self._warm_job = job
            self._mailbox = mailbox
            self._active_job = job
            try:
                job.start()
            except Exception:
                self._warm_job = None
                self._mailbox = None
                self._active_job = None
                raise
            return job, mailbox

    def generate(self, request: Mapping[str, Any], output_path: Path, job_dir: Path, cancel_event: Event) -> GenerationResult:
        readiness = self.readiness()
        if not readiness["preflight_valid"]:
            raise GenerationError("MODEL_NOT_FOUND: " + ", ".join(item["path"] for item in readiness["errors"]))
        payload = self._request_payload(request, output_path, job_dir)
        started = time.perf_counter()
        job, mailbox = self._ensure_worker(job_dir)
        request_id = str(request["id"])
        result_path = mailbox / "results" / f"{request_id}.json"
        pending_path = mailbox / "requests" / f"{request_id}.json"
        temporary = pending_path.with_suffix(".tmp")
        try:
            temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            os.replace(temporary, pending_path)
            deadline = time.monotonic() + 900
            while not result_path.is_file():
                if cancel_event.is_set():
                    audit = job.cancel("generation_cancelled")
                    raise GenerationCancelled(json.dumps({"pid_audit": audit}, ensure_ascii=False))
                if job.poll() is not None:
                    raise GenerationError(f"BACKEND_CRASH: {self.engine_id} resident worker exit={job.poll()}; stderr={job.stderr_path}")
                if time.monotonic() >= deadline:
                    job.cancel("generation_timeout")
                    raise GenerationError(f"BACKEND_TIMEOUT: {self.engine_id} 生成超過 15 分鐘；stderr={job.stderr_path}")
                time.sleep(0.05)
            result = json.loads(result_path.read_text(encoding="utf-8"))
            if cancel_event.is_set():
                audit = job.cancel("generation_cancelled")
                raise GenerationCancelled(json.dumps({"pid_audit": audit}, ensure_ascii=False))
            if result.get("status") != "PASS" or result.get("id") != request_id:
                raise GenerationError(f"BACKEND_CRASH: {self.engine_id} resident request failed: {result.get('error')}; stderr={job.stderr_path}")
            return self._finish_result(
                request=request, output_path=output_path, started=started, audit=job.audit(),
                runner={"kind": "resident_wsl_worker", "script": "tools/tts-resident-worker.py",
                        "supports_streaming_tts": False},
            )
        finally:
            with self._job_lock:
                self._active_job = None
            if cancel_event.is_set() and job.poll() is None:
                job.cancel("adapter_finally_cleanup")
                try:
                    job.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    pass
                with self._job_lock:
                    if self._warm_job is job:
                        self._warm_job = None
                        self._mailbox = None

    def close(self) -> dict[str, Any] | None:
        with self._job_lock:
            job = self._warm_job
            self._warm_job = None
            self._mailbox = None
            self._active_job = None
        if job is None:
            return None
        if job.poll() is None:
            audit = job.cancel("resident_worker_close")
        else:
            audit = job.audit()
        try:
            job.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
        return audit


class CosyVoiceAdapter(ResidentGenerationAdapter):
    def __init__(self, root: Path, distro: str = "Ubuntu") -> None:
        super().__init__(root, "cosyvoice", distro)


class BreezeAdapter(ResidentGenerationAdapter):
    def __init__(self, root: Path, distro: str = "Ubuntu") -> None:
        super().__init__(root, "breeze", distro)


def default_adapters(root: Path, distro: str = "Ubuntu") -> dict[str, BaseGenerationAdapter]:
    return {
        "cosyvoice": CosyVoiceAdapter(root, distro=distro),
        "breeze": BreezeAdapter(root, distro=distro),
    }


__all__ = [
    "BaseGenerationAdapter",
    "BreezeAdapter",
    "CosyVoiceAdapter",
    "GenerationCancelled",
    "GenerationError",
    "GenerationResult",
    "default_adapters",
    "model_fingerprint",
]
