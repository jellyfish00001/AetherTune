"""AetherTune project-local UI for the official Breeze TTS 2 runtime.

Breeze TTS 2 upstream currently exposes CLI and streaming API entrypoints, but
does not ship a Gradio WebUI. This wrapper provides a small local-only UI and
keeps one official runtime resident for repeated requests in the same UI
session. Changing ``eager``/``Fast-all`` intentionally reloads the runtime.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any

import gradio as gr


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BREEZE_REPO = PROJECT_ROOT / "tools" / "external" / "breeze-tts"
DEFAULT_MODEL_DIR = PROJECT_ROOT / "models" / "speech-reconstruction" / "breeze-tts-2"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "artifacts" / "breeze-ui"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


class BreezeRuntimeService:
    """Lazily load and reuse the official Breeze runtime within one UI process."""

    def __init__(self, model_dir: Path) -> None:
        self.model_dir = model_dir
        self._runtime_key: tuple[bool, str] | None = None
        self._tokenizer: Any | None = None
        self._model: Any | None = None
        self._audio_tokenizer: Any | None = None
        self._runtime: Any | None = None
        self._torch: Any | None = None
        self._soundfile: Any | None = None
        self._lock = threading.Lock()

    def _ensure_runtime(self, fast_all: bool, attention: str) -> tuple[float, bool]:
        key = (bool(fast_all), attention)
        if self._runtime_key == key and self._runtime is not None:
            return 0.0, True

        # The model is large. Release an old variant before loading a new one
        # so changing eager/Fast-all does not leave two copies on the GPU.
        old_torch = self._torch
        self._runtime = None
        self._tokenizer = None
        self._model = None
        self._audio_tokenizer = None
        self._runtime_key = None
        gc.collect()
        if old_torch is not None and old_torch.cuda.is_available():
            old_torch.cuda.empty_cache()

        if str(BREEZE_REPO) not in sys.path:
            sys.path.insert(0, str(BREEZE_REPO))
        import soundfile as sf
        import torch

        from breeze_infer.runtime import (
            load_runtime,
            resolve_device,
            update_generation_config_for_breeze,
        )
        from models.fast_streaming import FastBreezeStreamingRuntime, FastStreamingConfig

        device = resolve_device()
        device_type = getattr(device, "type", None) or str(device).split(":", 1)[0]
        if device_type != "cuda" or not torch.cuda.is_available():
            raise RuntimeError(f"Breeze did not select CUDA: device={device}")

        load_started = time.perf_counter()
        tokenizer, model, audio_tokenizer = load_runtime(
            self.model_dir,
            device=device,
            attn_implementation=attention,
        )
        update_generation_config_for_breeze(model)
        runtime = FastBreezeStreamingRuntime(
            model,
            audio_tokenizer,
            FastStreamingConfig(
                max_new_tokens=1500,
                max_seq_len=2048,
                fast_all=bool(fast_all),
                repetition_penalty=1.1,
            ),
            tokenizer=tokenizer,
        )
        load_seconds = time.perf_counter() - load_started

        self._torch = torch
        self._soundfile = sf
        self._tokenizer = tokenizer
        self._model = model
        self._audio_tokenizer = audio_tokenizer
        self._runtime = runtime
        self._runtime_key = key
        return load_seconds, False

    def generate(
        self,
        *,
        text: str,
        instruction: str,
        cfg_scale: float,
        seed: int,
        reference_audio: str | None,
        reference_text: str,
        fast_all: bool,
        attention: str,
        output_file: Path,
    ) -> dict[str, Any]:
        """Generate one WAV using the cached official runtime."""

        # Imports are delayed until the first request so the UI opens quickly.
        if str(BREEZE_REPO) not in sys.path:
            sys.path.insert(0, str(BREEZE_REPO))
        from audio_output_validation import ensure_finite_samples, validate_wav_file
        from breeze_infer.templates import get_template, prepare_inputs, select_template_name

        with self._lock:
            load_seconds, reused = self._ensure_runtime(fast_all, attention)
            assert self._runtime is not None
            assert self._tokenizer is not None
            assert self._model is not None
            assert self._audio_tokenizer is not None
            assert self._soundfile is not None
            assert self._torch is not None

            request: dict[str, Any] = {
                "id": "aethertune-ui-request",
                "text": text.strip(),
                "speaker": "S0",
            }
            if instruction:
                request["instruction"] = instruction.strip()
            if reference_audio:
                request["ref_audio_path"] = str(Path(reference_audio).resolve())
                request["ref_text"] = reference_text.strip()
            template_name = select_template_name(request)
            inputs = prepare_inputs(
                self._tokenizer,
                self._audio_tokenizer,
                self._model,
                [request],
                get_template(template_name),
                guidance_scale=float(cfg_scale),
                guidance_scale_ref=None,
                guidance_scale_ins=None,
            )

            inference_started = time.perf_counter()
            with self._soundfile.SoundFile(
                output_file,
                mode="w",
                samplerate=self._runtime.sample_rate,
                channels=1,
                subtype="PCM_16",
            ) as output_stream:
                for chunk_index, chunk in enumerate(
                    self._runtime.iter_audio_chunks(
                        inputs,
                        request_id=f"aethertune-ui-{uuid.uuid4().hex[:8]}",
                        seed=int(seed),
                    )
                ):
                    audio = chunk.audio
                    if isinstance(audio, self._torch.Tensor):
                        audio = audio.detach().float().cpu().numpy()
                    ensure_finite_samples(audio, f"Breeze chunk {chunk_index}")
                    output_stream.write(audio)
            inference_seconds = time.perf_counter() - inference_started

            with self._soundfile.SoundFile(output_file) as audio_file:
                output_seconds = len(audio_file) / audio_file.samplerate
            output_validation = validate_wav_file(
                output_file, expected_sample_rate=self._runtime.sample_rate
            )
            manifest = {
                "status": "PASS",
                "backend": "breeze-tts-2",
                "ui_mode": "resident-runtime",
                "model_dir": str(self.model_dir),
                "model_source": "BreezeBlue/Breeze-TTS-2",
                "reference_audio": (
                    {"path": str(reference_audio), "sha256": _sha256(Path(reference_audio))}
                    if reference_audio
                    else None
                ),
                "reference_text": reference_text or None,
                "text": text,
                "instruction": instruction or None,
                "output": {
                    "path": str(output_file),
                    "sha256": _sha256(output_file),
                    "bytes": output_file.stat().st_size,
                },
                "output_validation": output_validation,
                "sample_rate": self._runtime.sample_rate,
                "output_seconds": output_seconds,
                "load_seconds": load_seconds,
                "runtime_reused": reused,
                "inference_seconds": inference_seconds,
                "rtf": inference_seconds / output_seconds if output_seconds else None,
                "runtime": {
                    "torch": self._torch.__version__,
                    "cuda": True,
                    "device": self._torch.cuda.get_device_name(0),
                    "cuda_version": self._torch.version.cuda,
                },
                "template": template_name,
                "cfg_scale": float(cfg_scale),
                "seed": int(seed),
                "fast_all": bool(fast_all),
                "attention_implementation": attention,
            }
            _write_json(output_file.with_suffix(".json"), manifest)
            return manifest


def generate_audio(
    text: str,
    instruction: str,
    cfg_scale: float,
    seed: float,
    reference_audio: str | None,
    reference_text: str,
    fast_all: bool,
    attention: str,
    *,
    service: BreezeRuntimeService,
    output_root: Path,
) -> tuple[str | None, str]:
    """Validate UI inputs, call the resident service, and write an audit record."""

    text = (text or "").strip()
    instruction = (instruction or "").strip()
    reference_text = (reference_text or "").strip()
    if not text:
        return None, "WAITING：請輸入要合成的文字。"
    has_reference_audio = bool(reference_audio)
    if has_reference_audio != bool(reference_text):
        return None, "WAITING：reference audio 與 exact reference text 必須同時提供。"
    if has_reference_audio and not Path(reference_audio).is_file():
        return None, f"WAITING：找不到 reference audio：{reference_audio}"
    if not service.model_dir.is_dir():
        return None, f"BLOCKED：找不到 Breeze model directory：{service.model_dir}"

    run_dir = output_root / f"run-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
    run_dir.mkdir(parents=True, exist_ok=True)
    output_file = run_dir / "output.wav"
    started = time.perf_counter()
    try:
        manifest = service.generate(
            text=text,
            instruction=instruction,
            cfg_scale=float(cfg_scale),
            seed=int(seed),
            reference_audio=reference_audio,
            reference_text=reference_text,
            fast_all=bool(fast_all),
            attention=attention,
            output_file=output_file,
        )
    except Exception as exc:
        _write_json(
            run_dir / "ui-run.json",
            {
                "status": "WAITING",
                "ui_mode": "resident-runtime",
                "elapsed_seconds": time.perf_counter() - started,
                "error": repr(exc),
                "reference_audio": reference_audio,
                "cfg_scale": float(cfg_scale),
                "seed": int(seed),
                "fast_all": bool(fast_all),
                "attention_implementation": attention,
            },
        )
        return None, f"WAITING：Breeze UI 生成失敗：{exc!r}\nartifact={run_dir}"

    manifest["ui_run_directory"] = str(run_dir)
    _write_json(run_dir / "ui-run.json", manifest)
    return str(output_file), (
        f"PASS：已完成 Breeze TTS 2 UI 生成，耗時 {time.perf_counter() - started:.1f}s\n"
        f"runtime_reused={manifest['runtime_reused']}，model_load={manifest['load_seconds']:.1f}s，"
        f"inference={manifest['inference_seconds']:.1f}s\n"
        f"artifact={run_dir}\n"
        f"manifest={output_file.with_suffix('.json')}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="AetherTune local Breeze TTS 2 UI")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=50081)
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    service = BreezeRuntimeService(args.model_dir)

    def on_generate(text, instruction, cfg_scale, seed, reference_audio, reference_text, fast_all, attention):
        return generate_audio(
            text,
            instruction,
            cfg_scale,
            seed,
            reference_audio,
            reference_text,
            fast_all,
            attention,
            service=service,
            output_root=args.output_dir,
        )

    with gr.Blocks(title="AetherTune - Breeze TTS 2") as demo:
        gr.Markdown(
            "# AetherTune Breeze TTS 2\n"
            "本地 UI wrapper：輸出內容由官方 Breeze runtime 產生；"
            "reference clone 必須同時提供 exact transcript。首次生成會載入模型，"
            "同一 UI 工作階段的相同 eager/Fast-all 設定會重用模型。"
        )
        text = gr.Textbox(
            label="目標合成文字",
            lines=4,
            value="收到好友從遠方寄來的生日禮物，那份意外的驚喜與深深的祝福讓我心中充滿甜蜜的快樂。",
        )
        instruction = gr.Textbox(
            label="Voice direction / instruction",
            value="一位溫柔明亮的成年女性，聲音清晰自然，語氣親切而帶有溫暖笑意。",
        )
        with gr.Row():
            cfg_scale = gr.Number(label="CFG scale", value=4.0, minimum=0.1, maximum=20.0, step=0.1)
            seed = gr.Number(label="Seed", value=42, precision=0)
            attention = gr.Dropdown(
                label="Attention implementation",
                choices=["eager", "flash_attention_2"],
                value="eager",
            )
            fast_all = gr.Checkbox(label="Fast-all CUDA graph", value=False)
        reference_audio = gr.Audio(label="Reference audio", sources=["upload"], type="filepath")
        reference_text = gr.Textbox(
            label="Exact reference transcript",
            lines=3,
            placeholder="若提供 reference audio，請填入與音檔逐字一致的文字。",
        )
        generate = gr.Button("生成音訊", variant="primary")
        output = gr.Audio(label="Breeze output", type="filepath", autoplay=False)
        status = gr.Textbox(label="狀態與 artifact", lines=8)
        generate.click(
            on_generate,
            inputs=[text, instruction, cfg_scale, seed, reference_audio, reference_text, fast_all, attention],
            outputs=[output, status],
        )

    demo.queue(max_size=2, default_concurrency_limit=1)
    demo.launch(server_name=args.host, server_port=args.port, share=False, inbrowser=False)


if __name__ == "__main__":
    main()
