"""彙整同一個 EngineManager 的真正 probe 與基線相容性，不偽造音訊結果。"""
import ctypes
import hashlib
import json
import subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
FOLDER=ROOT/'artifacts/desktop/integration'
kernel=ctypes.WinDLL('kernel32',use_last_error=True)
kernel.OpenProcess.restype=ctypes.c_void_p
kernel.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_ulong]
kernel.CloseHandle.argtypes=[ctypes.c_void_p]


def alive(pid):
    handle=kernel.OpenProcess(0x100000,False,pid)
    if not handle:
        return False
    try:
        return kernel.WaitForSingleObject(handle,0)==258
    finally:
        kernel.CloseHandle(handle)


results=[]
for engine in ('seed-vc','meanvc2','xvc'):
    path=FOLDER/f'{engine}-probe.jsonl'
    events=[json.loads(line) for line in path.read_text(encoding='utf-8-sig').splitlines() if line.strip()]
    final=events[-1]
    pids=[int(e['pid']) for e in events if e.get('type') in ('probe_pid','process_started')]
    survivors=[pid for pid in pids if alive(pid)]
    assert final['value']=='OFFLINE' and not final['service_alive'] and not survivors
    blocked=any(e.get('type')=='state' and e.get('value')=='ERROR' for e in events)
    results.append(dict(engine=engine,process_control='PASS',scope='preflight ERROR + service cleanup' if blocked else 'existing WAV runner start/stop',upstream_start='BLOCKED' if blocked else 'PASS (process only)',realtime_audio='WAITING',pids=pids,survivors=survivors,final=final,log=str(path.relative_to(ROOT))))
paths=['tools/aethertune-ui.py','tools/meanvc2-run.py','tools/xvc-run.py','tools/seed-vc-gui-run.ps1','tools/seed-vc-run.ps1']
baseline=[]
for path in paths:
    old=subprocess.check_output(['git','show',f'HEAD:{path}'],cwd=ROOT)
    current=(ROOT/path).read_bytes()
    # Git working tree 的 CRLF 與 blob LF 不代表語意變更；另以 git diff 確認。
    unchanged=old.replace(b'\r\n',b'\n')==current.replace(b'\r\n',b'\n')
    assert unchanged
    baseline.append(dict(path=path,unchanged=True,sha256=hashlib.sha256(current).hexdigest()))
report=dict(status='PARTIAL',scope='M0 + M1 + M2 skeleton',results=results,existing_runners=baseline)
(FOLDER/'probe-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('PASS: three probe stops + no PID survivors + existing runner baseline unchanged; realtime WAITING')
