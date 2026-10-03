"""JSONL control bridge。只編排現有 runner；stdout 僅輸出協定，PCM 不經 IPC。"""
from __future__ import annotations
import argparse
import os
import json
import math
import subprocess
import sys
import threading
import uuid
import wave
from pathlib import Path

OUTPUT_LOCK = threading.Lock()


def emit(event: dict) -> None:
    with OUTPUT_LOCK:
        print(json.dumps(event, ensure_ascii=False), flush=True)


def state(engine: str, value: str, reason: str) -> None:
    emit(dict(type="state", engine_id=engine, value=value, reason=reason, audio_verified=False))


def read_wav(value: str) -> Path:
    path = Path(value).resolve()
    if not path.is_file():
        raise ValueError(f"REFERENCE_INVALID: 找不到 WAV：{path}")
    with wave.open(str(path), "rb") as stream:
        if stream.getnframes() == 0 or stream.getnchannels() not in (1, 2):
            raise ValueError("REFERENCE_INVALID: WAV 為空或不支援聲道")
    return path


def validate(root: Path, engine: str, request: dict) -> tuple[dict, dict]:
    if not isinstance(request, dict):
        raise ValueError("PARAMETER_INVALID: request 必須是 object")
    for key in ("reference", "source", "input", "output", "host_api"):
        if key in request and not isinstance(request[key], str):
            raise ValueError(f"PARAMETER_INVALID: {key} 必須是字串")
    if engine not in ("seed-vc", "meanvc2", "xvc", "rvc"):
        raise ValueError("BACKEND_UNAVAILABLE: 此輪尚未實作該 Engine")
    manifest = json.loads((root / "contracts/engines" / f"{engine}.json").read_text(encoding="utf-8"))
    missing = [p for p in manifest["requiredPaths"] if not (root / p).is_file()]
    if missing:
        raise ValueError("MODEL_NOT_FOUND: " + ", ".join(missing))
    values = {p["name"]: p["default"] for p in manifest["parameters"]}
    supplied = request.get("parameters", {})
    if not isinstance(supplied, dict) or set(supplied) - set(values):
        raise ValueError("PARAMETER_INVALID: 未知參數")
    values.update(supplied)
    # 以 manifest 驗證型別、有限數、步進；UI 的輸入驗證不取代此邊界。
    for p in manifest["parameters"]:
        value = values[p["name"]]
        if p["type"] == "number":
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"PARAMETER_INVALID: {p['name']} 必須是有限數字")
            if not p["min"] <= value <= p["max"] or abs((value-p["min"])/p["step"]-round((value-p["min"])/p["step"])) > 1e-6:
                raise ValueError(f"PARAMETER_INVALID: {p['name']} 超出範圍或步進")
        elif p["type"] == "select" and value not in p["options"]:
            raise ValueError(f"PARAMETER_INVALID: {p['name']} 選項不合法")
    if engine != "rvc":
        read_wav(request.get("reference", ""))
    if engine == "rvc" and values["source_mode"] == "file":
        read_wav(request.get("source", ""))
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from services.engines.postfx import validate_postfx
    from services.engines.noise_reduction import validate_noise_reduction
    from services.engines.rvc_runtime import endpoint
    from services.tts.playback import resolve_route
    validate_postfx(request.get("postfx"))
    validate_noise_reduction(request.get("noise_reduction"))
    import sounddevice as sd
    endpoint(sd, request.get("output", ""), request.get("host_api", ""), "output", 2)
    if engine != "rvc" or values["source_mode"] == "microphone":
        endpoint(sd, request.get("input", ""), request.get("host_api", ""), "input", 1)
        if "cable output" in request["input"].lower() and ("cable input" in request["output"].lower() or "cable in 16ch" in request["output"].lower()):
            raise ValueError("ROUTE_FAILED: 請勿將同一條 CABLE 的 Output 回送 Input")
        if "cable out 16ch" in request["input"].lower() and "cable in 16ch" in request["output"].lower():
            raise ValueError("ROUTE_FAILED: 請勿將同一條 CABLE 16ch 回送")
    route = resolve_route({"output": request["output"], "host_api": request["host_api"], "monitor": request.get("monitor", {"enabled": False})})
    if route.get("monitor", {}).get("enabled"):
        endpoint(sd, route["monitor"]["output"], route["monitor"]["host_api"], "output", 2)
    if engine == "rvc":
        try:
            from .rvc_runtime import registered_model, endpoint
        except ImportError:
            from rvc_runtime import registered_model, endpoint
        registered_model(root, values["model_id"])
        if values["crossfade"] > values["chunk"]:
            raise ValueError("PARAMETER_INVALID: crossfade 不得大於 chunk")
    if engine == "seed-vc":
        if any(not request.get(k, "").strip() for k in ("input", "output", "host_api")):
            raise ValueError("DEVICE_NOT_FOUND: 請填同一 Host API 的完整 input/output 名稱；launcher 會核對唯一端點")
        if values["crossfade_length"] > values["block_time"]:
            raise ValueError("PARAMETER_INVALID: crossfade 不得大於 block time")
        if values["extra_time_ce"] < values["extra_time"]:
            raise ValueError("PARAMETER_INVALID: Content encoder context 不得小於 DiT context")
    if engine == "meanvc2" and values["model"] == "120ms":
        for p in ("meanvc2_120ms_40ms.safetensors", "fastu2pp_160ms.pt"):
            if not (root / "models/meanvc2" / p).is_file():
                raise ValueError("MODEL_NOT_FOUND: " + p)
    if engine == "xvc":
        if values["current"] <= 0:
            raise ValueError("PARAMETER_INVALID: Desktop 麥克風模式 current 必須大於 0；offline 請使用 CLI")
        if any(values[name] % 80 for name in ("current", "chunk", "future")):
            raise ValueError("PARAMETER_INVALID: X-VC codec 視窗必須對齊 80ms")
        if values["smooth"] > values["current"] or values["current"] + values["future"] + values["smooth"] > values["chunk"]:
            raise ValueError("PARAMETER_INVALID: X-VC streaming 視窗不合法")
    return manifest, values


