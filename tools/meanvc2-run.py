"""精簡 MeanVC2 adapter：使用固定 upstream runtime，不改第三方程式。"""
from pathlib import Path
import argparse
import importlib.util
import sys
import time
from streaming_backend_evidence import write_evidence

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--source', type=Path)
    mode.add_argument('--realtime', action='store_true', help='官方互動式裝置選擇與麥克風模式')
    parser.add_argument('--target', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--model', choices=['120ms', '40ms'], default='40ms')
    args = parser.parse_args()
    if args.source and args.output is None:
        parser.error('file 模式需要 --output')
    repo = ROOT / 'tools/external/MeanVC2'
    assets = ROOT / 'models/meanvc2'
    sys.path.insert(0, str(repo / 'runtime'))
    spec = importlib.util.spec_from_file_location('meanvc2_runtime', repo / 'runtime/run_rt.py')
    runtime = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runtime)
    # 上游路徑常數轉向本機模型目錄，第三方 checkout 保持乾淨。
    runtime.VOCODER_PATH = str(assets / 'vocos.pt')
    runtime.SPEAKER_MODEL_PATH = str(assets / 'wavlm_large_finetune.pth')
    runtime.WAVLM_CONFIG_PATH = str(assets / 'wavlm_large_cfg.pt')
    for name, paths in runtime.MODEL_PATHS.items():
        paths['ckpt'] = str(assets / f'meanvc2_{name}_40ms.safetensors')
        paths['asr_ckpt'] = str(assets / ('fastu2pp_80ms.pt' if name == '40ms' else 'fastu2pp_160ms.pt'))
    if args.output:
        output = args.output.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    runner = runtime.VCRunner(str(args.target.resolve()), 'cuda', args.model)
    print(f'Model load seconds: {time.perf_counter()-started:.3f}', flush=True)
    if args.realtime:
        runtime.run_realtime(runner)
    else:
        runner.process_file(str(args.source.resolve()), str(output))
        elapsed = time.perf_counter() - started
        devices = {name: str(next(module.parameters()).device) for name, module in
                   [('vc', runner.vc), ('speaker', runner.spk_model), ('asr', runner.asr), ('vocoder', runner.vocoder)]}
        write_evidence('meanvc2', args.source.resolve(), args.target.resolve(), [output],
                       [Path(runtime.MODEL_PATHS[args.model]['ckpt']), assets / 'vocos.pt', assets / 'wavlm_large_finetune.pth'],
                       repo, devices, {'model': args.model, 'mode': 'file-driven streaming'}, elapsed,
                       evidence_name=f'{output.stem}.run-evidence.json')

if __name__ == '__main__':
    main()
