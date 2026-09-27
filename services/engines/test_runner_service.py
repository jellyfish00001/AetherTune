"""可重跑 M2 邊界測試；不替代 CUDA／音訊 E2E。"""
import json
import tempfile
import unittest
import wave
from unittest.mock import Mock, patch
from pathlib import Path
from runner_service import validate, build_command

ROOT = Path(__file__).resolve().parents[2]


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name)
        (self.root / "contracts/engines").mkdir(parents=True)
        for engine in ("seed-vc", "meanvc2", "xvc"):
            data = (ROOT / "contracts/engines" / f"{engine}.json").read_text(encoding="utf-8")
            (self.root / "contracts/engines" / f"{engine}.json").write_text(data, encoding="utf-8")
            for path in json.loads(data)["requiredPaths"]:
                p = self.root / path
                p.parent.mkdir(parents=True, exist_ok=True)
                p.touch()
        self.wav = self.root / "test.wav"
        with wave.open(str(self.wav), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(16000)
            output.writeframes(b"\x01\x00" * 1600)
        self.request = dict(source=str(self.wav), reference=str(self.wav), input="Mic", output="Cable", host_api="WASAPI", parameters={})
        sd = Mock()
        sd.query_hostapis.return_value = [{"name":"WASAPI"}]
        sd.query_devices.return_value = [{"name":"Mic","hostapi":0,"max_input_channels":1,"max_output_channels":0}, {"name":"Cable","hostapi":0,"max_input_channels":0,"max_output_channels":2}]
        self.device_patch = patch.dict("sys.modules", {"sounddevice":sd})
        self.device_patch.start()

    def tearDown(self):
        self.device_patch.stop()
        self.folder.cleanup()

    def test_missing_assets(self):
        (self.root / "models/xvc/xvc.pt").unlink()
        with self.assertRaisesRegex(ValueError, "MODEL_NOT_FOUND"):
            validate(self.root, "xvc", self.request)

    def test_rejects_unknown_or_nonfinite_parameters(self):
        for params in ({"unknown":1}, {"current":float("nan")}, {"current":True}, {"current":-1}, {"current":1.5}):
            with self.subTest(params=params), self.assertRaises(ValueError):
                validate(self.root, "xvc", {**self.request,"parameters":params})

    def test_window_constraint(self):
        with self.assertRaisesRegex(ValueError, "視窗"):
            validate(self.root,"xvc",{**self.request,"parameters":{"chunk":100}})

    def test_seed_device_and_step(self):
        for patch in ({"input":""}, {"input":"Missing Mic"}, {"host_api":"Wrong API"}, {"parameters":{"block_time":.31}}, {"parameters":{"block_time":.04,"crossfade_length":.1}}):
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                validate(self.root,"seed-vc",{**self.request,**patch})

    def test_no_tts_integration(self):
        with self.assertRaisesRegex(ValueError,"BACKEND_UNAVAILABLE"):
            validate(self.root,"cosyvoice",self.request)

    def test_three_existing_runner_commands(self):
        for engine in ("seed-vc","meanvc2","xvc"):
            _,values=validate(self.root,engine,self.request)
            command=build_command(self.root,engine,self.request,values,self.root)
            self.assertTrue(any(f"{engine}-" in c or "seed-vc-gui-run" in c for c in command))
            self.assertNotIn("--realtime",command)


if __name__=="__main__":
    unittest.main()
