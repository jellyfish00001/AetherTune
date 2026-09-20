"""FCPE (Fast-Context-based Pitch Extractor) 驗證腳本與推論探針。

驗證項目：
1. 專案環境 (torchfcpe + PyTorch CUDA) 是否可正常載入 FCPE 模型並以 GPU 提取音高。
2. 合成音（220Hz / 440Hz）音高提取精準度與推論耗時。
3. （選用）VCClient 即時變聲客戶端狀態、Slot 音高演算法配置與端對端即時 chunk 轉換測試。
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import torch


def write_result(path: Path, result: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def test_fcpe_cuda_synthetic(device: str = "cuda") -> dict[str, Any]:
    """使用合成音訊對 torchfcpe 執行 GPU 推論並驗證音高提取精度。"""
    import torchfcpe

    sr = 16000
    test_freq = 220.0
    duration = 1.0  # 1 秒

    t = torch.linspace(0, duration, int(sr * duration))
    wav = (0.5 * torch.sin(2 * 3.141592653589793 * test_freq * t)).unsqueeze(0).to(device)

    load_start = time.perf_counter()
    model = torchfcpe.spawn_bundled_infer_model(device=device)
    load_time_sec = time.perf_counter() - load_start

    infer_start = time.perf_counter()
    f0 = model.infer(wav, sr=sr, decoder_mode="local_argmax", threshold=0.006)
    torch.cuda.synchronize()
    infer_time_ms = (time.perf_counter() - infer_start) * 1000

    f0_np = f0.squeeze().cpu().numpy()
    voiced = f0_np[f0_np > 10.0]
    median_f0 = float(np.median(voiced)) if len(voiced) > 0 else 0.0
    error_hz = abs(median_f0 - test_freq)

    return {
        "device": device,
        "model_loaded": model is not None,
        "model_load_time_sec": round(load_time_sec, 4),
        "infer_time_ms": round(infer_time_ms, 2),
        "target_frequency_hz": test_freq,
        "extracted_median_f0_hz": round(median_f0, 4),
        "error_hz": round(error_hz, 4),
        "total_frames": int(len(f0_np)),
        "voiced_frames": int(len(voiced)),
        "accuracy_passed": bool(error_hz < 1.0),
    }


def test_vcclient_api(url: str = "http://127.0.0.1:18000") -> dict[str, Any]:
    """檢測 VCClient Web API 狀態、Slot 設定以及即時 chunk 轉換測試。"""
    import io
    import requests

    status: dict[str, Any] = {
        "url": url,
        "reachable": False,
        "fcpe_supported": False,
        "slots_with_fcpe": [],
        "convert_chunk_tested": False,
        "convert_chunk_status": None,
    }

    try:
        r = requests.get(f"{url}/openapi.json", timeout=3)
        if r.status_code == 200:
            status["reachable"] = True
            openapi = r.json()
            estimator_enum = (
                openapi.get("components", {})
                .get("schemas", {})
                .get("PitchEstimatorInfo", {})
                .get("properties", {})
                .get("pitch_estimator_type", {})
                .get("enum", [])
            )
            status["fcpe_supported"] = "fcpe" in estimator_enum

        # 檢查 slots
        slots_r = requests.get(f"{url}/api/slot-manager/slots", timeout=3)
        if slots_r.status_code == 200:
            slots = slots_r.json()
            fcpe_slots = []
            for s in slots:
                if s.get("pitch_estimator") == "fcpe":
                    fcpe_slots.append(
                        {
                            "slot_index": s.get("slot_index"),
                            "name": s.get("name"),
                            "model_file": s.get("model_file"),
                            "pitch_estimator": s.get("pitch_estimator"),
                        }
                    )
            status["slots_with_fcpe"] = fcpe_slots

        # 測試即時 chunk 轉換
        sr = 48000
        chunk_dur = 0.2
        t = np.linspace(0, chunk_dur, int(sr * chunk_dur), endpoint=False, dtype=np.float32)
        test_audio = (0.2 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)

        buf = io.BytesIO(test_audio.tobytes())
        files = {"waveform": ("test.raw", buf, "application/octet-stream")}
        conv_r = requests.post(
            f"{url}/api/voice-changer/convert_chunk", files=files, timeout=5
        )
        status["convert_chunk_tested"] = True
        status["convert_chunk_status"] = conv_r.status_code
        status["convert_chunk_out_bytes"] = len(conv_r.content) if conv_r.status_code == 200 else 0

    except Exception as e:
        status["error"] = str(e)

    return status


def main() -> int:
    parser = argparse.ArgumentParser(description="FCPE Pitch Extractor Probe for AetherTune")
    parser.add_argument(
        "--artifact",
        type=Path,
        default=Path("artifacts/fcpe-probe.json"),
        help="輸出 JSON 檔案路徑",
    )
    parser.add_argument(
        "--device",
        default="cuda" if torch.cuda.is_available() else "cpu",
        help="推論裝置 (cuda 或 cpu)",
    )
    parser.add_argument(
        "--vcclient-url",
        default="http://127.0.0.1:18000",
        help="VCClient API 網址",
    )
    parser.add_argument(
        "--skip-vcclient",
        action="store_true",
        help="略過 VCClient 即時探針",
    )
    args = parser.parse_args()

    started_at = datetime.now(timezone.utc).isoformat()
    probe_result: dict[str, Any] = {
        "started_at_utc": started_at,
        "torch_version": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "N/A",
    }

    # 1. 測試 FCPE 本地 CUDA 合成推論
    try:
        synth_res = test_fcpe_cuda_synthetic(device=args.device)
        probe_result["synthetic_test"] = synth_res
        synthetic_passed = synth_res.get("accuracy_passed", False)
    except Exception as e:
        probe_result["synthetic_test"] = {"status": "error", "error": str(e)}
        synthetic_passed = False

    # 2. 測試 VCClient API
    if not args.skip_vcclient:
        probe_result["vcclient_status"] = test_vcclient_api(url=args.vcclient_url)

    finished_at = datetime.now(timezone.utc).isoformat()
    probe_result["finished_at_utc"] = finished_at
    probe_result["status"] = "PASS" if synthetic_passed else "FAIL"

    write_result(args.artifact, probe_result)
    print(f"FCPE probe finished: {probe_result['status']}")
    print(f"Artifact written to: {args.artifact}")
    return 0 if synthetic_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
