"""Headless resident streaming voice-conversion processors.

The desktop capture/output worker owns the audio device and its lifecycle.  This
module only owns a resident model, a fixed host-rate block contract, and the
rolling state needed by one conversion stream.  Imports for the three upstream
backends stay lazy so that parameter and algebra tests do not require any model
environment.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import math
import os
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping

import numpy as np


HOST_SAMPLE_RATE = 48_000
MEANVC2_BLOCK = 7_680  # 160 ms at the common host rate.
XVC_CODEC_HOP = 1_280  # 80 ms at the X-VC model sample rate.
SEED_VC_ZC = 960  # 20 ms at the common host rate, copied from upstream GUI.
MEANVC2_CODE_REVISION = "13acf84c1bf135ea5edad9c245b345289b06b33e"
XVC_CODE_REVISION = "49df8c591eafc48b096e466d96f9839f9c0dd739"


def _as_path(value: str | os.PathLike[str], label: str) -> Path:
    path = Path(value).expanduser().resolve()
    if not path.exists():
        raise ValueError(f"{label} 不存在：{path}")
    return path


def _require_file(value: str | os.PathLike[str], label: str) -> Path:
    path = _as_path(value, label)
    if not path.is_file():
        raise ValueError(f"{label} 不是檔案：{path}")
    return path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _git_revision(repo: Path) -> str | None:
    """Read a checkout revision without invoking git or mutating the checkout."""
    git = repo / ".git"
    if git.is_file():
        text = git.read_text(encoding="utf-8").strip()
        if text.startswith("gitdir:"):
            git = (repo / text.split(":", 1)[1].strip()).resolve()
    if not git.is_dir():
        return None
    head = git / "HEAD"
    if not head.is_file():
        return None
    value = head.read_text(encoding="utf-8").strip()
    if not value.startswith("ref: "):
        return value or None
    ref = value[5:]
    target = git / ref
    if target.is_file():
        return target.read_text(encoding="utf-8").strip() or None
    packed = git / "packed-refs"
    if packed.is_file():
        suffix = f" {ref}"
        for line in packed.read_text(encoding="utf-8").splitlines():
            if line and not line.startswith("#") and line.endswith(suffix):
                return line.split(" ", 1)[0]
    return None


def _source_metadata(repo: Path, files: tuple[str, ...], *, registered_revision: str | None = None) -> dict[str, Any]:
    actual_revision = _git_revision(repo)
    if registered_revision is not None and actual_revision != registered_revision:
        raise ValueError(
            f"SOURCE_REVISION_MISMATCH: {repo.name} actual={actual_revision!r} registered={registered_revision!r}"
        )
    source_hashes: dict[str, str | None] = {}
    for relative in files:
        path = repo / relative
        source_hashes[relative] = _sha256(path) if path.is_file() else None
    return {
        "source_revision": actual_revision or "unresolved",
        "source_hashes": source_hashes,
        "source_root": str(repo),
    }


def _validated_audio(value: Any, expected: int | None = None, *, label: str = "AUDIO") -> np.ndarray:
    """Normalize one-dimensional float32 audio and reject ambiguous tensors."""
    if hasattr(value, "detach"):
        value = value.detach().float().cpu().numpy()
    array = np.asarray(value)
    array = np.squeeze(array)
    if array.ndim != 1:
        raise ValueError(f"{label}_INVALID: 必須是 mono 一維音訊")
    array = np.ascontiguousarray(array, dtype=np.float32)
    if expected is not None and array.size != expected:
        raise ValueError(f"{label}_INVALID: frame 數 {array.size} != {expected}")
    if not np.isfinite(array).all():
        raise ValueError(f"{label}_INVALID: 含非有限樣本")
    return array


def _fit_length(value: Any, length: int) -> np.ndarray:
    array = _validated_audio(value)
    if array.size == length:
        return array
    if array.size > length:
        return np.ascontiguousarray(array[:length], dtype=np.float32)
    return np.pad(array, (0, length - array.size)).astype(np.float32, copy=False)


def _resample_poly(value: Any, up: int, down: int) -> np.ndarray:
    """Resample only audio arrays; scipy is imported after a backend is selected."""
    array = _validated_audio(value)
    if up == down:
        return array.copy()
    try:
        from scipy.signal import resample_poly
    except ImportError as exc:  # pragma: no cover - environment contract
        raise RuntimeError("DEPENDENCY_MISSING: streaming adapter 需要 scipy.signal.resample_poly") from exc
    result = resample_poly(array, up, down)
    return _validated_audio(result)


def _cuda_device(torch_module: Any, values: Mapping[str, Any], engine: str) -> Any:
    """Enforce CUDA instead of accepting an upstream CPU fallback."""
    if not torch_module.cuda.is_available():
        raise RuntimeError(f"CUDA_UNAVAILABLE: {engine} processor 需要 CUDA，拒絕暗中回退 CPU")
    try:
        gpu = int(values.get("gpu", 0))
    except (TypeError, ValueError) as exc:
        raise ValueError("PARAMETER_INVALID: gpu 必須是整數") from exc
    if gpu < 0 or gpu >= torch_module.cuda.device_count():
        raise ValueError(f"PARAMETER_INVALID: gpu={gpu} 不存在")
    return torch_module.device(f"cuda:{gpu}")


def _module_device(module: Any) -> str | None:
    try:
        return str(next(module.parameters()).device)
    except (AttributeError, StopIteration, TypeError):
        return None


def _load_module(path: Path, name_prefix: str) -> Any:
    name = f"_aethertune_{name_prefix}_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"IMPORT_FAILED: 無法載入 upstream module：{path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _meanvc2_paths(runtime: Any, root: Path) -> Path:
    """Apply the same local model-path override as tools/meanvc2-run.py."""
    assets = root / "models/meanvc2"
    runtime.VOCODER_PATH = str(assets / "vocos.pt")
    runtime.SPEAKER_MODEL_PATH = str(assets / "wavlm_large_finetune.pth")
    runtime.WAVLM_CONFIG_PATH = str(assets / "wavlm_large_cfg.pt")
    for name, paths in runtime.MODEL_PATHS.items():
        paths["ckpt"] = str(assets / f"meanvc2_{name}_40ms.safetensors")
        paths["asr_ckpt"] = str(assets / ("fastu2pp_80ms.pt" if name == "40ms" else "fastu2pp_160ms.pt"))
    return assets


class MeanVC2Processor:
    """Resident MeanVC2 processor using upstream VCRunner.process_chunk."""

    sample_rate = HOST_SAMPLE_RATE
    block = MEANVC2_BLOCK

    def __init__(self, root: Path, values: Mapping[str, Any], reference: Path, run_dir: Path):
        import torch

        self.root = root
        self.values = dict(values)
        self.reference = _require_file(reference, "MeanVC2 reference")
        self.run_dir = run_dir
        self.run_dir.mkdir(parents=True, exist_ok=True)
        model_name = str(self.values.get("model", "40ms"))
        if model_name not in ("40ms", "120ms"):
            raise ValueError(f"PARAMETER_INVALID: MeanVC2 model 不支援：{model_name}")
        gpu_device = _cuda_device(torch, self.values, "MeanVC2")
        repo = _require_file(root / "tools/external/MeanVC2/runtime/run_rt.py", "MeanVC2 upstream runtime").parent.parent
        _source_metadata(repo, (), registered_revision=MEANVC2_CODE_REVISION)
        # run_rt.py resolves src imports relative to its own checkout; keep that
        # checkout read-only and override only the model paths in memory.
        runtime_parent = str(repo / "runtime")
        if runtime_parent not in sys.path:
            sys.path.insert(0, runtime_parent)
        runtime = _load_module(repo / "runtime/run_rt.py", "meanvc2_runtime")
        assets = _meanvc2_paths(runtime, root)
        model_paths = runtime.MODEL_PATHS[model_name]
        required = [
            assets / "vocos.pt",
            assets / "wavlm_large_finetune.pth",
            assets / "wavlm_large_cfg.pt",
            Path(model_paths["ckpt"]),
            Path(model_paths["asr_ckpt"]),
        ]
        missing = [str(path) for path in required if not path.is_file()]
        if missing:
            raise ValueError("MODEL_NOT_FOUND: " + ", ".join(missing))
        device_name = "cuda" if int(self.values.get("gpu", 0)) == 0 else str(gpu_device)
        self._runner = runtime.VCRunner(str(self.reference), device_name, model_name)
        self._runtime_module = runtime
        self._model_sample_rate = 16_000
        self._model_block = 2_560
        if int(getattr(self._runner, "CHUNK", self._model_block)) != self._model_block:
            raise ValueError("PARAMETER_INVALID: MeanVC2 process_chunk 必須使用 160 ms／2560 frame")
        devices = {
            name: _module_device(getattr(self._runner, name, None))
            for name in ("vc", "spk_model", "asr", "vocoder")
        }
        devices = {name: value for name, value in devices.items() if value is not None}
        required_cuda = ("vc", "spk_model", "vocoder")
        if any(name not in devices or not devices[name].startswith("cuda") for name in required_cuda):
            raise RuntimeError(f"CUDA_UNAVAILABLE: MeanVC2 模組實際 device={devices}")
        metadata = _source_metadata(
            repo,
            ("runtime/run_rt.py", "runtime/src/dit.py", "runtime/src/speaker.py"),
            registered_revision=MEANVC2_CODE_REVISION,
        )
        metadata.update(
            {
                "engine": "meanvc2",
                "profile": "desktop-headless-resident",
                "device": str(gpu_device),
                "gpu": torch.cuda.get_device_name(int(self.values.get("gpu", 0))),
                "torch": torch.__version__,
                "cuda": torch.version.cuda,
                "module_devices": devices,
                "model": model_name,
                "host_sample_rate": self.sample_rate,
                "model_sample_rate": self._model_sample_rate,
                "block": self.block,
                "model_block": self._model_block,
                "reference_sha256": _sha256(self.reference),
                "asset_hashes": {str(path): _sha256(path) for path in required},
                "audio_e2e": "WAITING; capture/output worker and LIVE evidence are separate",
            }
        )
        self.runtime = metadata

    def process(self, mono: Any) -> np.ndarray | None:
        input_host = _validated_audio(mono, self.block, label="INPUT")
        input_model = _fit_length(_resample_poly(input_host, 1, 3), self._model_block)
        output_model = self._runner.process_chunk(input_model)
        if output_model is None:
            return None
        output_model = _validated_audio(output_model, label="OUTPUT")
        if output_model.size == 0:
            raise ValueError("OUTPUT_INVALID: MeanVC2 回傳空音訊")
        output_host = _resample_poly(output_model, 3, 1)
        return _validated_audio(output_host, label="OUTPUT")

    def reset(self) -> None:
        init_cache = getattr(self._runner, "_init_cache", None)
        if not callable(init_cache):
            raise RuntimeError("RESET_FAILED: MeanVC2 upstream runner 缺少 _init_cache")
        init_cache()


def _xvc_ms_samples(value: Any, name: str, sample_rate: int) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"PARAMETER_INVALID: X-VC {name} 必須是有限數字")
    samples = float(value) * sample_rate / 1000.0
    if abs(samples - round(samples)) > 1e-6:
        raise ValueError(f"PARAMETER_INVALID: X-VC {name} 無法對齊 model sample rate")
    return int(round(samples))


def _validate_xvc_window(values: Mapping[str, Any], sample_rate: int) -> dict[str, int | float]:
    if sample_rate <= 0:
        raise ValueError("PARAMETER_INVALID: X-VC sample_rate 無效")
    current_ms = values.get("current", 160)
    chunk_ms = values.get("chunk", 2400)
    future_ms = values.get("future", 80)
    smooth_ms = values.get("smooth", 20)
    current = _xvc_ms_samples(current_ms, "current", sample_rate)
    chunk = _xvc_ms_samples(chunk_ms, "chunk", sample_rate)
    future = _xvc_ms_samples(future_ms, "future", sample_rate)
    smooth = _xvc_ms_samples(smooth_ms, "smooth", sample_rate)
    if current <= 0 or chunk <= 0 or future < 0 or smooth < 0:
        raise ValueError("PARAMETER_INVALID: X-VC streaming frame 必須符合正負邊界")
    if smooth > current or current + smooth + future > chunk:
        raise ValueError("PARAMETER_INVALID: X-VC streaming 視窗不合法")
    hop = int(values.get("latent_hop_length", XVC_CODEC_HOP))
    if hop != XVC_CODEC_HOP:
        raise ValueError(f"PARAMETER_INVALID: X-VC codec hop 必須是 {XVC_CODEC_HOP}")
    # current/chunk/future are codec-window boundaries.  smooth is an audio
    # overlap length and intentionally may be a smaller fade interval (20 ms
    # is the upstream default while the codec hop is 80 ms).
    for name, frame_count in (("current", current), ("chunk", chunk), ("future", future)):
        if frame_count and frame_count % hop:
            raise ValueError(f"PARAMETER_INVALID: X-VC {name} 必須對齊 codec hop={hop}")
    history = chunk - current - smooth - future
    host_block_float = float(current_ms) * HOST_SAMPLE_RATE / 1000.0
    if abs(host_block_float - round(host_block_float)) > 1e-6:
        raise ValueError("PARAMETER_INVALID: X-VC current 無法形成 48000 host frame")
    host_block = int(round(host_block_float))
    return {
        "current_ms": float(current_ms),
        "chunk_ms": float(chunk_ms),
        "future_ms": float(future_ms),
        "smooth_ms": float(smooth_ms),
        "current": current,
        "chunk": chunk,
        "future": future,
        "smooth": smooth,
        "history": history,
        "hop": hop,
        "host_block": host_block,
    }


def _crossfade_overlap(current: np.ndarray, tail: np.ndarray | None) -> np.ndarray:
    """Blend one X-VC current segment with the preceding raw overlap tail."""
    current = _validated_audio(current, label="OUTPUT")
    if tail is None or tail.size == 0:
        return current.copy()
    tail = _validated_audio(tail, label="OVERLAP")
    overlap = min(current.size, tail.size)
    fade_in = 0.5 * (1.0 - np.cos(np.pi * np.linspace(0.0, 1.0, overlap, dtype=np.float32)))
    fade_out = 1.0 - fade_in
    result = current.copy()
    result[:overlap] = tail[:overlap] * fade_out + result[:overlap] * fade_in
    return _validated_audio(result, label="OUTPUT")


class XVCProcessor:
    """Resident X-VC processor using one rolling window per host block."""

    sample_rate = HOST_SAMPLE_RATE

    def __init__(self, root: Path, values: Mapping[str, Any], reference: Path, run_dir: Path):
        import torch
        import yaml

        # tools/xvc-run.py fixes this before the resident model is built; doing
        # it here avoids inheriting an arbitrary host thread count.
        torch.set_num_threads(4)
        self.root = root
        self.values = dict(values)
        self.reference = _require_file(reference, "X-VC reference")
        self.run_dir = run_dir
        self.run_dir.mkdir(parents=True, exist_ok=True)
        repo = _as_path(root / "tools/external/X-VC", "X-VC upstream repo")
        _source_metadata(repo, (), registered_revision=XVC_CODE_REVISION)
        config_source = _require_file(repo / "configs/xvc.yaml", "X-VC config")
        assets = _as_path(root / "models/xvc", "X-VC local assets")
        config = yaml.safe_load(config_source.read_text(encoding="utf-8"))
        if not isinstance(config, dict):
            raise ValueError("PARAMETER_INVALID: X-VC config 根節點不是 object")
        config = copy.deepcopy(config)
        generator = config.setdefault("model", {}).setdefault("generator", {})
        generator["loss_config"] = None
        generator.setdefault("speaker_encoder", {})["pretrained_dir"] = str(assets / "eres2net")
        semantic = generator.setdefault("semantic_encoder", {})
        encoder = semantic.setdefault("encoder", {}).setdefault("from_pretrained", {})
        encoder["local_ckpt"] = str(assets / "glm-tokenizer")
        semantic.setdefault("cfg", {})["local_ckpt"] = str(assets / "glm-tokenizer")
        self._config = config
        self._model_sample_rate = int(config.get("sample_rate", 16_000))
        self._window = _validate_xvc_window(self.values, self._model_sample_rate)
        self.block = int(self._window["host_block"])
        local_config = self.run_dir / "xvc-local.yaml"
        local_config.write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")
        device = _cuda_device(torch, self.values, "X-VC")
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
        sys.path.insert(0, str(repo))
        from bins import infer_utils

        gpu = int(self.values.get("gpu", 0))
        cfg, model, actual_device = infer_utils.load_xvc(
            str(local_config), str(assets / "xvc.pt"), gpu, bool(self.values.get("ema_load", False))
        )
        actual_model_device = _module_device(model)
        if not str(actual_device).startswith("cuda") or not (actual_model_device or "").startswith("cuda"):
            raise RuntimeError(
                f"CUDA_UNAVAILABLE: X-VC 實際 device={actual_device}, model={actual_model_device}"
            )
        self._torch = torch
        self._infer_utils = infer_utils
        self._model = model
        self._device = device
        self._cfg = cfg
        component_devices = {
            name: _module_device(getattr(model, name, None))
            for name in (
                "semantic_encoder",
                "semantic_adapter",
                "acoustic_encoder",
                "acoustic_quantizer",
                "prenet",
                "acoustic_converter",
                "acoustic_decoder",
                "speaker_encoder",
                "mel_extractor",
            )
        }
        component_devices = {name: value for name, value in component_devices.items() if value is not None}
        source_wav, target_wav, target_wav_cond = infer_utils.load_pair_as_tensors(
            str(self.reference),
            str(self.reference),
            cfg=cfg,
            device=actual_device,
            latent_hop_length=int(self._window["hop"]),
            mask_target_condition=bool(self.values.get("mask_target_condition", False)),
        )
        self._speaker_condition, self._frame_condition = infer_utils.precompute_conditions(
            model, target_wav, target_wav_cond
        )
        del source_wav
        self._buffer = np.zeros(0, dtype=np.float32)
        self._buffer_start = 0
        self._received = 0
        self._position = 0
        self._tail: np.ndarray | None = None
        self._last_window: np.ndarray | None = None
        required_assets = [assets / "xvc.pt", assets / "glm-tokenizer/model.safetensors", assets / "eres2net/pretrained_eres2net.ckpt"]
        metadata = _source_metadata(
            repo,
            ("bins/infer_utils.py", "bins/infer_single.py", "configs/xvc.yaml"),
            registered_revision=XVC_CODE_REVISION,
        )
        metadata.update(
            {
                "engine": "xvc",
                "profile": "desktop-headless-resident",
                "device": str(actual_device),
                "model_device": actual_model_device,
                "component_devices": component_devices,
                "semantic_device": component_devices.get("semantic_encoder"),
                "vocoder_device": component_devices.get("acoustic_decoder"),
                "gpu": torch.cuda.get_device_name(int(self.values.get("gpu", 0))),
                "torch": torch.__version__,
                "cuda": torch.version.cuda,
                "host_sample_rate": self.sample_rate,
                "model_sample_rate": self._model_sample_rate,
                "block": int(self._window["host_block"]),
                "model_block": int(self._window["current"]),
                "window": dict(self._window),
                "codec_hop": int(self._window["hop"]),
                "reference_sha256": _sha256(self.reference),
                "asset_hashes": {str(path): _sha256(path) for path in required_assets if path.is_file()},
                "config_path": str(local_config),
                "latency_ms": float(self._window["smooth_ms"] + self._window["future_ms"]),
                "audio_e2e": "WAITING; capture/output worker and LIVE evidence are separate",
            }
        )
        self.runtime = metadata

    def _append(self, value: np.ndarray) -> None:
        if self._buffer.size == 0:
            self._buffer_start = self._received
            self._buffer = value.copy()
            self._received += value.size
            return
        expected = self._buffer_start + self._buffer.size
        if expected != self._received:
            raise RuntimeError("STREAM_STATE_INVALID: X-VC rolling buffer 不連續")
        self._buffer = np.concatenate((self._buffer, value)).astype(np.float32, copy=False)
        self._received += value.size

    def _take_window(self, start: int, end: int) -> np.ndarray:
        if end <= start:
            raise ValueError("PARAMETER_INVALID: X-VC window end 必須大於 start")
        buffer_end = self._buffer_start + self._buffer.size
        left_pad = max(0, self._buffer_start - start)
        right_pad = max(0, end - buffer_end)
        actual_start = max(start, self._buffer_start)
        actual_end = min(end, buffer_end)
        body = self._buffer[actual_start - self._buffer_start : actual_end - self._buffer_start]
        if left_pad or right_pad:
            body = np.pad(body, (left_pad, right_pad))
        return _validated_audio(body, end - start, label="WINDOW")

    def _drop_old_samples(self) -> None:
        keep_start = max(0, self._position - int(self._window["history"]))
        if keep_start <= self._buffer_start:
            return
        offset = min(self._buffer.size, keep_start - self._buffer_start)
        self._buffer = self._buffer[offset:].copy()
        self._buffer_start += offset

    def process(self, mono: Any) -> np.ndarray | None:
        host_block = int(self._window["host_block"])
        input_host = _validated_audio(mono, host_block, label="INPUT")
        input_model = _fit_length(
            _resample_poly(input_host, self._model_sample_rate, self.sample_rate),
            int(self._window["current"]),
        )
        self._append(input_model)
        current_start = self._position
        history = int(self._window["history"])
        current = int(self._window["current"])
        smooth = int(self._window["smooth"])
        future = int(self._window["future"])
        window = self._take_window(current_start - history, current_start + current + smooth + future)
        self._last_window = window.copy()
        required_input_end = current_start + current + smooth + future
        if self._received < required_input_end:
            self._drop_old_samples()
            return None
        source = self._torch.from_numpy(window).to(self._device).view(1, 1, -1)
        with self._torch.inference_mode():
            output = self._infer_utils.run_stream_chunk_forward(
                self._model, source, self._speaker_condition, self._frame_condition
            )
        output_model = _validated_audio(output, label="OUTPUT")
        current_end = history + current
        required_end = current_end + smooth
        if output_model.size < required_end:
            raise ValueError(
                f"OUTPUT_INVALID: X-VC window output frame 不足 {output_model.size} < {required_end}"
            )
        current_output = output_model[history:current_end]
        overlap_tail = output_model[current_end:required_end] if smooth else None
        current_output = _crossfade_overlap(current_output, self._tail)
        self._tail = overlap_tail.copy() if overlap_tail is not None else None
        self._position += current
        self._drop_old_samples()
        result = _resample_poly(current_output, self.sample_rate, self._model_sample_rate)
        return _fit_length(result, host_block)

    def reset(self) -> None:
        self._buffer = np.zeros(0, dtype=np.float32)
        self._buffer_start = 0
        self._received = 0
        self._position = 0
        self._tail = None
        self._last_window = None


def _seed_manifest(root: Path) -> dict[str, Any]:
    """Read the registered local-only cache contract without repairing/downloading it."""
    manifest_path = _require_file(root / "tools/seed-vc-assets.json", "Seed-VC asset manifest")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    from services.engines.seed_cache import REPOSITORIES

    records = manifest.get("huggingface_repositories", [])
    if {record.get("repo_id") for record in records} != set(REPOSITORIES):
        raise ValueError("MODEL_NOT_FOUND: Seed-VC cache repository 登記不符")
    return manifest


def _seed_hf_asset(root: Path, manifest: Mapping[str, Any], repo_id: str, filename: str) -> Path:
    for record in manifest["huggingface_repositories"]:
        if record["repo_id"] != repo_id:
            continue
        cache_root = root / "tools/external/seed-vc/checkpoints" / record["cache_directory"]
        revision = record["expected_local_revision"]
        ref = cache_root / "refs/main"
        if ref.is_file() and ref.read_text(encoding="utf-8").strip() != revision:
            raise ValueError(f"MODEL_NOT_FOUND: Seed-VC cache revision 不符：{repo_id}")
        candidate = cache_root / "snapshots" / revision / filename
        if candidate.is_file():
            return candidate
        raise ValueError(f"MODEL_NOT_FOUND: Seed-VC local asset：{repo_id}/{filename}")
    raise ValueError(f"MODEL_NOT_FOUND: Seed-VC 未登記 repository：{repo_id}")


def _seed_local_loader(root: Path, manifest: Mapping[str, Any]):
    def load_asset(repo_id: str, model_filename: str = "pytorch_model.bin", config_filename: str | None = None):
        model_path = _seed_hf_asset(root, manifest, repo_id, model_filename)
        if config_filename is None:
            return str(model_path)
        return str(model_path), str(_seed_hf_asset(root, manifest, repo_id, config_filename))

    return load_asset


class SeedVCProcessor:
    """Resident Seed-VC processor adapted from real-time-gui.py without GUI/VAD."""

    sample_rate = HOST_SAMPLE_RATE

    def __init__(self, root: Path, values: Mapping[str, Any], reference: Path, run_dir: Path):
        import torch

        # real-time-gui.py may import OMP-backed dependencies before this
        # constructor runs; enforce the same bounded resident-wrapper count as
        # tools/xvc-run.py before loading Seed-VC weights.
        torch.set_num_threads(4)
        self.root = root
        self.values = dict(values)
        self.reference = _require_file(reference, "Seed-VC reference")
        self.run_dir = run_dir
        self.run_dir.mkdir(parents=True, exist_ok=True)
        repo = _as_path(root / "tools/external/seed-vc", "Seed-VC upstream repo")
        checkpoint = _require_file(
            root / "models/seed-vc/checkpoints/realtime-tiny/DiT_uvit_tat_xlsr_ema.pth",
            "Seed-VC realtime checkpoint",
        )
        config_path = _require_file(
            repo / "configs/presets/config_dit_mel_seed_uvit_xlsr_tiny.yml",
            "Seed-VC realtime config",
        )
        manifest = _seed_manifest(root)
        seed_revision = manifest.get("seed_vc_source", {}).get("revision")
        _source_metadata(repo, (), registered_revision=seed_revision)
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA_UNAVAILABLE: Seed-VC processor 需要 CUDA，拒絕暗中回退 CPU")
        gpu_device = _cuda_device(torch, self.values, "Seed-VC")
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        os.environ["HF_HOME"] = str(repo / "checkpoints")
        os.environ["HF_HUB_CACHE"] = str(repo / "checkpoints")
        os.environ["HUGGINGFACE_HUB_CACHE"] = str(repo / "checkpoints")
        os.environ["TRANSFORMERS_CACHE"] = str(repo / "checkpoints")
        os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
        # real-time-gui.py only enters its GUI block under __main__.  Its loader
        # still resolves package imports and local relative assets from checkout CWD.
        old_cwd = Path.cwd()
        sys.path.insert(0, str(repo))
        try:
            os.chdir(repo)
            module = _load_module(repo / "real-time-gui.py", "seedvc_realtime_gui")
            module.device = gpu_device
            module.fp16 = False
            module.load_custom_model_from_hf = _seed_local_loader(root, manifest)
            model_args = SimpleNamespace(
                checkpoint_path=str(checkpoint),
                config_path=str(config_path),
                fp16=False,
                gpu=int(self.values.get("gpu", 0)),
            )
            model_set = module.load_models(model_args)
        finally:
            os.chdir(old_cwd)
        self._module = module
        self._torch = torch
        self._device = gpu_device
        self._model_set = model_set
        self._model_sample_rate = int(model_set[-1]["sampling_rate"])
        try:
            reference_wav = module.librosa.load(
                str(self.reference), sr=self._model_sample_rate, mono=True
            )[0]
        except (AttributeError, OSError, ValueError) as exc:
            raise ValueError(f"REFERENCE_INVALID: Seed-VC reference 載入失敗：{self.reference}") from exc
        self._reference_wav = _validated_audio(reference_wav, label="REFERENCE")
        self._block_time = float(self.values.get("block_time", 0.30))
        self._crossfade_time = float(self.values.get("crossfade_length", 0.04))
        self._extra_time_ce = float(self.values.get("extra_time_ce", 5.0))
        self._extra_time = float(self.values.get("extra_time", 0.5))
        self._extra_time_right = float(self.values.get("extra_time_right", 0.02))
        if not all(math.isfinite(value) for value in (
            self._block_time, self._crossfade_time, self._extra_time_ce,
            self._extra_time, self._extra_time_right,
        )):
            raise ValueError("PARAMETER_INVALID: Seed-VC context 參數必須是有限數")
        if (
            self._block_time <= 0
            or self._crossfade_time <= 0
            or self._crossfade_time > self._block_time
            or self._extra_time < 0
            or self._extra_time_ce < self._extra_time
            or self._extra_time_right < 0
        ):
            raise ValueError("PARAMETER_INVALID: Seed-VC block/crossfade 不合法")
        self._zc = SEED_VC_ZC
        self.block = int(round(self._block_time * self.sample_rate / self._zc)) * self._zc
        self._crossfade_frame = int(round(self._crossfade_time * self.sample_rate / self._zc)) * self._zc
        self._extra_frame = int(round(self._extra_time_ce * self.sample_rate / self._zc)) * self._zc
        self._extra_frame_right = int(round(self._extra_time_right * self.sample_rate / self._zc)) * self._zc
        if self.block <= 0:
            raise ValueError("PARAMETER_INVALID: Seed-VC block frame 不合法")
        self._sola_buffer_frame = min(self._crossfade_frame, 4 * self._zc)
        self._sola_search_frame = self._zc
        self._block_frame_16k = 320 * self.block // self._zc
        self._input_wav = torch.zeros(
            self._extra_frame + self._crossfade_frame + self._sola_search_frame + self.block + self._extra_frame_right,
            device=self._device,
            dtype=torch.float32,
        )
        self._input_wav_res = torch.zeros(
            320 * self._input_wav.shape[0] // self._zc,
            device=self._device,
            dtype=torch.float32,
        )
        self._sola_buffer = torch.zeros(self._sola_buffer_frame, device=self._device, dtype=torch.float32)
        self._fade_in = torch.sin(
            0.5 * math.pi * torch.linspace(0.0, 1.0, steps=self._sola_buffer_frame, device=self._device, dtype=torch.float32)
        ) ** 2
        self._fade_out = 1.0 - self._fade_in
        self._skip_head = self._extra_frame // self._zc
        self._skip_tail = self._extra_frame_right // self._zc
        self._return_length = (self.block + self._sola_buffer_frame + self._sola_search_frame) // self._zc
        devices = {}
        for name, item in zip(("model", "semantic", "vocoder", "campplus"), model_set[:4]):
            device_value = _module_device(item)
            if device_value is not None:
                devices[name] = device_value
        if not devices or any(not value.startswith("cuda") for value in devices.values()):
            raise RuntimeError(f"CUDA_UNAVAILABLE: Seed-VC 模組實際 device={devices}")
        source_metadata = _source_metadata(
            repo,
            ("real-time-gui.py", "configs/presets/config_dit_mel_seed_uvit_xlsr_tiny.yml"),
            registered_revision=manifest.get("seed_vc_source", {}).get("revision"),
        )
        source_metadata.update(
            {
                "engine": "seed-vc",
                "profile": "desktop-headless-resident-realtime-tiny",
                "device": str(gpu_device),
                "gpu": torch.cuda.get_device_name(int(self.values.get("gpu", 0))),
                "torch": torch.__version__,
                "cuda": torch.version.cuda,
                "module_devices": devices,
                "host_sample_rate": self.sample_rate,
                "model_sample_rate": self._model_sample_rate,
                "block": self.block,
                "model_block": self._block_frame_16k,
                "zc": self._zc,
                "skip_head": self._skip_head,
                "skip_tail": self._skip_tail,
                "return_length": self._return_length,
                "reference_sha256": _sha256(self.reference),
                "checkpoint_sha256": _sha256(checkpoint),
                "hf_cache_revisions": {
                    record["repo_id"]: record["expected_local_revision"]
                    for record in manifest["huggingface_repositories"]
                },
                "audio_e2e": "WAITING; capture/output worker and LIVE evidence are separate",
            }
        )
        self.runtime = source_metadata

    def process(self, mono: Any) -> np.ndarray:
        input_host = _validated_audio(mono, self.block, label="INPUT")
        self._input_wav[:-self.block] = self._input_wav[self.block:].clone()
        self._input_wav[-self.block:] = self._torch.from_numpy(input_host).to(self._device)
        self._input_wav_res[:-self._block_frame_16k] = self._input_wav_res[self._block_frame_16k:].clone()
        resample_segment = self._input_wav[-self.block - 2 * self._zc :].detach().cpu().numpy()
        resampled = _resample_poly(resample_segment, 1, 3)
        # GUI writes the tail after discarding the 20 ms look-behind frame.
        resampled = resampled[320:]
        write_count = 320 * (self.block // self._zc + 1)
        resampled = _fit_length(resampled, write_count)
        self._input_wav_res[-write_count:] = self._torch.from_numpy(resampled).to(self._device)
        with self._torch.inference_mode():
            infer_wav = self._module.custom_infer(
                self._model_set,
                self._reference_wav,
                str(self.reference),
                self._input_wav_res,
                self._block_frame_16k,
                self._skip_head,
                self._skip_tail,
                self._return_length,
                int(self.values.get("diffusion_steps", 10)),
                float(self.values.get("inference_cfg_rate", 0.7)),
                float(self.values.get("max_prompt_length", 3.0)),
                self._extra_time_ce - self._extra_time,
            )
        infer_wav = infer_wav.detach().float().reshape(-1)
        if not infer_wav.is_cuda:
            raise RuntimeError("CUDA_UNAVAILABLE: Seed-VC custom_infer 輸出未在 CUDA")
        if self._model_sample_rate != self.sample_rate:
            infer_np = _resample_poly(infer_wav.cpu().numpy(), self.sample_rate, self._model_sample_rate)
            infer_wav = self._torch.from_numpy(infer_np).to(self._device)
        required = self.block + self._sola_buffer_frame + self._sola_search_frame
        if infer_wav.numel() < required:
            raise ValueError(f"OUTPUT_INVALID: Seed-VC SOLA 輸出不足 {infer_wav.numel()} < {required}")
        conv_input = infer_wav[None, None, : self._sola_buffer_frame + self._sola_search_frame]
        kernel = self._torch.ones(1, 1, self._sola_buffer_frame, device=self._device, dtype=self._torch.float32)
        import torch.nn.functional as functional

        numerator = functional.conv1d(conv_input, self._sola_buffer[None, None, :])
        denominator = self._torch.sqrt(functional.conv1d(conv_input ** 2, kernel) + 1e-8)
        offset = int(self._torch.argmax(numerator / denominator).item())
        infer_wav = infer_wav[offset:]
        infer_wav[: self._sola_buffer_frame] *= self._fade_in
        infer_wav[: self._sola_buffer_frame] += self._sola_buffer * self._fade_out
        self._sola_buffer[:] = infer_wav[self.block : self.block + self._sola_buffer_frame]
        output = infer_wav[: self.block].detach().float().cpu().numpy()
        return _validated_audio(output, self.block, label="OUTPUT")

    def reset(self) -> None:
        self._input_wav.zero_()
        self._input_wav_res.zero_()
        self._sola_buffer.zero_()


def create_processor(
    root: str | os.PathLike[str],
    engine: str,
    values: Mapping[str, Any],
    reference: str | os.PathLike[str],
    run_dir: str | os.PathLike[str],
) -> MeanVC2Processor | XVCProcessor | SeedVCProcessor:
    """Create one headless resident processor; no audio device or worker thread is started."""
    root_path = _as_path(root, "AetherTune root")
    run_path = Path(run_dir).expanduser().resolve()
    normalized = str(engine).lower().replace("_", "-")
    values = dict(values or {})
    if normalized == "meanvc2":
        return MeanVC2Processor(root_path, values, Path(reference).expanduser().resolve(), run_path)
    if normalized == "xvc":
        return XVCProcessor(root_path, values, Path(reference).expanduser().resolve(), run_path)
    if normalized == "seed-vc":
        return SeedVCProcessor(root_path, values, Path(reference).expanduser().resolve(), run_path)
    raise ValueError(f"BACKEND_UNAVAILABLE: 未知 streaming engine：{engine}")


__all__ = [
    "HOST_SAMPLE_RATE",
    "MEANVC2_BLOCK",
    "XVC_CODEC_HOP",
    "SEED_VC_ZC",
    "MeanVC2Processor",
    "XVCProcessor",
    "SeedVCProcessor",
    "create_processor",
    "_crossfade_overlap",
    "_validate_xvc_window",
]
