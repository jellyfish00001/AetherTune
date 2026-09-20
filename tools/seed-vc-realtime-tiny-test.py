"""Seed-VC realtime-tiny 的 headless GPU streaming benchmark。

這個工具重用官方 real-time-gui.py 的 model loader/custom_infer，避免啟動
PySimpleGUI/PortAudio；因此能驗證 GPU 模型、串流 block 與輸出，但不冒充
真實麥克風／聲卡端到端證據。
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Callable

import librosa
import numpy as np
import soundfile as sf
import torch


def load_official_module(repo: Path):
    # 官方檔名含連字號，使用 importlib 載入；cwd 必須保持在 Seed-VC repo，
    # 讓官方 config、modules 與 HuggingFace cache 路徑保持原本契約。
    sys.path.insert(0, str(repo))
    spec = importlib.util.spec_from_file_location("seed_vc_realtime_gui", repo / "real-time-gui.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("無法載入官方 real-time-gui.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def find_local_hf_asset(repo: Path, repo_id: str, filename: str) -> Path | None:
    """先找專案內已下載的 HF asset，避免測試時無預警連線。"""
    direct = repo / filename
    if direct.is_file():
        return direct
    cache_root = repo / "checkpoints" / f"models--{repo_id.replace('/', '--')}" / "snapshots"
    if cache_root.is_dir():
        for snapshot in sorted(cache_root.iterdir(), reverse=True):
            candidate = snapshot / filename
            if candidate.is_file():
                return candidate
    return None


def make_asset_loader(repo: Path, allow_network: bool) -> Callable:
    """把官方 loader 的網路依賴變成可審計的 local-first 行為。"""
    from hf_utils import load_custom_model_from_hf as upstream_loader

    def load_asset(repo_id: str, model_filename: str = "pytorch_model.bin", config_filename: str | None = None):
        model_path = find_local_hf_asset(repo, repo_id, model_filename)
        if model_path is None:
            if not allow_network:
                raise FileNotFoundError(
                    f"找不到本機 Seed-VC asset：repo={repo_id} file={model_filename}；"
                    "請先準備 checkpoints cache，或明確傳入 --allow-network-assets"
                )
            model_path = Path(upstream_loader(repo_id, model_filename, None))
        if config_filename is None:
            return str(model_path)
        config_path = find_local_hf_asset(repo, repo_id, config_filename)
        if config_path is None:
            if not allow_network:
                raise FileNotFoundError(
                    f"找不到本機 Seed-VC config：repo={repo_id} file={config_filename}"
                )
            config_path = Path(upstream_loader(repo_id, config_filename, None))
        return str(model_path), str(config_path)

    return load_asset


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--repo", default="tools/external/seed-vc")
    parser.add_argument("--checkpoint", default="models/seed-vc/checkpoints/realtime-tiny/DiT_uvit_tat_xlsr_ema.pth")
    parser.add_argument("--config", default="tools/external/seed-vc/configs/presets/config_dit_mel_seed_uvit_xlsr_tiny.yml")
    parser.add_argument("--output-dir", default="artifacts/seed-vc/realtime-tiny")
    parser.add_argument("--blocks", type=int, default=3)
    parser.add_argument("--block-time", type=float, default=0.30)
    parser.add_argument("--diffusion-steps", type=int, default=10)
    parser.add_argument("--fp16", action="store_true")
    parser.add_argument(
        "--allow-network-assets",
        action="store_true",
        help="本機 assets 不足時允許官方 Hugging Face downloader；預設離線可重跑。",
    )
    args = parser.parse_args()

    root = Path.cwd()
    repo = (root / args.repo).resolve()
    source_path = (root / args.source).resolve()
    target_path = (root / args.target).resolve()
    checkpoint = (root / args.checkpoint).resolve()
    config = (root / args.config).resolve()
    output_dir = (root / args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    for path in (source_path, target_path, checkpoint, config):
        if not path.is_file():
            raise FileNotFoundError(path)
    if not torch.cuda.is_available():
        raise RuntimeError("Seed-VC realtime-tiny 需要 CUDA；torch.cuda.is_available()=False")

    device = torch.device("cuda:0")
    # 官方 real-time-gui.py 以 repo cwd 解析 hifigan/config/cache 相對路徑。
    os.chdir(repo)
    if not args.allow_network_assets:
        # WhisperModel / AutoFeatureExtractor 由 transformers 自己解析 cache；
        # 將離線模式設在 import 前，避免已存在的本機 cache 仍被拿去做 HEAD。
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
    module = load_official_module(repo)
    # 官方 real-time-gui.py 會從 Hugging Face 下載 CampPlus／HiFT；本專案
    # 已保存可重跑的 local cache，優先使用它，避免網路狀態改變測試結果。
    module.load_custom_model_from_hf = make_asset_loader(repo, args.allow_network_assets)
    module.device = device
    model_args = SimpleNamespace(checkpoint_path=str(checkpoint), config_path=str(config), fp16=bool(args.fp16))

    started = time.perf_counter()
    model_set = module.load_models(model_args)
    model_load_sec = time.perf_counter() - started
    model_sr = int(model_set[-1]["sampling_rate"])

    # Realtime GUI 預設以 2.5 秒 content-encoder context + block + right context
    # 建立輸入；custom_infer 內部會去掉 2 秒 CE 差異，只回傳 block_time 的音訊。
    source, _ = librosa.load(str(source_path), sr=16000, mono=True)
    reference, _ = librosa.load(str(target_path), sr=model_sr, mono=True)
    context_seconds = 2.5 + args.block_time + 0.02
    window_samples = int(round(context_seconds * 16000))
    return_length = max(1, int(round(args.block_time * 50)))
    skip_head = int(round(2.5 * 50))
    skip_tail = 1
    outputs = []
    rows = []

    module.prompt_condition = None
    module.reference_wav_name = ""
    for block_index in range(args.blocks):
        start_sample = int(round(block_index * args.block_time * 16000))
        window = source[start_sample : start_sample + window_samples]
        if window.shape[0] < window_samples:
            window = np.pad(window, (0, window_samples - window.shape[0]))
        input_tensor = torch.from_numpy(window.astype(np.float32)).to(device)
        started = time.perf_counter()
        with torch.inference_mode():
            output = module.custom_infer(
                model_set,
                reference,
                str(target_path),
                input_tensor,
                window_samples,
                skip_head,
                skip_tail,
                return_length,
                args.diffusion_steps,
                0.7,
                3.0,
                2.0,
            )
        torch.cuda.synchronize()
        elapsed = time.perf_counter() - started
        output_np = output.detach().float().cpu().numpy().reshape(-1)
        outputs.append(output_np)
        rows.append(
            {
                "block_index": block_index,
                "input_window_sec": context_seconds,
                "return_sec": args.block_time,
                "elapsed_sec": elapsed,
                "rtf": elapsed / args.block_time,
                "samples": int(output_np.size),
                "rms": float(np.sqrt(np.mean(np.square(output_np)))) if output_np.size else 0.0,
                "peak": float(np.max(np.abs(output_np))) if output_np.size else 0.0,
                "finite": bool(np.isfinite(output_np).all()),
            }
        )

    combined = np.concatenate(outputs) if outputs else np.zeros(0, dtype=np.float32)
    output_wav = output_dir / "realtime-tiny-headless.wav"
    sf.write(output_wav, combined, model_sr)
    latencies = np.asarray([row["elapsed_sec"] * 1000.0 for row in rows], dtype=np.float64)
    report = {
        "status": "PASS" if rows and all(row["finite"] and row["rms"] > 0 for row in rows) else "BLOCKED",
        "backend": "seed-vc",
        "profile": "realtime-tiny",
        "mode": "headless_official_custom_infer",
        "device": str(device),
        "torch": torch.__version__,
        "cuda": torch.version.cuda,
        "model_sample_rate": model_sr,
        "model_load_sec": model_load_sec,
        "blocks": rows,
        "p50_latency_ms": float(np.percentile(latencies, 50)) if latencies.size else None,
        "p95_latency_ms": float(np.percentile(latencies, 95)) if latencies.size else None,
        "mean_rtf": float(np.mean([row["rtf"] for row in rows])) if rows else None,
        "asset_mode": "local-first-network-opt-in" if not args.allow_network_assets else "local-first-network-allowed",
        "output_wav": str(output_wav.relative_to(root)),
        "audio_device_e2e": "WAITING; this test bypasses PortAudio/microphone",
    }
    report_path = output_dir / "seed-vc-realtime-tiny-test.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
