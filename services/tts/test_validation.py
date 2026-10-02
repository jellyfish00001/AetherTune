"""請求資料邊界的回歸；不建立 service、worker、DB 或音訊裝置。"""

import copy
import unittest

from .validation import validate_request


class RequestValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.profiles = {"voice": {"id": "voice", "engines": ["cosyvoice"],
                                    "references": {"text": "reference"}}}
        self.command = {"request": {"text": " 測試 ", "engine_id": "cosyvoice",
                                    "voice_profile_id": "voice", "source": "manual",
                                    "metadata": {"route": {"output": "fixture"}}}}
        self.calls = []

    def postfx(self, value):
        self.calls.append("postfx")
        return copy.deepcopy(value or {"enabled": False})

    def route(self, value):
        self.calls.append("route")
        return dict(value)

    def validate(self, command=None, **overrides):
        arguments = {"profiles": self.profiles, "default_policy": "queue",
                     "validate_postfx": self.postfx, "resolve_route": self.route}
        arguments.update(overrides)
        return validate_request(self.command if command is None else command, **arguments)

    def test_defaults_and_nested_data_are_isolated(self) -> None:
        original = copy.deepcopy(self.command)
        result = self.validate(default_policy="reject_new")
        self.assertEqual((result.text, result.policy, result.priority, result.enqueue),
                         (" 測試 ", "reject_new", 0, True))
        self.assertEqual(self.command, original)
        self.command["request"]["metadata"]["route"]["output"] = "changed"
        self.profiles["voice"]["references"]["text"] = "changed"
        self.assertEqual(result.route["output"], "fixture")
        self.assertEqual(result.profile["references"]["text"], "reference")
        self.assertEqual(self.calls, ["postfx", "route"])

    def test_invalid_fields_have_stable_errors(self) -> None:
        cases = [
            ("text", " ", "REQUEST_INVALID: text 不可為空"),
            ("text", 1, "REQUEST_INVALID: text 不可為空"),
            ("text", "a" * 20_001, "REQUEST_INVALID: text 超過 20000 字元"),
            ("engine_id", "cosyvoice3", "BACKEND_UNAVAILABLE: 只允許 cosyvoice 或 breeze；CosyVoice3/Agent 維持 PLANNED"),
            ("source", "loopback", "REQUEST_INVALID: source 必須是 manual、stt、system 或 agent"),
            ("source", "agent", "AGENT_NOT_ALLOWED: agent reply 尚未開放"),
            ("metadata", [], "REQUEST_INVALID: metadata 必須是 object"),
            ("priority", True, "REQUEST_INVALID: priority 必須是整數"),
            ("priority", 1.5, "REQUEST_INVALID: priority 必須是整數"),
            ("voice_profile_id", "missing", "REFERENCE_INVALID: voice_profile_id 不存在"),
            ("voice_profile_id", [], "REFERENCE_INVALID: voice_profile_id 不存在"),
            ("engine_id", "breeze", "REFERENCE_INVALID: profile 不支援 engine=breeze"),
            ("interrupt_policy", "invalid", "REQUEST_INVALID: interrupt_policy 不合法"),
        ]
        for field, value, expected in cases:
            with self.subTest(field=field, value_type=type(value).__name__):
                command = copy.deepcopy(self.command)
                command["request"][field] = value
                with self.assertRaises(ValueError) as caught:
                    self.validate(command)
                self.assertEqual(str(caught.exception), expected)

    def test_request_and_enqueue_types(self) -> None:
        for value in (None, [], "text"):
            with self.subTest(request=value), self.assertRaisesRegex(ValueError, "request 必須是 object"):
                self.validate({"request": value})
        for value in (0, 1, "true", None):
            with self.subTest(enqueue=value), self.assertRaisesRegex(ValueError, "enqueue 必須是 boolean"):
                self.validate({**self.command, "enqueue": value})
        self.assertFalse(self.validate({**self.command, "enqueue": False}).enqueue)
        self.command["request"]["text"] = "a" * 20_000
        self.assertEqual(len(self.validate().text), 20_000)

    def test_stt_accepts_only_physical_microphone(self) -> None:
        self.command["request"]["source"] = "stt"
        for source in (None, "loopback", "tts_output"):
            self.command["request"]["metadata"]["capture_source"] = source
            with self.subTest(source=source), self.assertRaisesRegex(ValueError, "CAPTURE_SOURCE_INVALID"):
                self.validate()
        self.command["request"]["metadata"]["capture_source"] = "physical_microphone"
        self.assertEqual(self.validate().source, "stt")

    def test_validation_error_precedence_and_injected_failure(self) -> None:
        self.command["request"].update(priority=True, voice_profile_id="missing")
        error = ValueError("POSTFX_INVALID: fixture")

        def invalid_postfx(value):
            raise error

        with self.assertRaises(ValueError) as caught:
            self.validate(validate_postfx=invalid_postfx)
        self.assertIs(caught.exception, error)
        self.assertEqual(self.calls, [])
        with self.assertRaisesRegex(ValueError, "priority 必須是整數"):
            self.validate()
        self.assertEqual(self.calls, ["postfx"])

        self.command["request"].update(priority=0, voice_profile_id="voice", interrupt_policy="invalid")

        def invalid_route(value):
            raise RuntimeError("route fixture")

        with self.assertRaisesRegex(RuntimeError, "route fixture"):
            self.validate(resolve_route=invalid_route)


if __name__ == "__main__":
    unittest.main()
