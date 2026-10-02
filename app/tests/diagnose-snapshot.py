"""同一 fixture 交錯 A/A 與 A/B，診斷 wall／thread CPU／GC；不啟動模型或音訊。"""
import argparse
import gc
import hashlib
import importlib.util
import json
import math
import random
import shutil
import statistics
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('storage_baseline', ROOT / 'app/tests/baseline-storage.py')
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--fixture-report', type=Path, required=True,
                    help='baseline-storage 產生的 PASS report.json；只接受 repo artifacts 內合成資料')
parser.add_argument('--compare-snapshot-ref', required=True)
parser.add_argument('--output', type=Path)
args = parser.parse_args()
artifact_root = (ROOT / 'artifacts').resolve()
fixture_report = args.fixture_report.resolve()
out = (args.output or artifact_root / 'desktop' / f'snapshot-control-{uuid.uuid4()}').resolve()
if not fixture_report.is_relative_to(artifact_root) or not fixture_report.is_file():
    parser.error('--fixture-report 必須是 artifacts 內的既有檔案')
if not out.is_relative_to(artifact_root) or out == artifact_root or out.exists():
    parser.error('--output 必須是 artifacts 內尚不存在的子目錄')
fixture = json.loads(fixture_report.read_text(encoding='utf-8'))
if fixture.get('status') != 'PASS' or fixture.get('scope') != 'synthetic SQLite/export/service snapshot; no audio, no model':
    parser.error('只接受通過的 synthetic baseline-storage report')
cases = fixture['cases']
if sorted((c['rows'], c['repeat']) for c in cases) != [(n, r) for n in (10, 100, 1000) for r in (1, 2, 3)]:
    parser.error('fixture 必須包含 10／100／1000 各 3 個案例')
sources = []
for entry in cases:
    source = (ROOT / entry['case']).resolve()
    if not source.is_relative_to(artifact_root) or not source.is_dir():
        parser.error('fixture case 必須位於 artifacts')
    if out.is_relative_to(source):
        parser.error('輸出不可位於來源 fixture 內，以免遞迴複製')
    # 只從已驗證的合成 DB 複製；不接受接到外部資料的 symlink／junction。
    for path in source.rglob('*'):
        if not path.resolve().is_relative_to(source):
            parser.error('fixture 不可包含指向案例外的路徑')
    sources.append((entry, source))
before, identity = bench.snapshot_baseline(args.compare_snapshot_ref)
out.mkdir(parents=True)
active_gc = None
gc_start = {}

def on_gc(phase, info):
    generation = info['generation']
    if phase == 'start':
        gc_start[generation] = time.perf_counter_ns()
    elif active_gc is not None:
        active_gc.append({'generation': generation, 'ms': (time.perf_counter_ns()-gc_start[generation])/1e6})

def measure(call):
    global active_gc
    active_gc = []
    cpu = time.thread_time_ns()
    start = time.perf_counter_ns()
    value = call()
    wall = (time.perf_counter_ns()-start)/1e6
    cpu = (time.thread_time_ns()-cpu)/1e6
    events = active_gc
    active_gc = None
    return value, {'wall_ms': wall, 'thread_cpu_ms': cpu, 'gc': events}

def summary(samples):
    result = {}
    for key in ('wall_ms', 'thread_cpu_ms'):
        values = [s[key] for s in samples]
        result[key] = {'median': statistics.median(values), 'p95': sorted(values)[math.ceil(.95*len(values))-1]}
    result['gc_calls'] = sum(bool(s['gc']) for s in samples)
    result['gc_ms'] = sum(e['ms'] for s in samples for e in s['gc'])
    return result

report = {'status': 'RUNNING', 'scope': 'synthetic snapshot diagnostic; production GC enabled; no audio/model',
          'started_at': datetime.now(timezone.utc).isoformat(), 'before': identity,
          'head': subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
          'samples_per_label': 100, 'seed': 731, 'cases': [], 'source_sha256': {},
          'fixture_report': str(fixture_report.relative_to(ROOT)),
          'fixture_report_sha256': hashlib.sha256(fixture_report.read_bytes()).hexdigest(),
          'gc_thresholds': gc.get_threshold(),
          'thread_cpu_clock': vars(time.get_clock_info('thread_time')),
          'limits': ['宿主機負載未受控', 'GC callback 額外負擔不等於無 instrumentation 的 latency',
                     'A/A p95 超過門檻時不得宣稱 A/B 效能通過']}
for name in ('services/tts/service.py','services/tts/snapshot.py','services/tts/validation.py',
             'services/tts/storage.py','app/tests/baseline-storage.py','app/tests/diagnose-snapshot.py'):
    report['source_sha256'][name] = hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
gc.callbacks.append(on_gc)
try:
    for entry, source in sources:
        count, repeat = entry['rows'], entry['repeat']
        case = out/f'rows-{count}-run-{repeat}'
        shutil.copytree(source,case)
        service = bench.SpeechService(case,session_id='synthetic-baseline',adapters={
            'cosyvoice':bench.NoGeneration(),'breeze':bench.NoGeneration()},playback=bench.NullPlayback())
        try:
            records = service._store.list_requests()
            assert len(records)==count and all(r['metadata']['benchmark_synthetic'] for r in records)
            with service._lock:
                service._requests.update((r['id'],r) for r in records)
            old,new = before(service),service.snapshot
            for _ in range(10): assert old()==new()
            modes = {'aa_old': (old,old), 'aa_new': (new,new), 'ab': (old,new)}
            samples = {m: {'before':[],'after':[]} for m in modes}
            rng = random.Random(731+count+repeat)
            for index in range(100):
                order = list(modes); rng.shuffle(order)
                for mode in order:
                    values = {}
                    for label in (('before','after') if index%2==0 else ('after','before')):
                        call = modes[mode][label=='after']
                        values[label], sample = measure(call)
                        sample['pair'] = index
                        samples[mode][label].append(sample)
                    assert values['before']==values['after']
            result = {'rows':count,'repeat':repeat,'payload_equal':True,'samples':samples,
                      'summary':{m:{k:summary(v) for k,v in labels.items()} for m,labels in samples.items()}}
        finally:
            service.close()
            assert not service._worker.is_alive()
        report['cases'].append(result)
        (out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps({'rows':count,'repeat':repeat,'summary':result['summary']}),flush=True)
    report['status']='PASS'
except BaseException as exc:
    report.update(status='FAILED', error=f'{type(exc).__name__}: {exc}')
    raise
finally:
    gc.callbacks.remove(on_gc)
    report['finished_at']=datetime.now(timezone.utc).isoformat()
    (out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