def build_command(root: Path, engine: str, request: dict, values: dict, run: Path) -> list[str]:
    if engine == "rvc":
        settings = run / "rvc-request.json"
        normalized = {**request, "parameters": values}
        if values["source_mode"] == "file":
            normalized["source"] = str(Path(request["source"]).resolve())
        settings.write_text(json.dumps(normalized, ensure_ascii=False), encoding="utf-8")
        return [str(root / ".venv/Scripts/python.exe"), "-u", "-B", str(root / "services/engines/rvc_runtime.py"),
                "--root", str(root), "--request", str(settings), "--output-dir", str(run)]
    python = str(root / f"tools/venvs/{engine}/Scripts/python.exe")
    settings = run / "stream-request.json"
    settings.write_text(json.dumps({**request, "parameters": values}, ensure_ascii=False), encoding="utf-8")
    return [python, "-u", "-B", str(root / "services/engines/stream_runtime.py"),
            "--root", str(root), "--engine", engine, "--request", str(settings), "--output-dir", str(run)]


def serve(root: Path, engine: str, request: dict, validate_only: bool = False) -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from services.engines.progress import Progress
    progress = Progress()
    emit(dict(type="progress", progress=progress.snapshot()))
    state(engine, "VALIDATING", "檔案與參數預檢；不代表模型載入或音訊驗證")
    try:
        manifest, values = validate(root, engine, request)
    except (ValueError, RuntimeError, OSError, wave.Error) as exc:
        progress.set("error")
        emit(dict(type="progress", progress=progress.snapshot(False)))
        emit(dict(type="error", code=str(exc).split(":")[0], message=str(exc)))
        state(engine, "ERROR", str(exc))
        return 2
    emit(dict(type="validation", valid=True, engine_id=engine, scope="assets_parameters_devices_only", audio_verified=False))
    if validate_only:
        state(engine, "OFFLINE", "預檢 PASS；模型尚未載入、音訊 WAITING")
        return 0
    run = root / "artifacts/desktop/runs" / uuid.uuid4().hex
    run.mkdir(parents=True)
    emit(dict(type="artifact", path=str(run), adapter=manifest["adapter"]))
    child: subprocess.Popen | None = None
    stopping = threading.Event()

    def observe(proc: subprocess.Popen) -> None:
        for line in proc.stdout:
            emit(dict(type="log", stream="backend", message=line.rstrip()))
            if line.startswith('{'):
                try:
                    runtime = json.loads(line)
                    if runtime.get("type") in ("rvc_runtime", "vc_runtime") and not stopping.is_set():
                        phase = runtime.get("phase") or {"LOADING": "model_load", "READY": "audio_open", "RUNNING": "running", "ERROR": "error", "OFFLINE": "completed"}.get(runtime["value"])
                        if phase:
                            progress.set(phase, load_seconds=runtime.get("load_seconds"))
                        emit(dict(type="progress", progress=progress.snapshot(proc.poll() is None)))
                        state(engine, runtime["value"], runtime["reason"])
                    elif runtime.get("type") in ("metrics", "runtime") and not stopping.is_set():
                        emit(runtime)
                except (ValueError, KeyError):
                    pass
            if "CUDA out of memory" in line or "CUDA error: out of memory" in line:
                progress.set("error")
                emit(dict(type="progress", progress=progress.snapshot(proc.poll() is None)))
                emit(dict(type="error", code="CUDA_OOM", message="GPU 記憶體不足；請停止其他模型後重試"))
                state(engine, "ERROR", "CUDA_OOM")
        code = proc.wait()
        emit(dict(type="process_exit", code=code))
        if not stopping.is_set():
            progress.set("error" if code else "completed")
            emit(dict(type="progress", progress=progress.snapshot(False)))
            if code:
                emit(dict(type="error", code="BACKEND_CRASH", message=f"現有 runner 結束：{code}；請查看 backend log"))
                state(engine, "ERROR", f"runner exit {code}")
            else:
                state(engine, "OFFLINE", "runner 已完成；exit 0 不代表音訊 PASS，請核對 run-evidence；Stop 可釋放 service")

    observer = None
    def heartbeat():
        while not stopping.wait(1):
            if child is not None:
                emit(dict(type="progress", progress=progress.snapshot(child.poll() is None)))
    threading.Thread(target=heartbeat, daemon=True, name="vc-progress").start()
    try:
        for line in sys.stdin:
            try:
                cmd = json.loads(line)
                if not isinstance(cmd, dict):
                    raise ValueError("command 必須是 JSON object")
                if cmd.get("command") == "start":
                    if child is not None:
                        emit(dict(type="error", code="COMMAND_INVALID", message="請停止後重新啟動新的 service"))
                        continue
                    state(engine, "LOADING", "載入模型、預熱並開啟音訊串流")
                    child = subprocess.Popen(build_command(root, engine, request, values, run), cwd=root,
                        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                        text=True, encoding="utf-8", errors="replace", shell=False,
                        env={**os.environ, "PYTHONIOENCODING": "utf-8"})
                    emit(dict(type="process_started", pid=child.pid, adapter=manifest["adapter"]))
                    observer = threading.Thread(target=observe, args=(child,), daemon=True)
                    observer.start()
                elif cmd.get("command") == "stop":
                    break
                elif cmd.get("command") == "status":
                    emit(dict(type="process", pid=child.pid if child else None, alive=child is not None and child.poll() is None))
                elif cmd.get("command") == "set_parameter":
                    if cmd.get("name") not in values:
                        raise ValueError("未知參數")
                    emit(dict(type="restart_required", parameter=cmd["name"]))
                else:
                    raise ValueError("未知命令")
            except (ValueError, OSError) as exc:
                emit(dict(type="error", code="COMMAND_INVALID", message=str(exc)))
                if isinstance(exc, OSError):
                    state(engine, "ERROR", str(exc))
    finally:
        stopping.set()
        progress.set("cancelled")
        state(engine, "STOPPING", "釋放程序；Rust Job Object 負責清除完整程序樹")
        if child is not None and child.poll() is None:
            if child.stdin is not None:
                try:
                    child.stdin.write("stop\n")
                    child.stdin.flush()
                    child.wait(timeout=2)
                except (OSError, subprocess.TimeoutExpired):
                    child.terminate()
                    child.wait(timeout=1)
            else:
                child.terminate()
                child.wait(timeout=5)
        if observer:
            observer.join(timeout=2)
        emit(dict(type="progress", progress=progress.snapshot(False)))
        state(engine, "OFFLINE", "service 已停止；Job cleanup 由 App 確認")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--engine", required=True)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    return serve(args.root.resolve(), args.engine, json.loads(args.request.read_text(encoding="utf-8")), args.validate)


if __name__ == "__main__":
    raise SystemExit(main())
