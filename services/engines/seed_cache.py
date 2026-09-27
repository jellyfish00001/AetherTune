"""補齊登記的 Seed cache；預設唯讀，既有不同內容不覆寫，不升級模型。"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import urllib.request

REPOSITORIES = {'facebook/wav2vec2-xls-r-300m', 'funasr/campplus', 'FunAudioLLM/CosyVoice-300M'}


def matches(path: Path, asset: dict) -> bool:
    if not path.is_file() or path.stat().st_size != asset['size_bytes']:
        return False
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest() == asset['sha256'].lower()


def repair(root: Path, source_root: Path, apply: bool = False, download: bool = False) -> dict:
    manifest = json.loads((root / 'tools/seed-vc-assets.json').read_text(encoding='utf-8'))
    records = manifest['huggingface_repositories']
    if {r['repo_id'] for r in records} != REPOSITORIES:
        raise ValueError('登記的三個 repository 不符，拒絕擴大下載範圍')
    cache = root / 'tools/external/seed-vc/checkpoints'
    actions = []
    for record in records:
        revision = record['expected_local_revision']
        directory = record['cache_directory']
        if not re.fullmatch(r'[0-9a-f]{40}', revision) or directory != 'models--' + record['repo_id'].replace('/', '--'):
            raise ValueError('cache directory／固定 revision 無效')
        destination = cache / directory
        ref = destination / 'refs/main'
        if ref.exists() and ref.read_text(encoding='utf-8').strip() != revision:
            raise ValueError(f'既有 ref 不同，保留並中止：{ref}')
        for asset in record['files']:
            name = asset['path']
            if Path(name).name != name or not re.fullmatch(r'[0-9a-fA-F]{64}', asset['sha256']) or asset['size_bytes'] <= 0:
                raise ValueError('登記檔名／hash／size 無效')
            target = destination / 'snapshots' / revision / name
            if matches(target, asset):
                actions.append({'path': str(target), 'action': 'existing_verified', 'sha256': asset['sha256']})
                continue
            if target.exists():
                raise ValueError(f'既有檔案 hash／size 不符；不覆寫：{target}')
            source = source_root / directory / 'snapshots' / revision / name
            local = matches(source, asset)
            url = f"https://huggingface.co/{record['repo_id']}/resolve/{revision}/{name}"
            action = {'path': str(target), 'action': 'copy_verified_local' if local else 'download_pinned',
                      'source': str(source) if local else url, 'sha256': asset['sha256'], 'size_bytes': asset['size_bytes']}
            actions.append(action)
            if not apply:
                continue
            if not local and not download:
                raise ValueError(f'缺少已驗證副本；下載需 --allow-download：{name}')
            target.parent.mkdir(parents=True, exist_ok=True)
            # 完整驗證後才 atomic replace；失敗不留下可被 loader 使用的半成品。
            fd, temporary = tempfile.mkstemp(dir=target.parent, prefix='.seed-asset-', suffix='.part')
            temporary = Path(temporary)
            try:
                with os.fdopen(fd, 'wb') as output:
                    if local:
                        with source.open('rb') as stream:
                            shutil.copyfileobj(stream, output, 4 * 1024 * 1024)
                    else:
                        with urllib.request.urlopen(url, timeout=60) as stream:
                            received = 0
                            while block := stream.read(4 * 1024 * 1024):
                                received += len(block)
                                if received > asset['size_bytes']:
                                    raise ValueError('下載超過登記 size')
                                output.write(block)
                if not matches(temporary, asset):
                    raise ValueError(f'下載／複製內容 hash 或 size 不符：{name}')
                os.replace(temporary, target)
            finally:
                temporary.unlink(missing_ok=True)
        if apply:
            # 這是原登記的 local snapshot pointer；不提升 upstream provenance 的 WAITING。
            ref.parent.mkdir(parents=True, exist_ok=True)
            if not ref.exists():
                ref.write_text(revision, encoding='utf-8')
        actions.append({'path': str(ref), 'action': 'ref_verified' if ref.exists() else 'create_registered_ref', 'revision': revision})
    return {'status': 'PASS' if apply else 'PLAN', 'scope': 'registered realtime-tiny dependency cache only',
            'upstream_provenance': 'unchanged', 'audio_status': 'WAITING', 'actions': actions}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--source-cache', type=Path, default=Path.home()/'.cache/huggingface/hub')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--allow-download', action='store_true')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    result = repair(args.root.resolve(), args.source_cache.resolve(), args.apply, args.allow_download)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
