"""可重跑 M2 邊界測試；不替代 CUDA／音訊 E2E。"""
import json
import csv
import hashlib
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
        for engine in ("seed-vc", "meanvc2", "xvc", "rvc"):
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
        weights = self.root / "models/weights/Sage.pth"
        index = self.root / "models/indexes/Sage.index"
        weights.parent.mkdir(parents=True, exist_ok=True)
        index.parent.mkdir(parents=True, exist_ok=True)
        weights.write_bytes(b"registered weights")
        index.write_bytes(b"registered index")
        self.weights = weights
        with (self.root / "models/model-register.csv").open("w", encoding="utf-8", newline="") as stream:
            fields = ["model_id", "weights_relative_path", "index_relative_path", "weights_sha256", "index_sha256"]
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerow(dict(model_id="Sage_CN_HeroicFemale", weights_relative_path="models/weights/Sage.pth",
                                 index_relative_path="models/indexes/Sage.index", weights_sha256=hashlib.sha256(weights.read_bytes()).hexdigest(),
                                 index_sha256=hashlib.sha256(index.read_bytes()).hexdigest()))
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

    def test_rvc_uses_registered_models_instead_of_reference_wav(self):
        _, values = validate(self.root, "rvc", {**self.request, "reference": "missing.wav"})
        self.assertEqual(values["model_id"], "Sage_CN_HeroicFemale")
        self.assertEqual(values["f0_method"], "fcpe")
        self.weights.write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "MODEL_HASH_MISMATCH"):
            validate(self.root, "rvc", self.request)

    def test_rvc_file_mode_requires_source_but_does_not_open_input(self):
        request = {**self.request, "input": "missing", "parameters": {"source_mode": "file", "pitch": 3}}
        _, values = validate(self.root, "rvc", request)
        command = build_command(self.root, "rvc", request, values, self.root)
        self.assertEqual(command[0], str(self.root / ".venv/Scripts/python.exe"))
        stored = json.loads((self.root / "rvc-request.json").read_text(encoding="utf-8"))
        self.assertEqual(stored["parameters"]["pitch"], 3)
        self.assertEqual(stored["parameters"]["source_mode"], "file")
        self.assertTrue(any("rvc_runtime.py" in argument for argument in command))
        with self.assertRaisesRegex(ValueError, "REFERENCE_INVALID"):
            validate(self.root, "rvc", {**request, "source": "missing.wav"})

    def test_rvc_rejects_unknown_models_invalid_route_or_monitor(self):
        for patch in ({"parameters": {"model_id": "unknown"}}, {"parameters": {"pitch": True}},
                      {"input": "missing"}, {"output": "missing"},
                      {"monitor": {"enabled": True, "output": "CABLE Input", "host_api": "WASAPI"}}):
            with self.subTest(patch=patch), self.assertRaises(ValueError if "monitor" not in patch else RuntimeError):
                validate(self.root, "rvc", {**self.request, **patch})

    def test_three_existing_runner_commands(self):
        for engine in ("seed-vc","meanvc2","xvc"):
            _,values=validate(self.root,engine,self.request)
            command=build_command(self.root,engine,self.request,values,self.root)
            self.assertTrue(any(f"{engine}-" in c or "seed-vc-gui-run" in c for c in command))
            self.assertNotIn("--realtime",command)

    def test_rvc_rejects_cable_feedback_alias(self):
        import sounddevice as sd
        source = "CABLE Output (VB-Audio Virtual Cable)"
        for target in ("CABLE Input (VB-Audio Virtual Cable)", "CABLE In 16ch (VB-Audio Virtual Cable)"):
            sd.query_devices.return_value = [dict(name=source, hostapi=0, max_input_channels=16, max_output_channels=0),
                                            dict(name=target, hostapi=0, max_input_channels=0, max_output_channels=16)]
            with self.subTest(target=target), self.assertRaisesRegex(ValueError, "ROUTE_FAILED"):
                validate(self.root, "rvc", {**self.request, "input": source, "output": target})


if __name__=="__main__":
    unittest.main()
