"""JSONL control bridge。只編排現有 runner；stdout 僅輸出協定，PCM 不經 IPC。"""
from __future__ import annotations
import argparse
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
    if engine not in ("seed-vc", "meanvc2", "xvc"):
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
    read_wav(request.get("reference", ""))
    if engine != "seed-vc":
        read_wav(request.get("source", ""))
    if engine == "seed-vc":
        if any(not request.get(k, "").strip() for k in ("input", "output", "host_api")):
            raise ValueError("DEVICE_NOT_FOUND: 請填同一 Host API 的完整 input/output 名稱；launcher 會核對唯一端點")
        if values["crossfade_length"] > values["block_time"]:
            raise ValueError("PARAMETER_INVALID: crossfade 不得大於 block time")
        import sounddevice as sd
        apis = sd.query_hostapis()
        devices = sd.query_devices()
        for name, channel in (("input", "max_input_channels"), ("output", "max_output_channels")):
            matching = [d for d in devices if d["name"] == request[name] and d[channel] > 0
                        and apis[d["hostapi"]]["name"] == request["host_api"]]
            if len(matching) != 1:
                raise ValueError(f"DEVICE_NOT_FOUND: {request[name]} 在 {request['host_api']} 不是唯一的 {name} 端點")
    if engine == "meanvc2" and values["model"] == "120ms":
        for p in ("meanvc2_120ms_40ms.safetensors", "fastu2pp_160ms.pt"):
            if not (root / "models/meanvc2" / p).is_file():
                raise ValueError("MODEL_NOT_FOUND: " + p)
    if engine == "xvc" and values["current"] > 0:
        if values["smooth"] > values["current"] or values["current"] + values["future"] + values["smooth"] > values["chunk"]:
            raise ValueError("PARAMETER_INVALID: X-VC streaming 視窗不合法")
    return manifest, values


def build_command(root: Path, engine: str, request: dict, values: dict, run: Path) -> list[str]:
    python = str(root / f"tools/venvs/{engine}/Scripts/python.exe")
    if engine == "seed-vc":
        settings = run / "seed-settings.json"
        settings.write_text(json.dumps(values), encoding="utf-8")
        return [str(root / "tools/external/powershell/pwsh.exe"), "-NoProfile", "-File",
                str(root / "tools/seed-vc-gui-run.ps1"), "-Python", python,
                "-SessionRoot", str(run / "gui-session"), "-SettingsFile", str(settings),
                "-ReferenceWav", str(Path(request["reference"]).resolve()),
                "-HostApi", request["host_api"], "-InputDeviceName", request["input"], "-OutputDeviceName", request["output"]]
    args = [python, "-u", str(root / f"tools/{engine}-run.py"), "--source", str(Path(request["source"]).resolve()),
            "--target", str(Path(request["reference"]).resolve())]
    if engine == "meanvc2":
        return args + ["--output", str(run / "output.wav"), "--model", values["model"]]
    args += ["--output-dir", str(run)]
    for name in ("current", "chunk", "future", "smooth"):
        args += ["--" + name, str(values[name])]
    return args


def serve(root: Path, engine: str, request: dict, validate_only: bool = False) -> int:
    state(engine, "VALIDATING", "檔案與參數預檢；不代表模型載入或音訊驗證")
    try:
        manifest, values = validate(root, engine, request)
    except (ValueError, OSError, wave.Error) as exc:
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
            if "CUDA out of memory" in line or "CUDA error: out of memory" in line:
                emit(dict(type="error", code="CUDA_OOM", message="GPU 記憶體不足；請停止其他模型後重試"))
                state(engine, "ERROR", "CUDA_OOM")
            if engine == "meanvc2" and line.startswith("Model load seconds:") and not stopping.is_set():
                state(engine, "READY", "現有 runner 已回報模型載入；音訊 WAITING")
                state(engine, "RUNNING", "現有 runner 已回報模型載入，正在 WAV 轉換；mic/output WAITING")
        code = proc.wait()
        emit(dict(type="process_exit", code=code))
        if not stopping.is_set():
            if code:
                emit(dict(type="error", code="BACKEND_CRASH", message=f"現有 runner 結束：{code}；請查看 backend log"))
                state(engine, "ERROR", f"runner exit {code}")
            else:
                state(engine, "OFFLINE", "runner 已完成；exit 0 不代表音訊 PASS，請核對 run-evidence；Stop 可釋放 service")

    observer = None
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
                    state(engine, "LOADING", "啟動現有 runner；等待模型／GUI；TEMPORARY 不自動開 stream" if engine == "seed-vc" else "載入 WAV runner")
                    child = subprocess.Popen(build_command(root, engine, request, values, run), cwd=root,
                        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                        text=True, encoding="utf-8", errors="replace", shell=False)
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
        state(engine, "STOPPING", "釋放程序；Rust Job Object 負責清除完整程序樹")
        if child is not None and child.poll() is None:
            child.terminate()
            child.wait(timeout=5)
        if observer:
            observer.join(timeout=2)
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
