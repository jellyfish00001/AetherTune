"""唯讀稽核正式 probe 自己留下的 Windows PID 與 WSL process-group。"""
from __future__ import annotations
import argparse
import json
import subprocess
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("probe", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    events = []
    for line in args.probe.read_text(encoding="utf-8").splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    snapshots = [e["snapshot"] for e in events if e.get("type") in {"initial", "probe_snapshot"}]
    if not snapshots:
        raise RuntimeError("probe 沒有 snapshot")
    session_id = snapshots[0]["session_id"]
    # UUID 只用來解析既有 artifact；不可讓未驗證文字跨出 workspace。
    import uuid
    uuid.UUID(session_id)
    session_dir = root / "artifacts/sessions" / session_id
    windows_pids = {int(s["service_pid"]) for s in snapshots if s.get("service_pid")}
    linux_pids = set()
    for path in (session_dir / "jobs").glob("*/wsl-pid.json"):
        record = json.loads(path.read_text(encoding="utf-8"))
        linux_pids.add(int(record["pid"]))
    for path in session_dir.glob("*.evidence.json"):
        record = json.loads(path.read_text(encoding="utf-8"))
        audit = record.get("pid_audit") or {}
        if audit.get("host_pid"):
            windows_pids.add(int(audit["host_pid"]))
    if any(p <= 0 for p in windows_pids | linux_pids):
        raise RuntimeError("invalid owned PID")
    survivors = []
    if windows_pids:
        # 整數 argv，只有唯讀 Get-Process；沒有名稱掃描或 kill 動作。
        ps_script = "$ErrorActionPreference='SilentlyContinue'; Get-Process -Id " + ",".join(map(str, sorted(windows_pids))) + " | ForEach-Object { $_.Id }; exit 0"
        result = subprocess.run(["powershell.exe", "-NoProfile", "-Command", ps_script], capture_output=True, text=True, timeout=15, check=True)
        survivors.extend({"platform": "windows", "pid": int(line)} for line in result.stdout.splitlines() if line.strip().isdigit())
    if linux_pids:
        # 包含 group leader 消失但 child 尚存的情況；仍僅讀已知 owned group。
        # --exec + Python argv 避免 WSL 預設 shell 提前展開 $pid 而產生假陰性。
        script = "import os,sys,json\nalive=[]\nfor value in sys.argv[1:]:\n p=int(value)\n try:\n  os.killpg(p,0)\n  alive.append(p)\n except ProcessLookupError:\n  pass\nprint(json.dumps(alive))"
        result = subprocess.run(["wsl.exe", "-d", "Ubuntu", "--exec", "/usr/bin/python3", "-c", script, *map(str, sorted(linux_pids))], capture_output=True, text=True, timeout=15, check=True)
        survivors.extend({"platform": "wsl_group", "pid": pid} for pid in json.loads(result.stdout))
    report = {"status": "PASS" if not survivors else "BLOCKED", "session_id": session_id,
              "scope": "read-only audit of this probe's recorded PIDs, not global process inventory",
              "windows_pids": sorted(windows_pids), "wsl_group_ids": sorted(linux_pids), "survivors": survivors}
    (args.probe.parent / "process-audit.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if not survivors else 1


if __name__ == "__main__":
    raise SystemExit(main())
