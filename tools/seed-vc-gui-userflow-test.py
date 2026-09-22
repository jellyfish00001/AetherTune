"""Seed-VC 官方 GUI 的本機 user-flow / audio-path 測試。

這是專案測試工具，不修改第三方 Seed-VC 原始碼。測試會：
1. 開啟官方 real-time-gui.py。
2. 透過 GUI event path 套用 reference、裝置與即時參數。
3. 用實際 PortAudio duplex stream 開啟使用者選定的輸入／輸出裝置。
4. 在 GUI callback 邊界注入男聲 WAV，保存 GUI callback 的處理後輸出。

它驗證的是「GUI 啟動 + GUI 設定 + PortAudio stream + Seed-VC 推論 + 輸出擷取」；
輸入聲音以 deterministic male WAV 注入 callback，因此可重現且不依賴虛擬麥克風
的 MME 輸入權限。它不等同於人工聽測，也不會把輸出送進 Discord。所有輸出只寫入
artifacts。
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import runpy
import subprocess
import sys
import threading
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = PROJECT_ROOT / "dataset" / "reference-voices" / "voice-male-m1.wav"
DEFAULT_OUT = PROJECT_ROOT / "artifacts" / "seed-vc" / "gui-userflow"
GUI_PATH = PROJECT_ROOT / "tools" / "external" / "seed-vc" / "real-time-gui.py"
CHECKPOINT_PATH = (
    PROJECT_ROOT
    / "models"
    / "seed-vc"
    / "checkpoints"
    / "offline-v1"
    / "DiT_seed_v2_uvit_whisper_small_wavenet_bigvgan_pruned.pth"
)
REALTIME_CONFIG_PATH = (
    PROJECT_ROOT
    / "tools"
    / "external"
    / "seed-vc"
    / "configs"
    / "presets"
    / "config_dit_mel_seed_uvit_whisper_small_wavenet.yml"
)
HF_CACHE_PATH = GUI_PATH.parent / "checkpoints" / "hf_cache"

REFERENCE_CASES = {
    "female-young-f004": PROJECT_ROOT / "dataset" / "reference-voices" / "female-young-f004.wav",
    "female-sister-f003": PROJECT_ROOT / "dataset" / "reference-voices" / "female-sister-f003.wav",
    "female-warm-f005": PROJECT_ROOT / "dataset" / "reference-voices" / "female-warm-f005.wav",
    "female-fresh-f006": PROJECT_ROOT / "dataset" / "reference-voices" / "female-fresh-f006.wav",
}

# 保留已驗證過的低延遲設定；輸出裝置使用 VB-CABLE 虛擬端點，避免測試聲音直出實體喇叭。
USERFLOW_SETTINGS = {
    "sg_hostapi": "MME",
    "sg_wasapi_exclusive": False,
    "sg_input_device": "麥克風 (HyperX QuadCast S)",
    # 輸出寫入虛擬端點，避免測試音訊直接播放到實體喇叭；名稱同樣是 MME 截短值。
    "sg_output_device": "CABLE Input (VB-Audio Virtual C",
    "sr_model": True,
    "sr_device": False,
    "diffusion_steps": 10.0,
    "inference_cfg_rate": 0.7,
    "max_prompt_length": 3.0,
    "block_time": 0.30,
    "crossfade_length": 0.04,
    "extra_time_ce": 5.0,
    "extra_time": 0.5,
    "extra_time_right": 0.02,
    "vc": True,
    "im": False,
}

PLAYBACK_SR = 22050
PLAYBACK_SECONDS = 5.0
# 官方 GUI 第一次 callback 會觸發 VAD／CUDA／vocoder warm-up；目前實測約
# 11.2 秒。多保留一段只給首個 case 的 capture window，避免把「輸出尚未
# 形成」誤判成模型無輸出；這段 warm-up 仍必須在 LIVE latency 報告中分開記錄。
FIRST_CASE_STARTUP_GRACE_SECONDS = 15.0

# GUI／音訊依賴延後載入，讓 --help 與 --preflight 不會被 Tcl/Tk 啟動失敗
# 阻擋。這些全域值只在實際 user-flow 前由 _load_runtime_dependencies() 設定。
sg = None
librosa = None
np = None
sd = None
sf = None
_ORIGINAL_WINDOW = None
_ORIGINAL_STREAM = None
_CAPTURES: dict[str, dict[str, object]] = {}
_CURRENT_LABEL = ""
_SOURCE_PATH = DEFAULT_SOURCE
_OUTPUT_ROOT = DEFAULT_OUT


# FunASR import 時只用 ffmpeg 做可選能力探針；本測試所有輸入都是 WAV，且系統
# 的 ffmpeg 執行檔目前受 Windows 權限阻擋，因此只對這個探針回報已存在。
# 不攔截其他 subprocess，也不改變正式 Seed-VC runtime。
_ORIGINAL_CHECK_OUTPUT = subprocess.check_output


def _check_output_for_funasr_probe(command, *args, **kwargs):
    if isinstance(command, (list, tuple)) and command and str(command[0]).lower() == "ffmpeg":
        return b"ffmpeg version local-wav-test"
    return _ORIGINAL_CHECK_OUTPUT(command, *args, **kwargs)


def _save_capture(label: str, input_chunks: list[np.ndarray], output_chunks: list[np.ndarray], sample_rate: int) -> None:
    """保存 GUI 實際 callback 收到與送出的音訊，供後續訊號檢查。"""

    case_dir = _OUTPUT_ROOT / label
    case_dir.mkdir(parents=True, exist_ok=True)
    if input_chunks:
        sf.write(case_dir / "gui-input-injected-male.wav", np.concatenate(input_chunks, axis=0), sample_rate)
    if output_chunks:
        sf.write(case_dir / "gui-output-after-vc.wav", np.concatenate(output_chunks, axis=0), sample_rate)


class _RecordingStream:
    """保留真實 sounddevice.Stream，並在 callback 邊界注入可重現的男聲。"""

    def __init__(self, *args, **kwargs):
        self._input_chunks: list[np.ndarray] = []
        self._output_chunks: list[np.ndarray] = []
        self._sample_rate = int(kwargs.get("samplerate") or PLAYBACK_SR)
        self._label = _CURRENT_LABEL
        source, source_sr = sf.read(_SOURCE_PATH, always_2d=False)
        if source.ndim > 1:
            source = source.mean(axis=1)
        source = np.asarray(source, dtype=np.float32)
        if source_sr != self._sample_rate:
            source = librosa.resample(source, orig_sr=source_sr, target_sr=self._sample_rate)
        source = np.asarray(source, dtype=np.float32)
        peak = float(np.max(np.abs(source))) if source.size else 0.0
        if peak > 0.8:
            source = source * (0.8 / peak)
        self._source = source
        self._source_cursor = 0
        callback = kwargs["callback"]

        def wrapped_callback(indata, outdata, frames, times, status):
            # 讓官方 GUI callback 看到男聲輸入。每個 callback 會循環 source，
            # 因此不用依賴 VB-CABLE 的 input endpoint，也不會因 source 結束變成靜音。
            injected = np.zeros_like(indata)
            if self._source.size:
                remaining = int(frames)
                write_cursor = 0
                while remaining > 0:
                    available = min(remaining, len(self._source) - self._source_cursor)
                    chunk = self._source[self._source_cursor : self._source_cursor + available]
                    if injected.ndim == 1:
                        injected[write_cursor : write_cursor + available] = chunk
                    else:
                        injected[write_cursor : write_cursor + available, :] = chunk[:, None]
                    self._source_cursor = (self._source_cursor + available) % len(self._source)
                    write_cursor += available
                    remaining -= available
            self._input_chunks.append(np.array(injected, copy=True))
            callback(injected, outdata, frames, times, status)
            self._output_chunks.append(np.array(outdata, copy=True))

        kwargs["callback"] = wrapped_callback
        self._stream = _ORIGINAL_STREAM(*args, **kwargs)

    @property
    def latency(self):
        return self._stream.latency

    def start(self):
        return self._stream.start()

    def abort(self):
        return self._stream.abort()

    def close(self):
        try:
            return self._stream.close()
        finally:
            _save_capture(self._label, self._input_chunks, self._output_chunks, self._sample_rate)

    def __getattr__(self, name):
        return getattr(self._stream, name)


class _UserFlowWindowMixin:
    """在官方 GUI 的 start event 上套用使用者會填入的欄位。"""

    def __init__(self, *args, **kwargs):
        # 由 _load_runtime_dependencies() 動態混入官方 Window；保留官方的
        # class-level state（例如 NumOpenWindows），避免改變 GUI framework 的
        # lifecycle。唯讀 preflight 仍不會建立此 class。
        super().__init__(*args, **kwargs)
        self._pending_values: dict[str, object] | None = None
        if kwargs.get("finalize"):
            threading.Thread(target=self._drive_user_flow, name="seed-vc-gui-userflow", daemon=True).start()

    def read(self, *args, **kwargs):
        event, values = super().read(*args, **kwargs)
        if event == "start_vc" and self._pending_values is not None:
            desired = self._pending_values
            self._pending_values = None
            # 由主 GUI 執行緒更新 widget，再把同一份值交給官方 event_handler。
            for key, value in desired.items():
                try:
                    self[key].update(value=value)
                except Exception:
                    pass
                values[key] = value
        return event, values

    def _drive_user_flow(self) -> None:
        global _CURRENT_LABEL
        time.sleep(2.0)
        for label, reference in REFERENCE_CASES.items():
            _CURRENT_LABEL = label
            desired = dict(USERFLOW_SETTINGS)
            desired["reference_audio_path"] = str(reference)
            self._pending_values = desired
            print(f"USERFLOW configure label={label} reference={reference}", flush=True)
            self.write_event_value("start_vc", None)
            time.sleep(3.0)
            print(f"USERFLOW inject male source at GUI callback label={label}", flush=True)
            # Stream wrapper 會在這段期間持續把男聲注入官方 GUI callback。
            startup_grace = (
                FIRST_CASE_STARTUP_GRACE_SECONDS
                if label == next(iter(REFERENCE_CASES))
                else 1.0
            )
            time.sleep(PLAYBACK_SECONDS + startup_grace)
            self.write_event_value("stop_vc", None)
            time.sleep(1.5)
        print("USERFLOW close GUI", flush=True)
        self.write_event_value(sg.WIN_CLOSED, None)


def _load_runtime_dependencies() -> None:
    """載入實際 GUI／音訊依賴並安裝測試用 adapter。"""

    global sg, librosa, np, sd, sf, _ORIGINAL_WINDOW, _ORIGINAL_STREAM

    # 不在模組 import 階段載入 FreeSimpleGUI；其 import 會建立 Tcl/Tk，
    # 若系統 Python 的 Tcl runtime 損壞，應由 --preflight 回報 WAITING。
    sg = importlib.import_module("FreeSimpleGUI")
    librosa = importlib.import_module("librosa")
    np = importlib.import_module("numpy")
    sd = importlib.import_module("sounddevice")
    sf = importlib.import_module("soundfile")
    _ORIGINAL_WINDOW = sg.Window
    _ORIGINAL_STREAM = sd.Stream

    # FunASR import 時只用 ffmpeg 做可選能力探針；所有輸入都是 WAV，
    # 因此只隔離該探針，不攔截其他 subprocess，也不修改正式 runtime。
    subprocess.check_output = _check_output_for_funasr_probe
    try:
        funasr = importlib.import_module("funasr")
    finally:
        subprocess.check_output = _ORIGINAL_CHECK_OUTPUT

    original_automodel = funasr.AutoModel

    class _OfflineAutoModel(original_automodel):
        """避免已快取的 VAD 模型在 GUI 啟動時額外發起更新檢查。"""

        def __init__(self, *args, **kwargs):
            if kwargs.get("model") == "fsmn-vad":
                # ModelScope cache 內已有完整 VAD 模型；直接傳本機資料夾可避開
                # .mdl 更新標記的權限問題，仍由 FunASR 建立同一個 VAD pipeline。
                local_vad = (
                    Path.home()
                    / ".cache"
                    / "modelscope"
                    / "hub"
                    / "iic"
                    / "speech_fsmn_vad_zh-cn-16k-common-pytorch"
                )
                kwargs["model"] = str(local_vad)
                kwargs.pop("model_revision", None)
            kwargs.setdefault("disable_update", True)
            super().__init__(*args, **kwargs)

    funasr.AutoModel = _OfflineAutoModel
    sd.Stream = _RecordingStream

    # FreeSimpleGUI 需要從 Window class 讀取全域生命週期狀態；用多重繼承
    # 保留原 class 的 attributes/methods，再只覆寫測試需要的 read／driver。
    class _RuntimeUserFlowWindow(_UserFlowWindowMixin, _ORIGINAL_WINDOW):
        pass

    sg.Window = _RuntimeUserFlowWindow


def _preflight(source: Path) -> int:
    """只做唯讀資源、裝置與 GUI import 檢查，不開啟 stream 或建立音訊檔。"""

    resources = {
        "source": source,
        "gui": GUI_PATH,
        "checkpoint": CHECKPOINT_PATH,
        "realtime_config": REALTIME_CONFIG_PATH,
        "hf_cache": HF_CACHE_PATH,
        **REFERENCE_CASES,
    }
    resource_report = {}
    missing_resources = []
    for label, path in resources.items():
        exists = path.exists()
        is_file = path.is_file() if exists else False
        size = path.stat().st_size if is_file else 0
        resource_report[label] = {
            "path": str(path),
            "exists": exists,
            "is_file": is_file,
            "size": size,
        }
        if not exists or (label != "hf_cache" and (not is_file or size == 0)):
            missing_resources.append(label)

    device_report: dict[str, object] = {
        "status": "WAITING",
        "hostapis": [],
        "devices": [],
        "expected_hostapi": USERFLOW_SETTINGS["sg_hostapi"],
        "expected_input": USERFLOW_SETTINGS["sg_input_device"],
        "expected_output": USERFLOW_SETTINGS["sg_output_device"],
        "input_matches": [],
        "output_matches": [],
    }
    try:
        preflight_sd = importlib.import_module("sounddevice")
        hostapis = preflight_sd.query_hostapis()
        hostapi_names = [str(item.get("name", "")) for item in hostapis]
        device_report["hostapis"] = hostapi_names
        for index, device in enumerate(preflight_sd.query_devices()):
            hostapi_index = int(device.get("hostapi", -1))
            hostapi_name = hostapi_names[hostapi_index] if 0 <= hostapi_index < len(hostapi_names) else ""
            item = {
                "index": index,
                "name": str(device.get("name", "")),
                "hostapi": hostapi_name,
                "max_input_channels": int(device.get("max_input_channels", 0)),
                "max_output_channels": int(device.get("max_output_channels", 0)),
            }
            device_report["devices"].append(item)
            if (
                hostapi_name.casefold() == str(USERFLOW_SETTINGS["sg_hostapi"]).casefold()
                and str(USERFLOW_SETTINGS["sg_input_device"]).casefold() in item["name"].casefold()
                and item["max_input_channels"] > 0
            ):
                device_report["input_matches"].append(item)
            if (
                hostapi_name.casefold() == str(USERFLOW_SETTINGS["sg_hostapi"]).casefold()
                and str(USERFLOW_SETTINGS["sg_output_device"]).casefold() in item["name"].casefold()
                and item["max_output_channels"] > 0
            ):
                device_report["output_matches"].append(item)
        device_report["status"] = (
            "PASS"
            if device_report["input_matches"] and device_report["output_matches"]
            else "BLOCKED"
        )
    except Exception as exc:
        device_report["status"] = "BLOCKED"
        device_report["error_type"] = type(exc).__name__
        device_report["error"] = str(exc)

    try:
        importlib.import_module("FreeSimpleGUI")
        gui_report = {"status": "PASS", "module": "FreeSimpleGUI"}
    except Exception as exc:
        # Tcl/Tk 初始化問題屬環境 WAITING；這裡保留完整錯誤給修復／重跑使用，
        # 但不自行改寫 Python 安裝或下載第三方 runtime。
        gui_report = {
            "status": "WAITING",
            "module": "FreeSimpleGUI",
            "error_type": type(exc).__name__,
            "error": str(exc),
        }

    if missing_resources or device_report["status"] == "BLOCKED":
        status = "BLOCKED"
        exit_code = 2
    elif gui_report["status"] != "PASS":
        status = "WAITING"
        exit_code = 3
    else:
        status = "PASS"
        exit_code = 0
    report = {
        "status": status,
        "test": "official-seed-vc-gui-userflow-preflight",
        "read_only": True,
        "resources": resource_report,
        "missing_resources": missing_resources,
        "devices": device_report,
        "gui_dependency": gui_report,
        "next_step": (
            "修復或官方重裝 Python Tcl/Tk 後重跑 --preflight，再執行正式 GUI user-flow。"
            if gui_report["status"] != "PASS"
            else "可進入正式 GUI user-flow；正式結果仍需人工聽測與完整 live gate。"
        ),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    return exit_code


def _audio_metrics(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"exists": False}
    data, sr = sf.read(path, always_2d=False)
    if data.ndim > 1:
        data = data.mean(axis=1)
    data = np.asarray(data, dtype=np.float64)
    rms = float(np.sqrt(np.mean(data * data))) if data.size else 0.0
    return {
        "exists": True,
        "sample_rate": int(sr),
        "seconds": round(float(len(data) / sr), 3) if sr else 0.0,
        "finite": bool(np.isfinite(data).all()),
        "rms": rms,
        "peak": float(np.max(np.abs(data))) if data.size else 0.0,
        "sha256": __import__("hashlib").sha256(path.read_bytes()).hexdigest().upper(),
    }


def _audio_difference(input_path: Path, output_path: Path) -> dict[str, object]:
    """檢查 GUI 輸出不是輸入男聲的原樣回放。"""

    if not input_path.exists() or not output_path.exists():
        return {"compared": False}
    source, _ = sf.read(input_path, always_2d=False)
    converted, _ = sf.read(output_path, always_2d=False)
    source = np.asarray(source, dtype=np.float64)
    converted = np.asarray(converted, dtype=np.float64)
    if source.ndim > 1:
        source = source.mean(axis=1)
    if converted.ndim > 1:
        converted = converted.mean(axis=1)
    length = min(len(source), len(converted))
    if length == 0:
        return {"compared": False}
    source = source[:length]
    converted = converted[:length]
    difference_rms = float(np.sqrt(np.mean((source - converted) ** 2)))
    correlation = 0.0
    if np.std(source) > 0 and np.std(converted) > 0:
        correlation = float(np.corrcoef(source, converted)[0, 1])
    return {
        "compared": True,
        "samples_compared": int(length),
        "zero_lag_correlation": correlation,
        "difference_rms": difference_rms,
        "different_from_input": bool(difference_rms > 1e-4),
    }


def main() -> int:
    global _SOURCE_PATH, _OUTPUT_ROOT
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--preflight",
        action="store_true",
        help="只檢查檔案、PortAudio 裝置與 FreeSimpleGUI import，不啟動 GUI 或錄製音訊",
    )
    args = parser.parse_args()
    _SOURCE_PATH = args.source.resolve()
    if args.preflight:
        return _preflight(_SOURCE_PATH)

    _load_runtime_dependencies()
    _OUTPUT_ROOT = args.output.resolve()
    _OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    sys.path.insert(0, str(GUI_PATH.parent))
    # runpy 會沿用目前程序的 argv；先將測試工具自己的參數隔離，避免官方
    # argparse 把 --output 誤當成 real-time-gui.py 的參數。
    sys.argv = [
        str(GUI_PATH),
        "--checkpoint-path",
        str(CHECKPOINT_PATH),
        "--config-path",
        str(REALTIME_CONFIG_PATH),
        # 官方 real-time-gui.py 的 fp16 路徑在目前 checkpoint／CUDA runtime
        # 會讓 SOLA callback 混用 HalfTensor 與 FloatTensor；FP32 才是可連續
        # 啟動與輸出的穩定 user-flow 參數。
        "--fp16",
        "False",
        "--gpu",
        "0",
    ]
    original_cwd = Path.cwd()
    try:
        # 官方 hf_utils 使用相對的 ./checkpoints；保持與手動啟動官方 GUI 相同的 cwd。
        os.chdir(GUI_PATH.parent)
        # 所需模型已在專案的 checkpoints cache；避免每個 GUI cycle 都做遠端 HEAD。
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        os.environ["HF_HOME"] = str(HF_CACHE_PATH)
        os.environ["HF_HUB_CACHE"] = str(HF_CACHE_PATH)
        import huggingface_hub.constants as hf_constants

        # huggingface_hub 已在 FunASR import 時載入 constants，需同步更新記憶體中的
        # cache 路徑，讓 BigVGAN／Whisper 也能使用專案隨附的本機快取。
        hf_constants.HF_HUB_CACHE = str(HF_CACHE_PATH)
        hf_constants.HUGGINGFACE_HUB_CACHE = str(HF_CACHE_PATH)
        runpy.run_path(str(GUI_PATH), run_name="__main__")
    except SystemExit:
        pass
    finally:
        os.chdir(original_cwd)

    cases = {}
    for label in REFERENCE_CASES:
        case_dir = _OUTPUT_ROOT / label
        input_path = case_dir / "gui-input-injected-male.wav"
        output_path = case_dir / "gui-output-after-vc.wav"
        input_metrics = _audio_metrics(input_path)
        output_metrics = _audio_metrics(output_path)
        comparison = _audio_difference(input_path, output_path)
        output_pass = bool(
            output_metrics.get("exists")
            and output_metrics.get("finite")
            and float(output_metrics.get("rms", 0.0)) > 1e-4
            and float(output_metrics.get("seconds", 0.0)) > 0.5
            and comparison.get("different_from_input") is True
        )
        cases[label] = {
            "status": "PASS" if output_pass else "WAITING",
            "reference": str(REFERENCE_CASES[label]),
            "input": input_metrics,
            "output": output_metrics,
            "comparison": comparison,
        }

    report = {
        "status": "PASS" if all(v["status"] == "PASS" for v in cases.values()) else "WAITING",
        "test": "official-seed-vc-gui-userflow",
        "source": str(_SOURCE_PATH),
        "settings": USERFLOW_SETTINGS,
        "portaudio_output_device": USERFLOW_SETTINGS["sg_output_device"],
        "input_injection": "callback-injected deterministic male WAV",
        "first_case_startup_grace_seconds": FIRST_CASE_STARTUP_GRACE_SECONDS,
        "cases": cases,
    }
    report_path = _OUTPUT_ROOT / "gui-userflow-report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"USERFLOW report={report_path}", flush=True)
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
