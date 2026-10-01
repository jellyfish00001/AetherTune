"""TTS 完整 WAV 的共用音效；保留原始生成檔，主輸出與監聽播放同一份結果。"""
from __future__ import annotations

import hashlib
from pathlib import Path
from threading import Event
import time

from services.engines.postfx import PostFx, validate_postfx
from services.tts.playback import PlaybackCancelled, PlaybackError


def render_postfx(source: Path, output: Path, settings: dict, cancel: Event) -> tuple[Path, dict]:
    settings = validate_postfx(settings)
    evidence = {"settings": settings, "enabled": settings["enabled"], "source_path": str(source)}
    if not settings["enabled"]:
        return source, {**evidence, "output_path": str(source), "seconds": 0.0}
    import numpy as np
    import soundfile as sf

    def digest(path):
        value = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                value.update(chunk)
        return value.hexdigest()

    started = time.perf_counter()
    try:
        with sf.SoundFile(source) as reader:
            if not reader.frames or reader.samplerate <= 8000:
                raise PlaybackError("POSTFX_INVALID: 音效需要非空且取樣率大於 8 kHz 的 WAV")
            processors = [PostFx(reader.samplerate, settings) for _ in range(reader.channels)]
            with sf.SoundFile(output, "w", samplerate=reader.samplerate, channels=reader.channels, subtype="FLOAT") as writer:
                # 固定大小處理、跨 block 保存 filter state；取消可在下一個 block 生效。
                for block in reader.blocks(blocksize=4096, dtype="float32", always_2d=True):
                    if cancel.is_set():
                        raise PlaybackCancelled("Post-FX cancelled")
                    rendered = np.column_stack([processor.process(block[:, channel]) for channel, processor in enumerate(processors)])
                    writer.write(rendered)
            evidence.update(sample_rate=reader.samplerate, channels=reader.channels, frames=reader.frames)
    except (PlaybackCancelled, PlaybackError):
        raise
    except Exception as exc:
        raise PlaybackError(f"POSTFX_FAILED: {exc}") from exc
    return output, {**evidence, "output_path": str(output), "source_sha256": digest(source),
                    "output_sha256": digest(output), "seconds": round(time.perf_counter() - started, 4)}
