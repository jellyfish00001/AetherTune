"""WSL resident Manual TTS worker. One owned process keeps one model in memory.

Windows writes one JSON request at a time into this process's private mailbox.
The worker writes a result only after the WAV and its manifest are complete.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import time
import uuid
from pathlib import Path

from audio_output_validation import ensure_finite_samples, validate_wav_file
from audio_runner_failure import clear_stale_outputs, write_failure_manifest


def _write_json(path: Path, payload: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def _sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class CosyRuntime:
    def __init__(self, model_dir: Path) -> None:
        import torch
        import torchaudio
        from cosyvoice.cli.cosyvoice import CosyVoice2

        self.torch = torch
        self.torchaudio = torchaudio
        started = time.perf_counter()
        self.model = CosyVoice2(str(model_dir), fp16=True)
        self.load_seconds = time.perf_counter() - started
        self.used = False
        self.model_dir = model_dir

    def generate(self, request: dict, output: Path) -> dict:
        prompt_audio = Path(request["prompt_audio"])
        prompt_text = Path(request["prompt_text_file"]).read_text(encoding="utf-8")
        text = Path(request["text_file"]).read_text(encoding="utf-8")
        if not prompt_audio.is_file() or not prompt_text.strip() or not text.strip():
            raise ValueError("reference audio/text 或輸入文字不可為空")
        started = time.perf_counter()
        chunks = list(self.model.inference_zero_shot(text, prompt_text, str(prompt_audio), stream=False))
        if not chunks:
            raise RuntimeError("CosyVoice returned no audio chunks")
        speech_chunks = []
        for index, item in enumerate(chunks):
            chunk = item["tts_speech"]
            ensure_finite_samples(chunk.detach().cpu().numpy(), f"CosyVoice chunk {index}")
            speech_chunks.append(chunk.cpu())
        speech = self.torch.cat(speech_chunks, dim=1)
        ensure_finite_samples(speech.detach().cpu().numpy(), "CosyVoice output")
        self.torchaudio.save(str(output), speech, self.model.sample_rate)
        validation = validate_wav_file(output, expected_sample_rate=self.model.sample_rate)
        inference_seconds = time.perf_counter() - started
        output_seconds = speech.shape[1] / self.model.sample_rate
        reused = self.used
        self.used = True
        return {
            "status": "PASS", "run_id": uuid.uuid4().hex, "backend": "cosyvoice2-zero-shot",
            "model_dir": str(self.model_dir),
            "prompt_audio": {"path": str(prompt_audio), "sha256": _sha256(prompt_audio)},
            "prompt_text": prompt_text, "text": text,
            "output": {"path": str(output), "sha256": _sha256(output), "bytes": output.stat().st_size},
            "output_validation": validation, "sample_rate": self.model.sample_rate,
            "output_seconds": output_seconds,
            "load_seconds": 0.0 if reused else self.load_seconds,
            "model_load_seconds": self.load_seconds, "runtime_reused": reused,
            "inference_seconds": inference_seconds,
            "rtf": inference_seconds / output_seconds if output_seconds else None,
            "runtime": {
                "torch": self.torch.__version__,
                "cuda_available": bool(self.torch.cuda.is_available()),
                "cuda_device": self.torch.cuda.get_device_name(0) if self.torch.cuda.is_available() else "cpu",
            },
        }


class BreezeRuntime:
    def __init__(self, model_dir: Path) -> None:
        # Reuse the existing Breeze resident runtime that backs its local UI.
        source = Path(__file__).with_name("breeze-tts2-webui.py")
        spec = importlib.util.spec_from_file_location("aethertune_breeze_webui", source)
        if spec is None or spec.loader is None:
            raise RuntimeError("Breeze resident runtime 無法匯入")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.service = module.BreezeRuntimeService(model_dir)

    def generate(self, request: dict, output: Path) -> dict:
        reference_audio = Path(request["reference_audio"])
        reference_text = Path(request["reference_text_file"]).read_text(encoding="utf-8")
        text = Path(request["text_file"]).read_text(encoding="utf-8")
        if not reference_audio.is_file() or not reference_text.strip() or not text.strip():
            raise ValueError("reference audio/text 或輸入文字不可為空")
        return self.service.generate(
            text=text, instruction=str(request.get("instruction") or ""),
            cfg_scale=float(request.get("cfg_scale", 1.0)),
            seed=int(request.get("seed", 42)),
            reference_audio=str(reference_audio), reference_text=reference_text,
            fast_all=bool(request.get("fast_all", False)),
            attention=str(request.get("attention_implementation", "eager")),
            output_file=output,
        )


def main() -> int:
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("--engine", required=True, choices=("cosyvoice", "breeze"))
    parser.add_argument("--model-dir", required=True, type=Path)
    parser.add_argument("--mailbox", required=True, type=Path)
    args = parser.parse_args()
    mailbox = args.mailbox
    requests = mailbox / "requests"
    results = mailbox / "results"
    requests.mkdir(parents=True, exist_ok=True)
    results.mkdir(parents=True, exist_ok=True)
    runtime = CosyRuntime(args.model_dir) if args.engine == "cosyvoice" else BreezeRuntime(args.model_dir)
    _write_json(mailbox / "ready.json", {"status": "READY", "engine": args.engine})
    while True:
        pending = sorted(requests.glob("*.json"))
        if not pending:
            time.sleep(0.05)
            continue
        for path in pending:
            request_id = path.stem
            output: Path | None = None
            try:
                request = json.loads(path.read_text(encoding="utf-8"))
                if request.get("id") != request_id:
                    raise ValueError("request ID 不一致")
                output = Path(request["output"])
                output.parent.mkdir(parents=True, exist_ok=True)
                manifest_path = clear_stale_outputs(output)
                manifest = runtime.generate(request, output)
                manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
                result = {"status": "PASS", "id": request_id}
            except Exception as exc:
                if output is not None:
                    write_failure_manifest(output, args.engine, exc)
                result = {"status": "FAIL", "id": request_id, "error": f"{type(exc).__name__}: {exc}"}
            _write_json(results / f"{request_id}.json", result)
            path.unlink(missing_ok=True)
            print(json.dumps(result, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
