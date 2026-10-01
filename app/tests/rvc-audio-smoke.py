"""正式 EngineManager 的 RVC CUDA／虛擬線路 smoke；不讀實體麥克風。"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
import numpy as np
import sounddevice as sd
import soundfile as sf

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from services.engines.rvc_runtime import endpoint
from services.tts.playback import SoundDevicePlayback


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--model-id', default='Sage_CN_HeroicFemale')
    parser.add_argument('--f0-method', choices=['fcpe', 'rmvpe'], default='fcpe')
    parser.add_argument('--source', type=Path, default=ROOT/'dataset/reference-voices/voice-male-m1.wav')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--stream-seconds', type=int, default=0)
    parser.add_argument('--monitor', action='store_true')
    parser.add_argument('--postfx', action='store_true', help='驗證共用 EQ／壓縮／殘響與乾濕混合')
    args = parser.parse_args()
    folder = args.output.resolve()
    folder.mkdir(parents=True, exist_ok=True)
    report_path = folder/'report.json'
    # 重跑先清除舊 PASS；裝置／資產失敗也留下本輪判定。
    report_path.write_text(json.dumps({'status':'LOADING','scope':'RVC native smoke in progress'}),encoding='utf-8')
    stream_mode = args.stream_seconds > 0
    # 串流用兩条不同虛擬線路，避免把轉換結果送回來源 CABLE 形成回授。
    output_name = 'Voicemeeter Input (VB-Audio Voicemeeter VAIO)' if stream_mode else 'CABLE Input (VB-Audio Virtual Cable)'
    capture_name = 'Voicemeeter Out B1 (VB-Audio Voicemeeter VAIO)' if stream_mode else 'CABLE Output (VB-Audio Virtual Cable)'
    try:
        capture_index = endpoint(sd, capture_name, 'Windows DirectSound', 'input', 2)
    except Exception as exc:
        report_path.write_text(json.dumps({'status':'BLOCKED','error':str(exc)},ensure_ascii=False),encoding='utf-8')
        print(str(exc))
        return 1
    request = dict(source=str(args.source.resolve()), input='CABLE Output (VB-Audio Virtual Cable)', output=output_name,
                   host_api='Windows DirectSound', parameters={'model_id':args.model_id,'f0_method':args.f0_method,'source_mode':'microphone' if stream_mode else 'file'},
                   monitor={'enabled':args.monitor,'output':'喇叭 (HyperX QuadCast S)','host_api':'MME'},
                   postfx={'enabled':args.postfx,'wet':0.5,'low_db':3,'high_db':-2,'reverb_mix':0.15})
    request_path = folder/'request.json'
    request_path.write_text(json.dumps(request,ensure_ascii=False),encoding='utf-8')
    capture = folder/'capture.wav'
    summary = {'status':'RUNNING','finite':True,'frames':0,'peak':0.0,'squares':0.0,'capture_errors':[]}
    events = []
    running = threading.Event()
    argv = [str(ROOT/'app/src-tauri/target/debug/desktop-probe.exe'),'rvc','180','--request',str(request_path)]
    argv += ['--run-seconds',str(args.stream_seconds)] if stream_mode else ['--complete']
    env = {**os.environ,'PYTHONIOENCODING':'utf-8'}
    process = None
    code = -1
    failure = None
    with sf.SoundFile(capture, mode='w',samplerate=48000,channels=2,subtype='PCM_16') as audio:
        def callback(data, frames, _timing, status):
            summary['frames'] += frames
            summary['peak'] = max(summary['peak'],float(np.max(np.abs(data))))
            summary['squares'] += float(np.sum(data.astype('float64')**2))
            summary['finite'] &= bool(np.isfinite(data).all())
            if status:
                summary['capture_errors'].append(str(status))
            audio.write(data)

        with sd.InputStream(device=capture_index,samplerate=48000,channels=2,dtype='float32',blocksize=960,callback=callback):
            process = subprocess.Popen(argv,cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8')
            def observe():
                with (folder/'probe.jsonl').open('w',encoding='utf-8') as log:
                    for line in process.stdout:
                        log.write(line)
                        log.flush()
                        try:
                            value = json.loads(line)
                            events.append(value)
                            if value.get('type')=='state' and value.get('value')=='RUNNING':
                                running.set()
                        except ValueError:
                            pass
            observer = threading.Thread(target=observe,daemon=True)
            observer.start()
            try:
                if stream_mode:
                    deadline = time.monotonic()+180
                    while not running.wait(0.1):
                        if process.poll() is not None or time.monotonic()>deadline:
                            raise RuntimeError('RVC duplex stream 未進入 RUNNING')
                    playback = SoundDevicePlayback()
                    playback.prepare()
                    playback.play(args.source.resolve(),{'output':'CABLE Input (VB-Audio Virtual Cable)','host_api':'Windows DirectSound'},threading.Event())
                code = process.wait(timeout=240)
            except Exception as exc:
                failure = str(exc)
            finally:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=10)
                observer.join(timeout=5)
            time.sleep(0.3)
    artifacts = [event['path'] for event in events if event.get('type')=='artifact']
    report = json.loads((Path(artifacts[-1])/'rvc-evidence.json').read_text(encoding='utf-8')) if artifacts else {}
    summary['rms'] = (summary.pop('squares')/max(1,summary['frames']*2))**0.5
    summary.update(exit_code=code, error=failure, engine_evidence=report, source_sha256=hashlib.sha256(args.source.read_bytes()).hexdigest(),
                   capture_sha256=hashlib.sha256(capture.read_bytes()).hexdigest(), probe_pid=process.pid,
                   process_pids=[event.get('pid') for event in events if event.get('type') in ('process_started','probe_pid')],
                   scope='native EngineManager + CUDA RVC + explicit virtual capture; physical mic/listening/Discord/LIVE WAITING')
    captured = summary['finite'] and summary['peak']>0.0001 and not summary['capture_errors']
    summary['virtual_capture_status'] = 'PASS' if captured else 'WAITING'
    metrics = report.get('metrics', {})
    duplex = metrics.get('blocks', 0)>=10 and metrics.get('input_peak', 0)>0.0001 and metrics.get('output_peak', 0)>0.0001 and metrics.get('underruns', 1)==0 and metrics.get('overruns', 1)==0 and bool(report.get('callback_sha256'))
    playback = report.get('playback', {})
    monitor_ok = not args.monitor or (report.get('monitor_status')=='stopped' and metrics.get('monitor_frames',0)>0 and metrics.get('monitor_peak',0)>0.0001 and metrics.get('monitor_underruns',1)==0 and metrics.get('monitor_drops',1)==0 if stream_mode else playback.get('monitor_status')=='completed' and playback.get('monitor_frames_written',0)>0 and playback.get('monitor_underrun_count',1)==0)
    summary['status']='PASS' if code==0 and report.get('status') in ('PASS','STOPPED') and (duplex if stream_mode else captured) and monitor_ok else 'BLOCKED'
    if stream_mode:
        summary['scope']='native EngineManager + injected virtual input + CUDA RVC duplex callback; independent B1 capture reported separately; physical mic/listening/Discord/LIVE WAITING'
    report_path.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({key:value for key,value in summary.items() if key!='engine_evidence'},ensure_ascii=False,indent=2))
    print(json.dumps({'engine_status':report.get('status'),'runtime':report.get('runtime'),'metrics':report.get('metrics'),
                      'p50_ms':report.get('p50_ms'),'p95_ms':report.get('p95_ms'),'error':report.get('error')},ensure_ascii=False))
    return 0 if summary['status']=='PASS' else 1


if __name__=='__main__':
    raise SystemExit(main())
