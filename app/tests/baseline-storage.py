"""量測真實 SQLite／export／snapshot 程式；資料為隔離的合成 fixture，沒有模型或音訊。"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import sqlite3
import statistics
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from services.tts.playback import NullPlayback  # noqa: E402
from services.tts.service import SpeechService  # noqa: E402

TEXT = "這是隔離的資料效能測試，沒有生成或播放語音。"
STAMP = "2026-10-01T00:00:00.000Z"
ROUTE = {"output": "Synthetic benchmark output", "host_api": "No audio device"}


class NoGeneration:
    def readiness(self) -> dict:
        return {"preflight_valid": False, "state": "WAITING", "errors": ["synthetic storage baseline"]}

    def generate(self, *args, **kwargs):
        raise AssertionError("儲存量測禁止執行 generation")


def timed(call, repeats: int = 5) -> tuple[object, dict]:
    samples = []
    result = None
    for _ in range(repeats):
        start = time.perf_counter_ns()
        result = call()
        samples.append((time.perf_counter_ns() - start) / 1_000_000)
    return result, {"samples_ms": samples, "median_ms": statistics.median(samples)}


def run_case(output: Path, count: int, repeat: int) -> dict:
    case = output / f"rows-{count}-run-{repeat}"
    case.mkdir()
    # catalogue 保持真實欄位大小；WAV／weights 不複製，也不讀使用者 DB。
    shutil.copytree(ROOT / "contracts/voices", case / "contracts/voices")
    service = SpeechService(case, session_id="synthetic-baseline",
                            adapters={"cosyvoice": NoGeneration(), "breeze": NoGeneration()},
                            playback=NullPlayback())
    completed_samples = []
    try:
        for index in range(count):
            request = {
                "id": f"fixture-{index:06d}", "session_id": service.session_id,
                "created_at": STAMP, "status": "completed", "source": "manual", "text": TEXT,
                "engine_id": "cosyvoice", "voice_profile_id": "official-cosyvoice-sample",
                "profile_snapshot": service._profiles_by_id["official-cosyvoice-sample"],
                "route_snapshot": ROUTE, "metadata": {"benchmark_synthetic": True},
                "metrics": {},
            }
            service._store.save_request(request)
            # 僅注入 terminal history；不 submit、不排入 worker，不將 fixture 視為音訊完成。
            with service._lock:
                service._requests[request["id"]] = request
            _, sample = timed(lambda: service._store.record_completed(
                request, started_at=STAMP, ended_at=STAMP, metrics={}, route=ROUTE), repeats=1)
            completed_samples.append(sample["samples_ms"][0])
        requests, request_query = timed(service._store.list_requests)
        transcripts, transcript_query = timed(service._store.list_transcripts)
        _, export = timed(service._store.export_session)
        snapshot, snapshot_timing = timed(service.snapshot)
        serialized, serialization = timed(lambda: json.dumps(snapshot, ensure_ascii=False))
        assert len(requests) == len(transcripts) == len(snapshot["snapshot"]["queue"]) == count
        assert len(snapshot["snapshot"]["transcript"]) == count
        result = {
            "rows": count, "repeat": repeat, "case": str(case.relative_to(ROOT)),
            "record_completed_including_export_ms": completed_samples,
            "request_query": request_query, "transcript_query": transcript_query,
            "export": export, "snapshot": snapshot_timing, "json_serialization": serialization,
            "snapshot_utf8_bytes": len(serialized.encode("utf-8")),
            "row_counts_verified": True,
        }
    finally:
        service.close()
        assert not service._worker.is_alive(), "fixture worker 未回收"

    # close() 會寫入 session ended_at；驗證與 hash 必須在最後一次 export 之後。
    session_dir = service._store.session_dir
    with sqlite3.connect(service._store.db_path.as_uri() + "?mode=ro", uri=True) as db:
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        request_ids = {row[0] for row in db.execute("SELECT request_id FROM speech_requests")}
        transcript_ids = {row[0] for row in db.execute("SELECT request_id FROM transcripts")}
        assert len(request_ids) == len(transcript_ids) == count
        assert request_ids == transcript_ids
    for filename, key in (("requests.jsonl", "id"), ("transcript.jsonl", "request_id")):
        rows = [json.loads(line) for line in (session_dir / filename).read_text(encoding="utf-8").splitlines()]
        assert len(rows) == count and {row[key] for row in rows} == request_ids
        assert all(row["text"] == TEXT for row in rows)
    assert len((session_dir / "transcript.txt").read_text(encoding="utf-8").splitlines()) == count
    assert json.loads((session_dir / "session.json").read_text(encoding="utf-8"))["ended_at"]
    assert not (session_dir / "export_error.json").exists(), "export failure 不可視為成功樣本"
    result["exports"] = {p.name: {"bytes": p.stat().st_size,
                                 "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                         for p in sorted(session_dir.glob("*"))}
    result["db_export_verified"] = True
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = (args.output or ROOT / "artifacts/desktop" / f"storage-baseline-{uuid.uuid4()}").resolve()
    # 只容許全新 artifacts 子目錄；不覆寫舊 evidence 或碰 canonical 使用者 DB。
    if not output.is_relative_to((ROOT / "artifacts").resolve()) or output.exists():
        parser.error("--output 必須是 artifacts 內尚未存在的子目錄")
    output.mkdir(parents=True)
    sources = [Path(__file__), ROOT / "services/tts/service.py", ROOT / "services/tts/storage.py"]
    sources.extend(sorted((ROOT / "contracts/voices").glob("*.json")))
    report = {
        "status": "RUNNING", "scope": "synthetic SQLite/export/service snapshot; no audio, no model",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "source_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
        "python": sys.version, "platform": platform.platform(), "text": TEXT,
        "text_sha256": hashlib.sha256(TEXT.encode("utf-8")).hexdigest(),
        "cases": [], "limits": ["模型、裝置、UI rendering、CPU/RSS、IPC transport 未量測",
                                 "catalogue 真實，request／transcript 是合成資料；readiness 為 stub"],
    }
    try:
        for count in (10, 100, 1000):
            for repeat in range(1, 4):
                case = run_case(output, count, repeat)
                report["cases"].append(case)
                (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
                print(json.dumps({"rows": count, "repeat": repeat, "snapshot_ms": case["snapshot"]["median_ms"],
                                  "export_ms": case["export"]["median_ms"], "bytes": case["snapshot_utf8_bytes"]}), flush=True)
        report["status"] = "PASS"
    except Exception as exc:
        report.update(status="FAILED", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(output / "report.json", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
