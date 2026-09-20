"""Run the local RVC WebUI pipeline with FCPE and the selected CUDA device.

這個入口故意不經 VCClient packaged ONNX runtime，直接使用專案固定的
RVC WebUI Python runtime，讓 f0=FCPE、device=cuda 與輸出 WAV 都能在同一份
manifest 中留下證據。模型仍須由使用者確認來源、授權與 metadata。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RVC_ROOT = PROJECT_ROOT / "tools" / "external" / "Retrieval-based-Voice-Conversion-WebUI"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="RVC FCPE CUDA offline inference")
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--index", required=True, type=Path)
    parser.add_argument("--pitch", type=int, default=0)
    parser.add_argument("--index-rate", type=float, default=0.75)
    parser.add_argument("--rms-mix-rate", type=float, default=1.0)
    parser.add_argument("--protect", type=float, default=0.33)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.model = args.model.resolve()
    args.input = args.input.resolve()
    args.output = args.output.resolve()
    args.index = args.index.resolve()
    for path in (args.model, args.input, args.index):
        if not path.is_file():
            raise FileNotFoundError(path)
    if not 0 <= args.index_rate <= 1:
        raise ValueError("index-rate must be between 0 and 1")

    os.chdir(RVC_ROOT)
    os.environ["weight_root"] = str(args.model.parent)
    os.environ["index_root"] = str(RVC_ROOT / "logs")
    os.environ["outside_index_root"] = str(args.index.parent)
    sys.path.insert(0, str(RVC_ROOT))

    # Config() 會解析 sys.argv；只傳入安全的 noautoopen，避免 wrapper 參數
    # 被上游 WebUI parser 誤解，也不會啟動 Gradio UI。
    original_argv = sys.argv[:]
    sys.argv = [original_argv[0], "--noautoopen"]
    try:
        from configs.config import Config
        from infer.vc.modules import VC
        import soundfile as sf
        import torch

        config = Config()
    finally:
        sys.argv = original_argv

    if config.device != "cuda:0" and not config.device.startswith("cuda:"):
        raise RuntimeError(f"RVC did not select CUDA device: {config.device}")
    if not torch.cuda.is_available():
        raise RuntimeError("torch.cuda.is_available() is false")

    started = time.perf_counter()
    vc = VC(config)
    vc.get_vc(args.model.name)
    status, result = vc.vc_single(
        0,
        str(args.input),
        args.pitch,
        "fcpe",
        str(args.index),
        args.index_rate,
        0,
        args.rms_mix_rate,
        args.protect,
    )
    elapsed = time.perf_counter() - started
    if not result or result[0] is None or result[1] is None:
        raise RuntimeError(f"RVC inference failed:\n{status}")

    sample_rate, audio = result
    args.output.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(args.output), audio, sample_rate)
    output_seconds = len(audio) / sample_rate
    manifest = {
        "status": "PASS",
        "backend": "rvc-webui-fcpe-cuda",
        "model": {"path": str(args.model), "sha256": sha256(args.model)},
        "index": {"path": str(args.index), "sha256": sha256(args.index)},
        "input": {"path": str(args.input), "sha256": sha256(args.input)},
        "output": {
            "path": str(args.output),
            "sha256": sha256(args.output),
            "bytes": args.output.stat().st_size,
        },
        "f0_method": "fcpe",
        "device": config.device,
        "gpu_name": torch.cuda.get_device_name(0),
        "torch": torch.__version__,
        "sample_rate": sample_rate,
        "output_seconds": output_seconds,
        "elapsed_seconds": elapsed,
        "rtf": elapsed / output_seconds if output_seconds else None,
        "index_rate": args.index_rate,
        "pitch": args.pitch,
    }
    manifest_path = args.output.with_suffix(".json")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
