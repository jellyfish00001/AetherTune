"""各隔離環境共用的唯讀 Python 3.10 / dependencies / CUDA 檢查。"""
import argparse
import importlib.metadata as metadata
import json
import subprocess
import sys

parser = argparse.ArgumentParser()
parser.add_argument('--backend', required=True)
args = parser.parse_args()
result = {'backend': args.backend, 'python': sys.version.split()[0], 'executable': sys.executable,
          'version_ok': sys.version_info[:2] == (3, 10), 'packages': {}}
try:
    for name in ('torch', 'torchaudio', 'numpy', 'scipy', 'gradio', 'ctranslate2'):
        try:
            result['packages'][name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            pass
    if args.backend == 'stt':
        import ctranslate2
        result['cuda_available'] = ctranslate2.get_cuda_device_count() > 0
    else:
        import torch
        result.update(cuda_available=torch.cuda.is_available(), cuda=torch.version.cuda,
                      gpu=torch.cuda.get_device_name(0) if torch.cuda.is_available() else None)
    if args.backend == 'seed-vc':
        import tkinter
        root = tkinter.Tk()
        root.withdraw()
        result['tk'] = root.tk.call('info', 'patchlevel')
        root.destroy()
    check = subprocess.run([sys.executable, '-m', 'pip', 'check'], capture_output=True, text=True)
    result.update(pip_check_exit=check.returncode, pip_check=(check.stdout + check.stderr).strip())
    result['status'] = 'PASS' if result['version_ok'] and result['cuda_available'] and check.returncode == 0 else 'BLOCKED'
except Exception as exc:
    result.update(status='BLOCKED', error=str(exc))
print(json.dumps(result, ensure_ascii=False))
sys.exit(0 if result['status'] == 'PASS' else 2)
