"""cache 修復的寫入／hash／ref 保護；不使用網路或真實模型。"""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import io
from seed_cache import REPOSITORIES, repair


class CacheTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)/'repo'
        self.source = Path(self.tmp.name)/'source'
        self.records = []
        for name in sorted(REPOSITORIES):
            record = {'repo_id': name, 'cache_directory': 'models--'+name.replace('/', '--'),
                      'expected_local_revision': 'a'*40, 'files': [{'path': 'asset.bin', 'size_bytes': 4, 'sha256': hashlib.sha256(b'test').hexdigest()}]}
            self.records.append(record)
            src = self.source/record['cache_directory']/'snapshots'/('a'*40)/'asset.bin'
            src.parent.mkdir(parents=True)
            src.write_bytes(b'test')
        (self.root/'tools').mkdir(parents=True)
        (self.root/'tools/seed-vc-assets.json').write_text(json.dumps({'huggingface_repositories': self.records}))
        self.cache = self.root/'tools/external/seed-vc/checkpoints'

    def test_plan_read_only(self):
        self.assertEqual(repair(self.root,self.source)['status'],'PLAN')
        self.assertFalse(self.cache.exists())

    def test_verified_copy_and_idempotence(self):
        self.assertEqual(repair(self.root,self.source,True)['status'],'PASS')
        result=repair(self.root,self.source,True)
        self.assertEqual(sum(a['action']=='existing_verified' for a in result['actions']),3)

    def test_different_ref_preserved(self):
        ref=self.cache/self.records[0]['cache_directory']/'refs/main'
        ref.parent.mkdir(parents=True);ref.write_text('b'*40)
        with self.assertRaises(ValueError):repair(self.root,self.source,True)
        self.assertEqual(ref.read_text(),'b'*40)

    def test_download_requires_explicit_flag(self):
        with self.assertRaises(ValueError):repair(self.root,Path(self.tmp.name)/'missing',True)

    def test_download_hash_failure_never_creates_ref(self):
        with patch('urllib.request.urlopen',return_value=io.BytesIO(b'bad!')):
            with self.assertRaises(ValueError):repair(self.root,Path(self.tmp.name)/'missing',True,True)
        self.assertFalse(any(self.cache.rglob('main')))
        self.assertFalse(any(self.cache.rglob('*.part')))

    def test_existing_corrupt_asset_preserved(self):
        target=self.cache/self.records[0]['cache_directory']/'snapshots'/('a'*40)/'asset.bin'
        target.parent.mkdir(parents=True);target.write_bytes(b'bad!')
        with self.assertRaises(ValueError):repair(self.root,self.source,True)
        self.assertEqual(target.read_bytes(),b'bad!')


if __name__=='__main__':unittest.main()
