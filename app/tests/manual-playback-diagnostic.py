"""短 WAV 的跨程序 capture／worker playback；不執行模型。"""
from __future__ import annotations
import argparse
import faulthandler
import json
import os
from pathlib import Path
import subprocess
import sys
import sysconfig
from threading import Event, Thread
import time


def child(source: Path) -> int:
    from services.tts.playback import SoundDevicePlayback
    faulthandler.dump_traceback_later(10, repeat=True)
    playback = SoundDevicePlayback()
    print('stage: prepare on main thread', flush=True)
    playback.prepare()
    print('stage: worker playback', flush=True)
    outcome = {}
    def play():
        try:
            result = playback.play(source, {'output': 'CABLE Input (VB-Audio Virtual Cable)', 'host_api': 'Windows DirectSound'}, Event())
            outcome.update(status='PASS', result=vars(result))
        except Exception as exc:
            outcome.update(status='BLOCKED', error=str(exc))
    worker = Thread(target=play, daemon=True)
    worker.start()
    worker.join(timeout=20)
    if worker.is_alive():
        print('BLOCKED: worker timeout', flush=True)
        return 1
    faulthandler.cancel_dump_traceback_later()
    print(json.dumps(outcome, ensure_ascii=False), flush=True)
    return 0 if outcome.get('status') == 'PASS' else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=Path)
    parser.add_argument('--child', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.child:
        return child(args.source.resolve())
    import numpy as np
    import sounddevice as sd
    import soundfile as sf
    folder = args.output.resolve()
    folder.mkdir(parents=True, exist_ok=True)
    devices, apis = sd.query_devices(), sd.query_hostapis()
    matches = [i for i,d in enumerate(devices) if d['name']=='CABLE Output (VB-Audio Virtual Cable)' and apis[d['hostapi']]['name']=='Windows DirectSound' and d['max_input_channels']>=2]
    if len(matches)!=1:
        raise RuntimeError(f'capture endpoint mismatch: {matches}')
    summary = {'frames': 0, 'peak': 0.0, 'squares': 0.0, 'finite': True, 'errors': []}
    with sf.SoundFile(folder/'capture.wav', mode='w', samplerate=48000, channels=2, subtype='PCM_16') as audio:
        def callback(data, frames, timing, status):
            summary['frames'] += frames
            summary['peak'] = max(summary['peak'], float(np.max(np.abs(data))))
            summary['squares'] += float(np.sum(data.astype(np.float64)**2))
            summary['finite'] &= bool(np.isfinite(data).all())
            if status:
                summary['errors'].append(str(status))
            audio.write(data)
        # 直接執行 base Python 並提供既有 venv site-packages，避免 venv shim
        # 產生另一個未知 child；timeout 僅終止本次 Popen 的確定 PID。
        env = os.environ.copy()
        root = Path(__file__).resolve().parents[2]
        env['PYTHONPATH'] = str(root)
        env['PYTHONIOENCODING'] = 'utf-8'
        with sd.InputStream(device=matches[0], samplerate=48000, channels=2, dtype='float32', blocksize=960, callback=callback):
            with (folder/'child.log').open('w', encoding='utf-8') as log:
                bootstrap = "import sys,runpy;sys.path.append(sys.argv.pop(1));runpy.run_path(sys.argv.pop(1),run_name='__main__')"
                process = subprocess.Popen([sys._base_executable, '-u', '-c', bootstrap, sysconfig.get_path('purelib'), str(Path(__file__).resolve()), str(args.source.resolve()), '--child'], cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT)
                try:
                    code = process.wait(timeout=60)
                    time.sleep(0.3)
                except subprocess.TimeoutExpired:
                    process.terminate()
                    process.wait(timeout=5)
                    code = -1
    summary['rms'] = (summary.pop('squares')/max(1,summary['frames']*2))**0.5
    summary.update(status='PASS' if code==0 and summary['finite'] and summary['peak']>0.0001 and not summary['errors'] else 'BLOCKED', exit_code=code, child_pid=process.pid, source=str(args.source.resolve()), scope='existing real WAV replay on worker, separate CABLE capture; no new generation')
    (folder/'report.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary['status']=='PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
