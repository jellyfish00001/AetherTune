"""測試 Seed-VC GUI 設定套用器會回報 widget failure。"""

from __future__ import annotations

import runpy
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
USERFLOW_TEST = PROJECT_ROOT / "tools" / "seed-vc-gui-userflow-test.py"
APPLY_GUI_SETTINGS = runpy.run_path(str(USERFLOW_TEST))["_apply_gui_settings"]


class _FakeElement:
    def __init__(self) -> None:
        self.value = None

    def update(self, *, value):
        self.value = value


class _FakeWindow:
    def __init__(self, keys: set[str]) -> None:
        self.elements = {key: _FakeElement() for key in keys}

    def __getitem__(self, key: str) -> _FakeElement:
        return self.elements[key]


class GuiSettingsRegression(unittest.TestCase):
    def test_all_widgets_and_event_values_are_reported_as_pass(self) -> None:
        desired = {"block_time": 0.3, "sg_output_device": "CABLE Input"}
        values = {}
        window = _FakeWindow(set(desired))

        result = APPLY_GUI_SETTINGS(window, values, desired)

        self.assertEqual(result["status"], "PASS")
        self.assertEqual(values, desired)
        self.assertEqual(result["widget_applied"], list(desired))
        self.assertEqual(window["block_time"].value, 0.3)

    def test_missing_widget_is_not_hidden_by_event_value_assignment(self) -> None:
        desired = {"block_time": 0.3, "missing_setting": True}
        values = {}
        window = _FakeWindow({"block_time"})

        result = APPLY_GUI_SETTINGS(window, values, desired)

        self.assertEqual(result["status"], "WAITING")
        self.assertEqual(result["widget_update_errors"]["missing_setting"].split(":", 1)[0], "KeyError")
        self.assertEqual(values, desired)
        self.assertNotIn("missing_setting", result["widget_applied"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
