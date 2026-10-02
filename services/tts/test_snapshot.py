"""純投影的資料隔離／身份回歸；不建立 service、DB 或音訊程序。"""

import unittest

from .snapshot import project_profile, project_queue, project_request


class SnapshotProjectionTests(unittest.TestCase):
    def test_request_retains_identity_and_isolates_aliased_public_fields(self) -> None:
        shared = {"references": [{"audio_path": "fixed.wav"}], "_nested_metadata": "public"}
        record = {"id": "accepted", "profile_snapshot": shared, "metadata": shared,
                  "route_snapshot": {"output": "fixed output"}, "_cancel_audit": {"private": True}}
        result = project_request(record)
        self.assertEqual(set(result), {"id", "profile_snapshot", "metadata", "route_snapshot"})
        result["metadata"]["references"][0]["audio_path"] = "consumer.wav"
        self.assertEqual(result["profile_snapshot"]["references"][0]["audio_path"], "fixed.wav")
        self.assertEqual(record["metadata"]["references"][0]["audio_path"], "fixed.wav")
        record["route_snapshot"]["output"] = "later setting"
        self.assertEqual(result["route_snapshot"]["output"], "fixed output")
        self.assertEqual(result["metadata"]["_nested_metadata"], "public")

    def test_catalogue_hides_local_path_but_request_keeps_evidence(self) -> None:
        profile = {"id": "voice", "profile_path": "contracts/voices/voice.json",
                   "references": {"cosyvoice": {"audio_path": "reference.wav"}}}
        catalogue = project_profile(profile)
        request = project_request({"profile_snapshot": profile})
        self.assertNotIn("profile_path", catalogue)
        self.assertEqual(request["profile_snapshot"]["profile_path"], profile["profile_path"])
        catalogue["references"]["cosyvoice"]["audio_path"] = "changed.wav"
        self.assertEqual(profile["references"]["cosyvoice"]["audio_path"], "reference.wav")
        self.assertEqual(request["profile_snapshot"]["references"]["cosyvoice"]["audio_path"], "reference.wav")

    def test_empty_and_terminal_only_queue_keep_history(self) -> None:
        self.assertEqual(project_queue({}, None, []), [])
        history = {"done": {"id": "done", "status": "completed"},
                   "failed": {"id": "failed", "status": "failed"}}
        self.assertEqual(project_queue(history, None, []), list(history.values()))


if __name__ == "__main__":
    unittest.main()
