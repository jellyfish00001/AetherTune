"""X-VC 本機 CUDA 推論；設定副本保存在 artifacts，不修改官方 checkout。"""
from pathlib import Path
import argparse
import os
import runpy
import sys
import yaml
import torch
import time
from streaming_backend_evidence import write_evidence

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--target', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--current', type=int, default=160, help='0 為 offline；正數為 streaming current 毫秒')
    parser.add_argument('--chunk', type=int, default=2400, help='streaming chunk 毫秒')
    parser.add_argument('--future', type=int, default=80, help='streaming future 毫秒')
    parser.add_argument('--smooth', type=int, default=20, help='streaming smooth 毫秒')
    args = parser.parse_args()
    if args.current < 0:
        parser.error('--current 不可小於 0')
    if args.chunk <= 0:
        parser.error('--chunk 必須大於 0')
    if args.future < 0 or args.smooth < 0:
        parser.error('--future 與 --smooth 不可小於 0')
    if args.current > 0 and args.smooth > args.current:
        parser.error('streaming 的 --smooth 不可大於 --current')
    if args.current > 0 and args.current + args.future + args.smooth > args.chunk:
        parser.error('streaming 視窗需滿足 current + future + smooth <= chunk')
    repo = ROOT / 'tools/external/X-VC'
    assets = ROOT / 'models/xvc'
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if list(output.glob('*.wav')):
        parser.error('輸出目錄已有 WAV；請使用新目錄，避免舊結果混入證據')
    config = yaml.safe_load((repo / 'configs/xvc.yaml').read_text(encoding='utf-8'))
    gen = config['model']['generator']
    # 推論不建立 training loss 或 DeepSpeed；直接使用官方 inference CLI。
    gen['loss_config'] = None
    gen['speaker_encoder']['pretrained_dir'] = str(assets / 'eres2net')
    gen['semantic_encoder']['encoder']['from_pretrained']['local_ckpt'] = str(assets / 'glm-tokenizer')
    gen['semantic_encoder']['cfg']['local_ckpt'] = str(assets / 'glm-tokenizer')
    config_path = output / 'xvc-local.yaml'
    config_path.write_text(yaml.safe_dump(config, allow_unicode=True), encoding='utf-8')
    torch.set_num_threads(4)
    sys.path.insert(0, str(repo))
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    from bins import infer_utils
    original_load = infer_utils.load_xvc
    devices = {}
    def observed_load(*positional, **kwargs):
        config, model, device = original_load(*positional, **kwargs)
        devices['model'] = str(next(model.parameters()).device)
        return config, model, device
    infer_utils.load_xvc = observed_load
    sys.argv = ['infer_single', '--config', str(config_path), '--ckpt', str(assets / 'xvc.pt'),
                '--source_wav_path', str(args.source.resolve()), '--target_wav_path', str(args.target.resolve()),
                '--save_dir', str(output), '--device', '0', '--current', str(args.current),
                '--chunk', str(args.chunk), '--future', str(args.future), '--smooth', str(args.smooth)]
    started = time.perf_counter()
    runpy.run_module('bins.infer_single', run_name='__main__')
    elapsed = time.perf_counter() - started
    write_evidence('xvc', args.source.resolve(), args.target.resolve(), list(output.glob('*.wav')),
                   [assets / 'xvc.pt', assets / 'glm-tokenizer/model.safetensors', assets / 'eres2net/pretrained_eres2net.ckpt'],
                   repo, devices, {'current_ms': args.current, 'chunk_ms': args.chunk,
                                   'future_ms': args.future, 'smooth_ms': args.smooth}, elapsed)

if __name__ == '__main__':
    main()
