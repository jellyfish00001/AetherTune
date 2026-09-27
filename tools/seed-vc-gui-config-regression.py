"""Regression tests for exact Seed-VC device pairing and reference path validation."""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


SPEC = importlib.util.spec_from_file_location(
    "seed_vc_gui_config", Path(__file__).with_name("seed-vc-gui-config.py")
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class GuiConfigRegression(unittest.TestCase):
    def setUp(self) -> None:
        self.hostapis = [{"name": "Windows WASAPI"}, {"name": "MME"}]
        self.devices = [
            {"index": 1, "hostapi_name": "Windows WASAPI", "name": "Microphone", "max_input_channels": 2},
            {"index": 2, "hostapi_name": "Windows WASAPI", "name": "CABLE Input", "max_output_channels": 2},
            {"index": 3, "hostapi_name": "MME", "name": "Microphone", "max_input_channels": 2},
            {"index": 4, "hostapi_name": "MME", "name": "CABLE Input", "max_output_channels": 2},
        ]

    def test_device_pair_requires_one_host_api(self) -> None:
        api, source, sink = MODULE.select_device_pair(
            self.hostapis, self.devices, "Windows WASAPI", "Microphone", "CABLE Input"
        )
        self.assertEqual((api, source["index"], sink["index"]), ("Windows WASAPI", 1, 2))

    def test_duplicate_names_require_explicit_host_api(self) -> None:
        with self.assertRaisesRegex(ValueError, "歧義"):
            MODULE.select_device_pair(self.hostapis, self.devices, None, "Microphone", "CABLE Input")

    def test_reference_requires_existing_ascii_path(self) -> None:
        with tempfile.TemporaryDirectory(prefix="seed-vc-reference-") as temp:
            root = Path(temp)
            ascii_file = root / "reference.wav"
            ascii_file.write_bytes(b"fixture")
            self.assertEqual(MODULE.validate_reference(ascii_file), ascii_file.resolve())

            unicode_file = root / "聲音.wav"
            unicode_file.write_bytes(b"fixture")
            with self.assertRaisesRegex(ValueError, "非 ASCII"):
                MODULE.validate_reference(unicode_file)

            with self.assertRaisesRegex(ValueError, "不存在"):
                MODULE.validate_reference(root / "missing.wav")


if __name__ == "__main__":
    unittest.main(verbosity=2)
