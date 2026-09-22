"""以 Voicemeeter Remote API 與實際 WASAPI capture 檢查 B1 路由。

這個工具只讀取 Voicemeeter 參數與電平，不會寫入 B1、Mute、Gain，
也不會修改 Windows 預設音訊裝置。它同時播放合成音到 Voicemeeter
Input、錄取 Voicemeeter Out B1，並保存 API 內部 level meter 的觀測值，
用來區分「按鈕設定正確」與「實際訊號真的穿過 B1」兩種證據。
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import sounddevice as sd
import soundfile as sf


DEFAULT_DLL_CANDIDATES = (
    Path(r"C:\Program Files\VB\Voicemeeter\VoicemeeterRemote64.dll"),
    Path(r"C:\Program Files (x86)\VB\Voicemeeter\VoicemeeterRemote64.dll"),
)
SAMPLE_RATE = 48_000
CHANNELS = 2
LEVEL_TYPES = (0, 1)
LEVEL_CHANNELS = range(32)


def find_wasapi_device(fragment: str, *, output: bool) -> int:
    """以 endpoint 名稱找 WASAPI 裝置，不依賴今天的整體索引。"""

    devices = sd.query_devices()
    hostapis = sd.query_hostapis()
    for index, device in enumerate(devices):
        host_name = hostapis[device["hostapi"]]["name"]
        channel_count = device["max_output_channels"] if output else device["max_input_channels"]
        if host_name == "Windows WASAPI" and fragment.lower() in device["name"].lower() and channel_count > 0:
            return index
    direction = "output" if output else "input"
    raise RuntimeError(f"找不到 Windows WASAPI {direction} endpoint: {fragment}")


def resolve_dll(explicit: Path | None) -> Path:
    """優先使用明確 DLL；否則只搜尋 Voicemeeter 官方安裝位置。"""

    candidates = (explicit,) if explicit else DEFAULT_DLL_CANDIDATES
    for candidate in candidates:
        if candidate and candidate.is_file():
            return candidate
    searched = ", ".join(str(path) for path in candidates if path)
    raise FileNotFoundError(f"找不到 VoicemeeterRemote64.dll；已搜尋: {searched}")


class VoicemeeterRemote:
    """ctypes 封裝；只暴露本工具需要的唯讀 API。"""

    def __init__(self, dll_path: Path) -> None:
        self.dll_path = dll_path
        self.dll = ctypes.WinDLL(str(dll_path))
        self._login = self._function("VBVMR_Login", [], ctypes.c_long)
        self._logout = self._function("VBVMR_Logout", [], ctypes.c_long)
        self._get_type = self._function(
            "VBVMR_GetVoicemeeterType",
            [ctypes.POINTER(ctypes.c_long)],
            ctypes.c_long,
        )
        self._get_parameter = self._function(
            "VBVMR_GetParameterFloat",
            [ctypes.c_char_p, ctypes.POINTER(ctypes.c_float)],
            ctypes.c_long,
        )
        self._get_level = self._function(
            "VBVMR_GetLevel",
            [ctypes.c_long, ctypes.c_long, ctypes.POINTER(ctypes.c_float)],
            ctypes.c_long,
        )
        self.login_code = int(self._login())
        if self.login_code < 0:
            raise RuntimeError(f"VBVMR_Login 失敗: {self.login_code}")

    def _function(self, name: str, argtypes: list[object], restype: object):
        function = getattr(self.dll, name)
        function.argtypes = argtypes
        function.restype = restype
        return function

    def close(self) -> None:
        self._logout()

    def get_type(self) -> tuple[int, int]:
        value = ctypes.c_long()
        result = int(self._get_type(ctypes.byref(value)))
        return result, int(value.value)

    def get_parameter(self, name: str) -> tuple[int, float | None]:
        value = ctypes.c_float()
        result = int(self._get_parameter(name.encode("ascii"), ctypes.byref(value)))
        return result, float(value.value) if result >= 0 else None

    def get_level(self, level_type: int, channel: int) -> tuple[int, float | None]:
        value = ctypes.c_float()
        result = int(self._get_level(level_type, channel, ctypes.byref(value)))
        return result, float(value.value) if result >= 0 else None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_parameters(api: VoicemeeterRemote) -> dict[str, object]:
    """保存目前實際設定；不呼叫任何 SetParameter 或 Command API。"""

    names = [
        *(f"Strip[{index}].B1" for index in range(3)),
        "Strip[2].Mute",
        "Strip[2].Gain",
        "Bus[1].Mute",
        "Bus[1].Gain",
    ]
    result: dict[str, object] = {}
    for name in names:
        error, value = api.get_parameter(name)
        result[name] = {"return_code": error, "value": value}
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only Voicemeeter B1 route and loopback check.")
    parser.add_argument("--seconds", type=float, default=3.0)
    parser.add_argument("--output-fragment", default="Voicemeeter Input")
    parser.add_argument("--input-fragment", default="Voicemeeter Out B1")
    parser.add_argument("--api-dll", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=Path("artifacts/voicemeeter-b1-route-check.wav"))
    parser.add_argument("--report", type=Path, default=None)
    args = parser.parse_args()

    frames = int(args.seconds * SAMPLE_RATE)
    tone = np.sin(2 * np.pi * 440 * np.arange(frames) / SAMPLE_RATE).astype(np.float32)
    tone *= np.linspace(0.0, 0.8, frames, dtype=np.float32)
    tone *= np.linspace(0.8, 0.0, frames, dtype=np.float32)
    output_data = np.repeat(tone[:, None], CHANNELS, axis=1)
    captured = np.zeros_like(output_data)
    out_cursor = 0
    in_cursor = 0
    stream_error: str | None = None
    api: VoicemeeterRemote | None = None
    api_error: str | None = None
    vm_type: int | None = None
    parameters: dict[str, object] = {}
    level_maxima = {
        str(level_type): {str(channel): 0.0 for channel in LEVEL_CHANNELS}
        for level_type in LEVEL_TYPES
    }
    level_return_codes = {
        str(level_type): {str(channel): None for channel in LEVEL_CHANNELS}
        for level_type in LEVEL_TYPES
    }

    try:
        api = VoicemeeterRemote(resolve_dll(args.api_dll))
        type_result, vm_type = api.get_type()
        if type_result < 0:
            raise RuntimeError(f"VBVMR_GetVoicemeeterType 失敗: {type_result}")
        parameters = inspect_parameters(api)
    except Exception as error:  # pragma: no cover - host-specific DLL/API state
        api_error = repr(error)

    try:
        output_device = find_wasapi_device(args.output_fragment, output=True)
        input_device = find_wasapi_device(args.input_fragment, output=False)
        wasapi = sd.WasapiSettings(exclusive=False)
    except Exception as error:  # pragma: no cover - host-specific endpoint state
        output_device = None
        input_device = None
        stream_error = repr(error)

    def output_callback(outdata, callback_frames, _time, _status):
        nonlocal out_cursor
        end = min(out_cursor + callback_frames, frames)
        count = end - out_cursor
        outdata[:] = 0
        if count > 0:
            outdata[:count] = output_data[out_cursor:end]
        out_cursor = end

    def input_callback(indata, callback_frames, _time, _status):
        nonlocal in_cursor
        end = min(in_cursor + callback_frames, frames)
        count = end - in_cursor
        if count > 0:
            captured[in_cursor:end] = indata[:count, :CHANNELS]
        in_cursor = end

    if stream_error is None and api_error is None:
        print(f"output_device={output_device}: {args.output_fragment}")
        print(f"input_device={input_device}: {args.input_fragment}")
        print(f"voicemeeter_type={vm_type}; sample_rate={SAMPLE_RATE}; seconds={args.seconds}")
        try:
            with sd.OutputStream(
                device=output_device,
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                blocksize=960,
                callback=output_callback,
                extra_settings=wasapi,
            ), sd.InputStream(
                device=input_device,
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                blocksize=960,
                callback=input_callback,
                extra_settings=wasapi,
            ):
                deadline = time.monotonic() + args.seconds + 0.5
                while time.monotonic() < deadline:
                    # API level meter 是診斷證據，不以單次輪詢結果判定；取整段最大值。
                    for level_type in LEVEL_TYPES:
                        for channel in LEVEL_CHANNELS:
                            error, value = api.get_level(level_type, channel)
                            level_return_codes[str(level_type)][str(channel)] = error
                            if value is not None:
                                level_maxima[str(level_type)][str(channel)] = max(
                                    level_maxima[str(level_type)][str(channel)], value
                                )
                    time.sleep(0.02)
        except Exception as error:  # pragma: no cover - device contention is host-specific
            stream_error = repr(error)
    elif api_error:
        print(f"api_error={api_error}")
    else:
        print(f"stream_error={stream_error}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    sf.write(args.out, captured, SAMPLE_RATE, subtype="PCM_16")
    rms = float(np.sqrt(np.mean(captured**2)))
    peak = float(np.max(np.abs(captured)))
    expected_frames = int(frames * 0.8)
    capture_pass = in_cursor >= expected_frames and rms >= 0.01 and stream_error is None
    status = "PASS" if capture_pass and api_error is None else "WAITING"
    if api_error and "找不到 VoicemeeterRemote" in api_error:
        status = "BLOCKED"
    report_path = args.report or args.out.with_suffix(".json")
    report = {
        "test": "voicemeeter-b1-read-only-route-check",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "output_fragment": args.output_fragment,
        "input_fragment": args.input_fragment,
        "sample_rate": SAMPLE_RATE,
        "channels": CHANNELS,
        "requested_seconds": args.seconds,
        "requested_frames": frames,
        "captured_frames": in_cursor,
        "minimum_captured_frames": expected_frames,
        "rms": rms,
        "peak": peak,
        "wav_path": str(args.out.resolve()),
        "wav_sha256": sha256_file(args.out),
        "status": status,
        "api_error": api_error,
        "stream_error": stream_error,
        "voicemeeter_type": vm_type,
        "parameters": parameters,
        "level_maxima": {
            level_type: {
                channel: value
                for channel, value in channels.items()
                if value > 0.000001
            }
            for level_type, channels in level_maxima.items()
        },
        "level_return_codes": level_return_codes,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if api is not None:
        api.close()

    nonzero_levels = sum(len(values) for values in report["level_maxima"].values())
    print(f"captured_frames={in_cursor}; rms={rms:.6f}; peak={peak:.6f}; nonzero_api_levels={nonzero_levels}")
    print(f"report={report_path}; wav_sha256={report['wav_sha256']}; status={status}")
    if status == "PASS":
        print("RESULT=PASS: Voicemeeter Input → B1 → Voicemeeter Out B1 已收到合成音。")
        return 0
    if status == "BLOCKED":
        print("RESULT=BLOCKED: 無法連線 Voicemeeter Remote API，未宣稱路由已通過。")
        return 2
    print("RESULT=WAITING: API/端點可檢查，但 B1 capture 尚未收到足夠的合成音。")
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
