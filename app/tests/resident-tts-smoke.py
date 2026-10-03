"""Real WSL model reuse smoke. Generates WAVs without opening an audio device."""

from __future__ import annotations

import json
import os
import sys
import threading
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from services.tts.adapters import BreezeAdapter, CosyVoiceAdapter  # noqa: E402


def run_engine(engine: str, profile_id: str, session: Path) -> dict:
    adapter = CosyVoiceAdapter(ROOT) if engine == "cosyvoice" else BreezeAdapter(ROOT)
    profile = json.loads((ROOT / "contracts/voices" / f"{profile_id}.json").read_text(encoding="utf-8"))
    outputs = []
    progress_events = []
    cleanup = None
    try:
        for index, text in enumerate(("今天測試中文語音。", "模型保持載入，第二句直接推論。")):
            request_id = str(uuid.uuid4())
            job_dir = session / "jobs" / request_id
            job_dir.mkdir(parents=True)
            finished = threading.Event()
            def observe():
                while not finished.wait(.2):
                    progress = adapter.get_progress(request_id)
                    if progress:
                        progress_events.append(progress)
            observer = threading.Thread(target=observe, daemon=True)
            observer.start()
            try:
                result = adapter.generate(
                    {"id": request_id, "text": text, "profile_snapshot": profile, "metadata": {}},
                    job_dir / f"{request_id}.wav", job_dir, threading.Event(),
                )
            finally:
                finished.set()
                observer.join(timeout=2)
            manifest = result.evidence["runner_manifest"]["manifest"]
            assert manifest["status"] == "PASS"
            assert manifest["runtime_reused"] is (index == 1), manifest
            assert manifest["output_validation"]["rms"] > 0, manifest
            outputs.append({
                "request_id": request_id, "output": str(result.audio_path),
                "generation_latency_ms": result.metrics["generation_latency_ms"],
                "load_seconds": manifest["load_seconds"],
                "inference_seconds": manifest["inference_seconds"],
                "runtime_reused": manifest["runtime_reused"],
                "worker_token": result.evidence["pid_audit"]["token"],
                "worker_host_pid": result.evidence["pid_audit"]["host_pid"],
                "sha256": result.evidence["output"]["sha256"],
            })
        assert outputs[0]["worker_token"] == outputs[1]["worker_token"]
        assert outputs[0]["worker_host_pid"] == outputs[1]["worker_host_pid"]
        assert any(p['phase'] == 'model_load' for p in progress_events), progress_events
        assert any(p['phase'] == 'generating' and p['runtime_reused'] for p in progress_events), progress_events
        return {"status": "PASS", "engine": engine, "profile": profile_id, "requests": outputs, "progress": progress_events}
    finally:
        cleanup = adapter.close()
        (session / f"{engine}-cleanup.json").write_text(json.dumps(cleanup, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    if os.environ.get("AETHERTUNE_RESIDENT_TTS_SMOKE") != "1":
        raise RuntimeError("此腳本會載入真實模型並生成 WAV；請設定 AETHERTUNE_RESIDENT_TTS_SMOKE=1")
    session = ROOT / "artifacts/sessions" / f"resident-smoke-{uuid.uuid4()}"
    session.mkdir(parents=True)
    report = {"status": "WAITING", "session": str(session), "engines": []}
    try:
        report["engines"].append(run_engine("cosyvoice", "official-cosyvoice-sample", session))
        report["engines"].append(run_engine("breeze", "reference-mandarin-female", session))
        report["status"] = "PASS"
        return 0
    except Exception as exc:
        report["status"] = "FAILED"
        report["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        path = session / "report.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(path, flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
