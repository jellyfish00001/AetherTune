"""下載固定 revision 的公開推論資產，檢查已登錄的必要權重 hash。"""
import argparse
import hashlib
import json
from pathlib import Path
from huggingface_hub import snapshot_download

ROOT = Path(__file__).resolve().parents[1]

HASHES = {
    'meanvc2': {
        'fastu2pp_160ms.pt': '9a372c1b7178f564a15da1cd36901d7d0c9081a2fabf53cb6cc0d971deca4928',
        'fastu2pp_80ms.pt': '4338739bd13e0f7718276373e9547ce1f9aa02ec0867452860df9e837f90e4d2',
        'vocos.pt': 'df1f2ba9f7ac35c96832579421ee1ed913a68c3a1d2f8a6536739f902f194a93',
        'meanvc2_120ms_40ms.safetensors': '04ea21a4fb55400469e6004ae842c3e7f059f759e92946fb95123418cad5d818',
        'meanvc2_40ms_40ms.safetensors': '01caafec9a3991a5514df9412952d24ae3370406358a01e20e03df41f2f5d515',
        'wavlm_large.pt': '6fb4b3c3e6aa567f0a997b30855859cb81528ee8078802af439f7b2da0bf100f',
        'wavlm_large_finetune.pth': '51f07e3b94d9e0262a6a675ef5a087be3dd09e8c62e9d886827f44f82fe7f94b',
    },
    'xvc': {
        'xvc.pt': '1ba0ca3187d2a6753a1529db18c5490e5cb20c8874dc067b92935ff39cfed687',
        'glm-tokenizer/model.safetensors': '2800bd503f52b51e45f0c53cfd5c31dcfe8ef7f13d22b396aa3d53e0280dd1e4',
        'eres2net/pretrained_eres2net.ckpt': 'd8941f5952e31820173c8854562cb6d7897aaa58cd65c18f30d5a2e52d30847d',
    },
}

def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--backend', choices=list(HASHES), required=True)
    parser.add_argument('--verify-only', action='store_true', help='本機檢查，不下載')
    args = parser.parse_args()
    assets = ROOT / 'models' / args.backend
    if not args.verify_only:
        assets.mkdir(parents=True, exist_ok=True)
    if not args.verify_only:
        if args.backend == 'meanvc2':
            snapshot_download('ASLP-lab/MeanVC2', revision='39cdd19522fe896c227da691314d9a0e3b995486', local_dir=assets)
            import gdown
            # 上游 initialization.py 的 Microsoft release URL 已 404，改用官方 README 的 Google Drive。
            for name, file_id in [('wavlm_large.pt', '12-cB34qCTvByWT-QtOcZaqwwO21FLSqU'),
                                  ('wavlm_large_finetune.pth', '1-aE1NfzpRCLxA4GUxX9ITI3F9LlbtEGP')]:
                if not (assets / name).exists():
                    gdown.download(id=file_id, output=str(assets / name))
        else:
            snapshot_download('chenxie95/X-VC', revision='9e54747d8c4d1ef544b903e2300a4ba040dcc126', local_dir=assets)
            snapshot_download('zai-org/glm-4-voice-tokenizer', revision='a5f2404e63c84e92f5238908e1706316324ebafa', local_dir=assets / 'glm-tokenizer')
            # ModelScope helper 未取得不可變 commit，主權重以 observed hash 固定；更新不得默默通過。
            if not (assets / 'eres2net/configuration.json').exists() or not (assets / 'eres2net/pretrained_eres2net.ckpt').exists():
                from modelscope.hub.snapshot_download import snapshot_download as ms_download
                ms_download('iic/speech_eres2net_sv_en_voxceleb_16k', local_dir=str(assets / 'eres2net'))
    results = []
    for name, expected in HASHES[args.backend].items():
        path = assets / name
        actual = sha256(path) if path.is_file() else None
        results.append({'path': str(path.relative_to(ROOT)), 'sha256': actual, 'status': 'PASS' if actual == expected else 'BLOCKED'})
    if any(row['status'] != 'PASS' for row in results):
        print(json.dumps(results, indent=2))
        raise SystemExit('資產缺失或 hash 不符，請檢查下載；不會自動覆寫既有權重。')
    if args.backend == 'meanvc2':
        import torch
        if not (assets / 'wavlm_large_cfg.pt').exists():
            if args.verify_only:
                raise SystemExit('BLOCKED: 缺少 wavlm_large_cfg.pt；VerifyOnly 不重建資產。')
            # 來源已先核對 hash；只載入已固定的官方 WavLM checkpoint 以抽取 cfg。
            checkpoint = torch.load(assets / 'wavlm_large.pt', map_location='cpu', weights_only=False)
            torch.save(checkpoint['cfg'], assets / 'wavlm_large_cfg.pt')
        cfg_hash = sha256(assets / 'wavlm_large_cfg.pt')
        if cfg_hash != '57a3573bd8204e039b97c8ffc8d313e77e5d8787389bdfab4dd4949a784d04e9':
            raise SystemExit('BLOCKED: wavlm_large_cfg.pt hash 不符，保留檔案並停止。')
        results.append({'path': 'models/meanvc2/wavlm_large_cfg.pt', 'sha256': cfg_hash, 'status': 'PASS'})
    output = ROOT / 'artifacts' / args.backend / 'install-assets.json'
    if not args.verify_only:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(results, indent=2), encoding='utf-8')
    print(json.dumps(results, indent=2))

if __name__ == '__main__':
    main()
