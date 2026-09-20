"""用合成音驗證 VB-CABLE 的播放端到錄音端資料流。

這個測試不使用實體麥克風，也不改 Windows 預設裝置；它只在指定的
WASAPI 端點播放 440 Hz 正弦波，再把 CABLE Output 錄到 artifacts/。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import sounddevice as sd
import soundfile as sf


def find_wasapi_device(fragment: str, *, output: bool) -> int:
    """以穩定的 endpoint 名稱找 WASAPI 裝置，不依賴今天的整體索引。"""

    devices = sd.query_devices()
    hostapis = sd.query_hostapis()
    for index, device in enumerate(devices):
        host_name = hostapis[device["hostapi"]]["name"]
        channel_count = device["max_output_channels"] if output else device["max_input_channels"]
        if host_name == "Windows WASAPI" and fragment.lower() in device["name"].lower() and channel_count > 0:
            return index
    direction = "output" if output else "input"
    raise RuntimeError(f"找不到 Windows WASAPI {direction} endpoint: {fragment}")


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Record a synthetic tone through VB-CABLE.")
    parser.add_argument("--seconds", type=float, default=3.0)
    parser.add_argument("--out", type=Path, default=Path("artifacts/virtual-cable-loopback.wav"))
    parser.add_argument("--output-fragment", default="CABLE Input", help="播放端名稱片段")
    parser.add_argument("--input-fragment", default="CABLE Output", help="錄音端名稱片段")
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="測試證據 JSON；未指定時使用 WAV 同名 .json",
    )
    args = parser.parse_args()

    sample_rate = 48_000
    channels = 2
    frames = int(args.seconds * sample_rate)
    tone = np.sin(2 * np.pi * 440 * np.arange(frames) / sample_rate).astype(np.float32)
    tone *= np.linspace(0.0, 0.8, frames, dtype=np.float32)
    tone *= np.linspace(0.8, 0.0, frames, dtype=np.float32)
    output_data = np.repeat(tone[:, None], channels, axis=1)
    captured = np.zeros_like(output_data)
    out_cursor = 0
    in_cursor = 0

    output_device: int | None = None
    input_device: int | None = None
    stream_error: str | None = None
    try:
        # 裝置查找也必須納入本次測試的錯誤範圍；找不到端點時仍要覆寫
        # WAV/JSON，避免 verifier 繼續引用上一次的 PASS 證據。
        output_device = find_wasapi_device(args.output_fragment, output=True)
        input_device = find_wasapi_device(args.input_fragment, output=False)
        wasapi = sd.WasapiSettings(exclusive=False)
    except Exception as error:  # pragma: no cover - endpoint inventory is host-specific
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
            captured[in_cursor:end] = indata[:count, :channels]
        in_cursor = end

    if stream_error is None:
        print(f"output_device={output_device}: {args.output_fragment}")
        print(f"input_device={input_device}: {args.input_fragment}")
    print(f"sample_rate={sample_rate}; seconds={args.seconds}")

    if stream_error is None:
        try:
            # 同時開啟兩端，避免先播完才開始錄而錯過資料。
            with sd.OutputStream(
                device=output_device,
                samplerate=sample_rate,
                channels=channels,
                blocksize=960,
                callback=output_callback,
                extra_settings=wasapi,
            ), sd.InputStream(
                device=input_device,
                samplerate=sample_rate,
                channels=channels,
                blocksize=960,
                callback=input_callback,
                extra_settings=wasapi,
            ):
                time.sleep(args.seconds + 0.5)
        except Exception as error:  # pragma: no cover - device contention is host-specific
            # 即使 PortAudio 無法開啟，也要留下可追溯 JSON，而不是讓 verifier
            # 只看到一個沒有測試結果的舊 WAV。
            stream_error = repr(error)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    sf.write(args.out, captured, sample_rate, subtype="PCM_16")
    rms = float(np.sqrt(np.mean(captured**2)))
    peak = float(np.max(np.abs(captured)))
    expected_frames = int(frames * 0.8)
    passed = in_cursor >= expected_frames and rms >= 0.01
    report_path = args.report or args.out.with_suffix(".json")
    report = {
        "test": "wasapi-synthetic-loopback",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "output_fragment": args.output_fragment,
        "input_fragment": args.input_fragment,
        "sample_rate": sample_rate,
        "channels": channels,
        "requested_seconds": args.seconds,
        "requested_frames": frames,
        "captured_frames": in_cursor,
        "minimum_captured_frames": expected_frames,
        "rms": rms,
        "peak": peak,
        "wav_path": str(args.out.resolve()),
        "wav_sha256": sha256_file(args.out),
        "status": "PASS" if passed and stream_error is None else "FAIL",
    }
    if stream_error:
        report["error"] = stream_error
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"captured_frames={in_cursor}; rms={rms:.6f}; peak={peak:.6f}; output={args.out}")
    print(f"report={report_path}; wav_sha256={report['wav_sha256']}")
    if not passed or stream_error:
        print("RESULT=FAIL: 錄音端沒有收到足夠的合成音，請檢查端點方向、Voicemeeter bus routing 或其他程式占用裝置。")
        return 1
    print("RESULT=PASS: VB-CABLE 播放端到錄音端 loopback 成功。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
