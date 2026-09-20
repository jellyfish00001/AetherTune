"""Breeze TTS 2 local runner with UTF-8 text files and a traceable manifest.

這個 runner 呼叫 Breeze 官方 inference modules，不上傳音檔；reference voice
clone 必須由使用者提供 exact transcript。預設使用 eager CUDA path，避免在
16 GB GPU 上誤啟用需要更多顯存的 fast-all path。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from pathlib import Path

import soundfile as sf
import torch

from breeze_infer.runtime import (
    load_runtime,
    resolve_device,
    set_all_seeds,
    update_generation_config_for_breeze,
)
from breeze_infer.templates import get_template, prepare_inputs, select_template_name
from models.fast_streaming import FastBreezeStreamingRuntime, FastStreamingConfig


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_value(value: str | None, value_file: Path | None, label: str) -> str | None:
    if value and value_file:
        raise ValueError(f"{label} 不能同時使用文字參數與檔案參數")
    if value_file:
        return value_file.read_text(encoding="utf-8")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Breeze TTS 2 local inference")
    parser.add_argument("--model-dir", required=True, type=Path)
    parser.add_argument("--text")
    parser.add_argument("--text-file", type=Path)
    parser.add_argument("--reference-audio", type=Path)
    parser.add_argument("--reference-text")
    parser.add_argument("--reference-text-file", type=Path)
    parser.add_argument("--instruction")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--cfg-scale", type=float, default=1.0)
    args = parser.parse_args()

    text = read_value(args.text, args.text_file, "text")
    reference_text = read_value(
        args.reference_text, args.reference_text_file, "reference-text"
    )
    if not text or not text.strip():
        raise ValueError("需要非空 --text 或 --text-file")
    if bool(args.reference_audio) != bool(reference_text and reference_text.strip()):
        raise ValueError("reference audio 與 exact reference text 必須成對提供")
    if args.reference_audio and not args.reference_audio.is_file():
        raise FileNotFoundError(args.reference_audio)
    if not args.model_dir.is_dir():
        raise FileNotFoundError(args.model_dir)
    if not math.isfinite(args.cfg_scale) or args.cfg_scale <= 0:
        raise ValueError("cfg-scale 必須大於 0")

    device = resolve_device()
    device_type = getattr(device, "type", None) or str(device).split(":", 1)[0]
    if device_type != "cuda" or not torch.cuda.is_available():
        raise RuntimeError(f"Breeze did not select CUDA: device={device}")

    load_started = time.perf_counter()
    tokenizer, model, audio_tokenizer = load_runtime(
        args.model_dir,
        device=device,
        attn_implementation="eager",
    )
    update_generation_config_for_breeze(model)
    runtime = FastBreezeStreamingRuntime(
        model,
        audio_tokenizer,
        FastStreamingConfig(
            max_new_tokens=1500,
            max_seq_len=2048,
            fast_all=False,
            fast_text_encoder=False,
            fast_backbone_prefill=False,
            fast_backbone_decode=False,
            fast_depth_decoder=False,
            fast_codec=False,
            repetition_penalty=1.1,
        ),
        tokenizer=tokenizer,
    )
    load_seconds = time.perf_counter() - load_started

    request = {"id": "aethertune-request", "text": text.strip(), "speaker": "S0"}
    if args.instruction:
        request["instruction"] = args.instruction.strip()
    if args.reference_audio:
        request["ref_audio_path"] = str(args.reference_audio)
        request["ref_text"] = reference_text.strip()
    template_name = select_template_name(request)
    inputs = prepare_inputs(
        tokenizer,
        audio_tokenizer,
        model,
        [request],
        get_template(template_name),
        guidance_scale=args.cfg_scale,
        guidance_scale_ref=None,
        guidance_scale_ins=None,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    inference_started = time.perf_counter()
    with sf.SoundFile(
        args.output,
        mode="w",
        samplerate=runtime.sample_rate,
        channels=1,
        subtype="PCM_16",
    ) as output_file:
        for chunk in runtime.iter_audio_chunks(
            inputs, request_id="aethertune-request", seed=args.seed
        ):
            output_file.write(chunk.audio)
    inference_seconds = time.perf_counter() - inference_started

    with sf.SoundFile(args.output) as audio_file:
        output_seconds = len(audio_file) / audio_file.samplerate
    manifest = {
        "status": "PASS",
        "backend": "breeze-tts-2",
        "model_dir": str(args.model_dir),
        "model_source": "BreezeBlue/Breeze-TTS-2",
        "reference_audio": (
            {"path": str(args.reference_audio), "sha256": sha256(args.reference_audio)}
            if args.reference_audio
            else None
        ),
        "reference_text": reference_text,
        "text": text,
        "instruction": args.instruction,
        "output": {
            "path": str(args.output),
            "sha256": sha256(args.output),
            "bytes": args.output.stat().st_size,
        },
        "sample_rate": runtime.sample_rate,
        "output_seconds": output_seconds,
        "load_seconds": load_seconds,
        "inference_seconds": inference_seconds,
        "rtf": inference_seconds / output_seconds if output_seconds else None,
        "runtime": {
            "torch": torch.__version__,
            "cuda": True,
            "device": torch.cuda.get_device_name(0),
            "cuda_version": torch.version.cuda,
        },
        "template": template_name,
        "cfg_scale": args.cfg_scale,
        "seed": args.seed,
    }
    manifest_path = args.output.with_suffix(".json")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
