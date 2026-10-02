"""量測真實 SQLite／export／snapshot 程式；資料為隔離的合成 fixture，沒有模型或音訊。"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import shutil
import sqlite3
import statistics
import subprocess
import sys
import time
import types
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


def snapshot_baseline(ref: str) -> tuple[object, dict]:
    revision = subprocess.check_output(["git", "rev-parse", "--verify", f"{ref}^{{commit}}"],
                                       cwd=ROOT, text=True).strip()
    source = subprocess.check_output(["git", "show", f"{revision}:services/tts/service.py"], cwd=ROOT)
    # 凍結 service class，避免舊 snapshot 誤用目前已搬移或修改的 private helpers。
    # module 不執行 main；比較物件不跑 constructor、不擁有 worker／DB，僅共讀 fixture。
    module = types.ModuleType(f"services.tts._snapshot_baseline_{revision}")
    module.__package__ = "services.tts"
    module.__file__ = f"git:{revision}:services/tts/service.py"
    exec(compile(source, module.__file__, "exec"), module.__dict__)
    # 舊 class 若反向載入目前的 projection，便不是隔離的 before；明確拒絕誤比。
    if "project_queue" in module.__dict__ or "project_profile" in module.__dict__:
        raise ValueError("此基準已依賴 snapshot 模組；需先隔離該版本依賴，不能套用目前的 projection")
    def bind(service):
        view = object.__new__(module.SpeechService)
        view.__dict__ = service.__dict__
        return view.snapshot
    return bind, {"revision": revision, "service_source_sha256": hashlib.sha256(source).hexdigest(),
                  "scope": "frozen service class snapshot/helpers; shared read-only fixture; other dependencies current"}


def compare_snapshot(service: SpeechService, baseline, sample_count: int) -> dict:
    calls = {"before": baseline(service), "after": service.snapshot}
    assert calls["before"]() == calls["after"]()  # 先暖機；完整公開 payload 必須一致。
    samples = {"before": [], "after": []}
    for index in range(sample_count):
        values = {}
        for name in (("before", "after") if index % 2 == 0 else ("after", "before")):
            values[name], timing = timed(calls[name], repeats=1)
            samples[name].append(timing["samples_ms"][0])
        assert values["before"] == values["after"], "snapshot payload 不相容"
    result = {name: {"samples_ms": values, "median_ms": statistics.median(values),
                     "p95_ms": sorted(values)[math.ceil(sample_count * 0.95) - 1]}
              for name, values in samples.items()}
    result["median_reduction_percent"] = 100 * (1 - result["after"]["median_ms"] / result["before"]["median_ms"])
    result["payload_equal"] = True
    result["samples_per_variant"] = sample_count
    return result


def run_case(output: Path, count: int, repeat: int, baseline=None, comparison_samples: int = 20) -> dict:
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
        if baseline is not None:
            result["snapshot_comparison"] = compare_snapshot(service, baseline, comparison_samples)
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
    parser.add_argument("--compare-snapshot-ref", help="在同一 fixture 比較指定 commit 的 service class snapshot／helpers")
    parser.add_argument("--comparison-samples", type=int, default=20,
                        help="每案例、每版本的 warm 樣本數（至少 20，預設 20）")
    args = parser.parse_args()
    if args.comparison_samples < 20:
        parser.error("--comparison-samples 不得小於 20")
    if args.comparison_samples != 20 and not args.compare_snapshot_ref:
        parser.error("--comparison-samples 需搭配 --compare-snapshot-ref")
    output = (args.output or ROOT / "artifacts/desktop" / f"storage-baseline-{uuid.uuid4()}").resolve()
    # 只容許全新 artifacts 子目錄；不覆寫舊 evidence 或碰 canonical 使用者 DB。
    if not output.is_relative_to((ROOT / "artifacts").resolve()) or output.exists():
        parser.error("--output 必須是 artifacts 內尚未存在的子目錄")
    baseline, comparison = snapshot_baseline(args.compare_snapshot_ref) if args.compare_snapshot_ref else (None, None)
    output.mkdir(parents=True)
    sources = [Path(__file__), ROOT / "services/tts/service.py", ROOT / "services/tts/storage.py"]
    sources.append(ROOT / "services/tts/snapshot.py")
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
    if comparison is not None:
        report["snapshot_comparison"] = comparison
    try:
        for count in (10, 100, 1000):
            for repeat in range(1, 4):
                case = run_case(output, count, repeat, baseline, args.comparison_samples)
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
