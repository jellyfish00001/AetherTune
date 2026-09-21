"""CosyVoice2 zero-shot inference entrypoint for the dedicated WSL environment.

這個 runner 只負責離線／本機模型推論：不會自動替使用者猜 reference transcript，
也不會把音檔上傳到外部服務。使用者必須提供與 prompt audio 對應的 exact prompt text。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import torch
import torchaudio
from cosyvoice.cli.cosyvoice import CosyVoice2

from audio_output_validation import validate_wav_file


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run CosyVoice2 zero-shot TTS in WSL.")
    parser.add_argument("--model-dir", required=True, type=Path)
    parser.add_argument("--prompt-audio", required=True, type=Path)
    parser.add_argument("--prompt-text")
    parser.add_argument("--prompt-text-file", type=Path)
    parser.add_argument("--text")
    parser.add_argument("--text-file", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--fp16", action="store_true")
    args = parser.parse_args()

    for path in (args.model_dir, args.prompt_audio):
        if not path.exists():
            raise FileNotFoundError(path)
    if not args.prompt_text and not args.prompt_text_file:
        raise ValueError("需要 --prompt-text 或 --prompt-text-file")
    if not args.text and not args.text_file:
        raise ValueError("需要 --text 或 --text-file")
    prompt_text = args.prompt_text or args.prompt_text_file.read_text(encoding="utf-8")
    text = args.text or args.text_file.read_text(encoding="utf-8")
    if not prompt_text.strip() or not text.strip():
        raise ValueError("prompt text 與 TTS text 不可為空")
    args.output.parent.mkdir(parents=True, exist_ok=True)

    # CosyVoice 官方推論會載入數 GB 權重；先記錄 runtime，讓 artifact 可追溯。
    runtime = {
        "torch": torch.__version__,
        "cuda_available": bool(torch.cuda.is_available()),
        "cuda_device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu",
    }
    started = time.perf_counter()
    cosyvoice = CosyVoice2(str(args.model_dir), fp16=args.fp16)
    load_seconds = time.perf_counter() - started

    # 明確使用 zero-shot API；prompt_text 由呼叫者提供，禁止在 runner 內猜測。
    inference_started = time.perf_counter()
    outputs = list(
        cosyvoice.inference_zero_shot(
            text,
            prompt_text,
            str(args.prompt_audio),
            stream=False,
        )
    )
    if not outputs:
        raise RuntimeError("CosyVoice returned no audio chunks")

    speech = torch.cat([item["tts_speech"].cpu() for item in outputs], dim=1)
    torchaudio.save(str(args.output), speech, cosyvoice.sample_rate)
    output_validation = validate_wav_file(args.output, expected_sample_rate=cosyvoice.sample_rate)
    inference_seconds = time.perf_counter() - inference_started
    output_seconds = speech.shape[1] / cosyvoice.sample_rate

    manifest = {
        "status": "PASS",
        "backend": "cosyvoice2-zero-shot",
        "model_dir": str(args.model_dir),
        "prompt_audio": {"path": str(args.prompt_audio), "sha256": sha256(args.prompt_audio)},
        "prompt_text": prompt_text,
        "text": text,
        "output": {"path": str(args.output), "sha256": sha256(args.output), "bytes": args.output.stat().st_size},
        "output_validation": output_validation,
        "sample_rate": cosyvoice.sample_rate,
        "output_seconds": output_seconds,
        "load_seconds": load_seconds,
        "inference_seconds": inference_seconds,
        "rtf": inference_seconds / output_seconds if output_seconds else None,
        "runtime": runtime,
    }
    manifest_path = args.output.with_suffix(".json")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
