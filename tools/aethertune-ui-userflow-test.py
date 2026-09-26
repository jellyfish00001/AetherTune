"""真實 Tk buttons 與 backend 子程序整合測試；不用 mock 模型。"""
import argparse
import importlib.util
import json
from pathlib import Path
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--backend', choices=['mean','xvc','seed','stop'], required=True)
parser.add_argument('--output', type=Path)
parser.add_argument('--seed-wait', type=int, default=170)
args = parser.parse_args()
spec = importlib.util.spec_from_file_location('aethertune_ui', ROOT / 'tools/aethertune-ui.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
app = module.App()
results = args.output or ROOT / 'artifacts/ui-tests' / str(uuid.uuid4())
results.mkdir(parents=True, exist_ok=False)
print(f'UI test report directory: {results}', flush=True)
started = time.monotonic()
launched = False
stopped = False
backend = 'mean' if args.backend == 'stop' else args.backend
app.vars['backend'].set(next(label for label, key in module.BACKENDS.items() if key == backend))
app._refresh_form()
app.vars['source'].set(str(ROOT / 'dataset/reference-voices/voice-male-m1.wav'))
app.vars['reference'].set(str(ROOT / 'dataset/reference-voices/voice-female-f1.wav'))
app.vars['mean_model'].set('120ms')

def tick():
    global launched, stopped
    elapsed = time.monotonic() - started
    if elapsed > 240:
        (results / 'timeout.txt').write_text('UI 測試超過 240 秒', encoding='utf-8')
        app.close()
        return
    if not launched and app.audio_inventory is not None:
        if backend == 'seed':
            app.vars['host_api'].set('MME')
            app._update_device_choices()
            for direction, token in [('input','HyperX QuadCast S'), ('output','CABLE Input')]:
                label = next(label for label,row in app.device_by_label[direction].items() if token in row['name'])
                app.vars[f'{direction}_device'].set(label)
        app.widgets['start'].invoke()
        launched = True
    if launched and args.backend == 'stop' and not stopped and elapsed > 4:
        app.widgets['stop'].invoke()
        stopped = True
    if launched and args.backend == 'seed' and elapsed > args.seed_wait and not stopped:
        # 官方 GUI 已有獨立 callback/loopback harness；此案驗 launcher 與設定，再停止。
        app.widgets['stop'].invoke()
        stopped = True
    if launched and app.last_result is not None:
        report = {'backend': args.backend, 'elapsed': elapsed, 'returncode': app.last_process_returncode,
                  'result': app.last_result, 'status': app.status_var.get(),
                  'run_directory': str(app.run_directory), 'settings': {key:var.get() for key,var in app.vars.items()},
                  'reference_widget_visible': bool(app.widgets['reference_entry'].winfo_ismapped()),
                  'geometry': app.root.winfo_geometry(), 'screen': [app.root.winfo_screenwidth(),app.root.winfo_screenheight()],
                  'start_position': [app.widgets['start'].winfo_rootx(), app.widgets['start'].winfo_rooty()],
                  'open_wav_enabled': str(app.widgets['open_wav'].cget('state')) == 'normal'}
        (results / f'{args.backend}-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2),encoding='utf-8')
        (results / f'{args.backend}-ui.log').write_text(app.widgets['log'].get('1.0','end'),encoding='utf-8')
        print(json.dumps(report,ensure_ascii=False),flush=True)
        app.root.after(18000,app.close)
        return
    app.root.after(150,tick)

app.root.after(300,tick)
app.run()
report_path = results / f'{args.backend}-report.json'
if not report_path.exists():
    raise SystemExit(2)
report = json.loads(report_path.read_text(encoding='utf-8'))
expected = 'STOPPED' if args.backend in ('stop','seed') else 'PASS'
raise SystemExit(0 if report['result']['status'] == expected else 2)
