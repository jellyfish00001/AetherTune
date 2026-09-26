"""兩個推論 wrapper 共用的精簡 WAV 證據；不判定人工音質或 LIVE。"""
import hashlib
import json
import subprocess
from pathlib import Path
import numpy as np
import soundfile as sf
import torch

ROOT = Path(__file__).resolve().parents[1]

def hash_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()

def audio(path):
    values, rate = sf.read(path, always_2d=True)
    return {'path': str(path), 'sha256': hash_file(path), 'sample_rate': rate,
            'seconds': len(values) / rate, 'finite': bool(np.isfinite(values).all()),
            'rms': float(np.sqrt(np.mean(values ** 2))), 'peak': float(np.max(np.abs(values))),
            'clipping_ratio': float(np.mean(np.abs(values) >= .999))}

def write_evidence(backend, source, target, outputs, models, repo, devices, settings, elapsed, evidence_name='run-evidence.json'):
    metrics = [audio(path) for path in outputs]
    passed = bool(metrics) and all(x['finite'] and x['rms'] > 1e-4 and x['seconds'] > .5 for x in metrics)
    report = {'status': 'PASS' if passed else 'BLOCKED', 'backend': backend,
              'scope': 'file-driven CUDA conversion; microphone/rack/600s/human listening WAITING',
              'source': audio(source), 'reference': audio(target), 'outputs': metrics,
              'code_revision': subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip(),
              'models': [{'path': str(p), 'sha256': hash_file(p)} for p in models],
              'devices': devices, 'gpu': torch.cuda.get_device_name(0), 'torch': torch.__version__,
              'cuda': torch.version.cuda, 'settings': settings, 'load_and_inference_seconds': elapsed}
    evidence = Path(outputs[0]).parent / evidence_name
    evidence.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"{report['status']}: {evidence}", flush=True)
    if not passed:
        raise SystemExit('輸出音訊未通過 finite／RMS／duration 檢查')
