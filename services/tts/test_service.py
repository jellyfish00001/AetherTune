"""Manual TTS orchestration regression tests using explicit fake adapters.

這些測試驗證 queue/state/SQLite/cancellation contract；不宣稱 CosyVoice、Breeze
模型或 Windows audio endpoint 已通過。fake generation 仍建立真實 subprocess，
用來檢查 stop/clear/20-request 後沒有殘留 process。
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import types
import unittest
import wave
from pathlib import Path

from .adapters import GenerationCancelled, GenerationResult
from .playback import MonitoredPlayback, NullPlayback, PlaybackCancelled, PlaybackError, SoundDevicePlayback, list_audio_devices, resolve_route
from .service import SpeechService
from .postfx import render_postfx
from .wsl_job import WslJob, to_wsl_path


ROOT = Path(__file__).resolve().parents[2]
ROUTE = {
    "output": "Fake explicit output",
    "host_api": "Fake host api",
    "rack_profile_id": "seed-vc-neutral",
    "route_profile_id": "seed-vc-virtual-route",
}


class DeviceListTests(unittest.TestCase):
    def test_endpoint_list_keeps_host_api_default_and_duplicate_safety(self) -> None:
        fake_sounddevice = types.SimpleNamespace(
            query_hostapis=lambda: [{"name": "MME"}, {"name": "Windows DirectSound"}],
            query_devices=lambda: [
                {"name": "Mic", "hostapi": 0, "max_input_channels": 1, "max_output_channels": 0},
                {"name": "Speaker", "hostapi": 0, "max_input_channels": 0, "max_output_channels": 2},
                {"name": "Speaker", "hostapi": 1, "max_input_channels": 0, "max_output_channels": 2},
                {"name": "Speaker", "hostapi": 1, "max_input_channels": 0, "max_output_channels": 2},
            ],
            default=types.SimpleNamespace(device=(0, 1)),
        )
        previous = sys.modules.get("sounddevice")
        sys.modules["sounddevice"] = fake_sounddevice
        try:
            devices = list_audio_devices()
        finally:
            if previous is None:
                sys.modules.pop("sounddevice", None)
            else:
                sys.modules["sounddevice"] = previous
        self.assertEqual(len(devices["inputs"]), 1)
        self.assertEqual(len(devices["outputs"]), 3)
        self.assertTrue(devices["outputs"][0]["is_default"])
        self.assertTrue(devices["outputs"][0]["selectable"])
        self.assertFalse(devices["outputs"][1]["selectable"])
        self.assertFalse(devices["outputs"][2]["selectable"])


class MonitorPlaybackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.primary = NullPlayback(seconds=0.01)
        self.monitor = NullPlayback(seconds=0.01)
        self.playback = MonitoredPlayback(primary=self.primary, monitor=self.monitor, monitor_join_timeout_seconds=0.1)
        self.route = {**ROUTE, "monitor": {"enabled": True, "output": "Headphones", "host_api": "MME"}}

    def test_off_does_not_open_monitor(self) -> None:
        result = self.playback.play(Path("fake.wav"), {**self.route, "monitor": {"enabled": False}}, threading.Event())
        self.assertEqual(result.monitor_status, "off")
        self.assertEqual(len(self.primary.calls), 1)
        self.assertEqual(self.monitor.calls, [])

    def test_monitor_runs_concurrently_without_changing_primary(self) -> None:
        started = threading.Event()

        class GatedPrimary(NullPlayback):
            def play(self, audio_path, route, cancel_event):
                if not started.wait(1):
                    raise AssertionError("monitor must start before primary finishes")
                return super().play(audio_path, route, cancel_event)

        class StartingMonitor(NullPlayback):
            def play(self, audio_path, route, cancel_event):
                started.set()
                return super().play(audio_path, route, cancel_event)

        playback = MonitoredPlayback(primary=GatedPrimary(), monitor=StartingMonitor())
        result = playback.play(Path("fake.wav"), self.route, threading.Event())
        self.assertEqual(result.output_name, ROUTE["output"])
        self.assertEqual(result.monitor_output, "Headphones")
        self.assertEqual(result.monitor_status, "completed")
        self.assertEqual(result.monitor_frames_written, 1)
        self.assertFalse(result.playback_verified)

    def test_monitor_failure_does_not_replay_or_fail_primary(self) -> None:
        class FailedMonitor(NullPlayback):
            def play(self, *args):
                raise PlaybackError("DEVICE_NOT_FOUND: headphones removed")

        playback = MonitoredPlayback(primary=self.primary, monitor=FailedMonitor())
        result = playback.play(Path("fake.wav"), self.route, threading.Event())
        self.assertEqual(len(self.primary.calls), 1)
        self.assertEqual(result.monitor_status, "failed")
        self.assertIn("headphones removed", result.monitor_error)

    def test_same_physical_output_avoids_double_playback_across_apis(self) -> None:
        route = {**self.route, "output": "Headphones", "host_api": "Windows WASAPI"}
        result = self.playback.play(Path("fake.wav"), route, threading.Event())
        self.assertEqual(result.monitor_status, "same_output")
        self.assertEqual(self.monitor.calls, [])

    def test_monitor_open_blocked_does_not_block_primary_output(self) -> None:
        self.monitor.open_blocked = True
        result = self.playback.play(Path("fake.wav"), self.route, threading.Event())
        self.assertIn("MONITOR_BLOCKED", result.monitor_error)
        self.assertEqual(len(self.primary.calls), 1)
        self.assertFalse(self.playback.open_blocked)
        self.assertEqual(self.monitor.calls, [])

    def test_stop_cancels_both_streams(self) -> None:
        self.primary.seconds = self.monitor.seconds = 3
        cancel = threading.Event()
        errors = []

        def play():
            try:
                self.playback.play(Path("fake.wav"), self.route, cancel)
            except PlaybackCancelled as exc:
                errors.append(exc)

        thread = threading.Thread(target=play)
        thread.start()
        deadline = time.monotonic() + 1
        while not self.primary.calls and time.monotonic() < deadline:
            time.sleep(0.005)
        cancel.set()
        self.playback.stop()
        thread.join(timeout=1)
        self.assertFalse(thread.is_alive())
        self.assertFalse(self.playback._monitor_thread.is_alive())
        self.assertEqual(len(errors), 1)
        self.assertGreaterEqual(self.primary.stop_calls, 1)
        self.assertGreaterEqual(self.monitor.stop_calls, 1)

    def test_stalled_monitor_is_bounded_and_cannot_overlap_next_request(self) -> None:
        release = threading.Event()

        class StalledMonitor(NullPlayback):
            def play(self, *args):
                self.calls.append({})
                release.wait(2)
                raise PlaybackError("fixture released")

        monitor = StalledMonitor()
        playback = MonitoredPlayback(primary=self.primary, monitor=monitor, monitor_join_timeout_seconds=0.1)
        try:
            started = time.monotonic()
            first = playback.play(Path("fake.wav"), self.route, threading.Event())
            self.assertLess(time.monotonic() - started, 0.8)
            self.assertIn("MONITOR_TIMEOUT", first.monitor_error)
            second = playback.play(Path("fake.wav"), self.route, threading.Event())
            self.assertIn("MONITOR_BLOCKED", second.monitor_error)
            self.assertEqual(len(monitor.calls), 1)
        finally:
            release.set()
            playback._monitor_thread.join(timeout=1)

    def test_monitor_route_validation_rejects_virtual_loop_and_missing_target(self) -> None:
        for target in ({"enabled": "false"}, {"enabled": True}, {"enabled": True, "output": "CABLE Input", "host_api": "MME"}):
            with self.subTest(target=target), self.assertRaises(PlaybackError):
                resolve_route({**ROUTE, "monitor": target})
        self.assertEqual(resolve_route({**ROUTE, "monitor": {"enabled": False}})["monitor"], {"enabled": False})


class FakeGenerationAdapter:
    supports_streaming_tts = False

    def __init__(self, engine_id: str = "cosyvoice", *, delay: float = 0.03) -> None:
        self.engine_id = engine_id
        self.delay = delay
        self.processes: list[subprocess.Popen] = []
        self.cancel_calls: list[str] = []
        self.cancel_result: dict | None = None
        self.fail_next = False
        self.start_gate: threading.Event | None = None
        self.started = threading.Event()
        self.close_calls = 0

    def readiness(self) -> dict:
        return {
            "engine_id": self.engine_id,
            "preflight_valid": True,
            "state": "VALIDATED",
            "errors": [],
            "supports_streaming_tts": False,
        }

    def generate(self, request, output_path: Path, job_dir: Path, cancel_event: threading.Event) -> GenerationResult:
        self.started.set()
        if self.start_gate is not None:
            while not self.start_gate.is_set():
                if cancel_event.wait(0.005):
                    raise GenerationCancelled("fake gate cancelled")
        if self.fail_next:
            self.fail_next = False
            raise RuntimeError("fixture generation failure")
        process = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(0.15)"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.processes.append(process)
        deadline = time.monotonic() + self.delay
        try:
            while process.poll() is None and time.monotonic() < deadline:
                if cancel_event.wait(0.005):
                    process.terminate()
                    process.wait(timeout=2)
                    raise GenerationCancelled("fake subprocess cancelled")
                time.sleep(0.002)
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=2)
            if cancel_event.is_set():
                raise GenerationCancelled("fake cancelled")
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with wave.open(str(output_path), "wb") as stream:
                stream.setnchannels(1)
                stream.setsampwidth(2)
                stream.setframerate(16000)
                stream.writeframes(b"\x01\x00" * 160)
            return GenerationResult(
                audio_path=output_path,
                metrics={"generation_latency_ms": 1.0, "supports_streaming_tts": False},
                evidence={
                    "engine_id": self.engine_id,
                    "model_fingerprint": {"aggregate_sha256": "fixture-model"},
                    "pid_audit": {"fixture_process_pid": process.pid, "alive_after": process.poll() is None},
                    "runner": {"kind": "fake_subprocess", "supports_streaming_tts": False},
                },
            )
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=2)

    def cancel(self, reason: str = "cancelled") -> dict:
        self.cancel_calls.append(reason)
        if self.cancel_result is not None:
            return dict(self.cancel_result)
        alive = []
        for process in self.processes:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=2)
            if process.poll() is None:
                alive.append(process.pid)
        return {"event": "fixture_group_cancelled", "reason": reason, "alive_pids": alive}

    def close(self) -> None:
        self.close_calls += 1


class ServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name)
        self.events: list[dict] = []
        (self.root / "contracts/voices").mkdir(parents=True)
        for profile in ("reference-male.json", "reference-female.json"):
            shutil.copy(ROOT / "contracts/voices" / profile, self.root / "contracts/voices" / profile)
        self.adapter = FakeGenerationAdapter(delay=0.01)
        self.service = SpeechService(
            self.root,
            adapters={"cosyvoice": self.adapter, "breeze": self.adapter},
            playback=NullPlayback(seconds=0.005),
            emit=self.events.append,
        )

    def tearDown(self) -> None:
        self.service.close()
        self.folder.cleanup()

    def test_postfx_is_snapshotted_and_processed_file_reaches_playback(self) -> None:
        command = self.request("effects-snapshot")
        command["request"]["metadata"]["postfx"] = {"enabled": True, "wet": 0.5, "low_db": 4}
        request_id = self.service.handle_command(command)["result"]["request_id"]
        command["request"]["metadata"]["postfx"]["wet"] = 0.9
        completed = self.wait_status(request_id, "completed")
        self.assertEqual(completed["metadata"]["postfx"]["wet"], 0.5)
        self.assertTrue(completed["metrics"]["postfx_enabled"])
        played = Path(self.service._playback.calls[0]["audio_path"])
        self.assertTrue(played.name.endswith(".postfx.wav"))
        self.assertTrue(played.is_file())
        self.assertTrue(played.with_name(f"{request_id}.wav").is_file())

    def test_invalid_postfx_rejected_before_enqueue(self) -> None:
        for settings in ({"wet": 1.1}, {"enabled": "yes"}, {"low_db": float("nan")}, {"unknown": 1}):
            command = self.request("effects-invalid")
            command["request"]["metadata"]["postfx"] = settings
            result = self.service.handle_command(command)
            self.assertFalse(result["accepted"])
        self.assertEqual(self.service.snapshot()["snapshot"]["queue"], [])

    def test_monitor_warning_and_route_snapshot_are_persisted_after_primary_completion(self) -> None:
        class WarningPlayback(NullPlayback):
            def play(self, audio_path, route, cancel_event):
                from dataclasses import replace
                return replace(super().play(audio_path, route, cancel_event), monitor_status="failed",
                               monitor_output="Headphones", monitor_host_api="MME", monitor_error="DEVICE_NOT_FOUND: fixture")

        self.service.close()
        self.service = SpeechService(self.root, adapters={"cosyvoice": self.adapter, "breeze": self.adapter}, playback=WarningPlayback())
        command = self.request("monitor persistence")
        route = {**ROUTE, "monitor": {"enabled": True, "output": "Headphones", "host_api": "MME"}}
        command["request"]["metadata"]["route"] = route
        request_id = self.service.handle_command(command)["result"]["request_id"]
        # 提交後修改呼叫者物件，不得改掉已接受 request 的監聽快照。
        route["monitor"]["enabled"] = False
        completed = self.wait_status(request_id, "completed")
        self.assertTrue(completed["route_snapshot"]["monitor"]["enabled"])
        self.assertEqual(completed["metrics"]["monitor_status"], "failed")
        self.assertIsNone(completed["error"])
        deadline = time.monotonic() + 1
        evidence_path = self.root / "artifacts" / "sessions" / self.service.session_id / f"{request_id}.evidence.json"
        while not evidence_path.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        self.assertEqual(evidence["route_resolution"]["monitor"]["status"], "failed")
        self.assertEqual(len(self.service.snapshot()["snapshot"]["transcript"]), 1)

    def request(self, text: str, *, enqueue: bool = True, policy: str = "queue", profile: str = "reference-male") -> dict:
        return {
            "action": "submit",
            "command_id": f"cmd-{text}",
            "enqueue": enqueue,
            "request": {
                "text": text,
                "engine_id": "cosyvoice",
                "voice_profile_id": profile,
                "source": "manual",
                "interrupt_policy": policy,
                "metadata": {"route": ROUTE},
            },
        }

    def wait_status(self, request_id: str, status: str, timeout: float = 4.0) -> dict:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            for item in self.service.snapshot()["snapshot"]["queue"]:
                if item["id"] == request_id and item["status"] == status:
                    return item
            time.sleep(0.01)
        self.fail(f"timeout waiting for {request_id}={status}: {self.service.snapshot()}")

    def wait_all(self, ids: list[str], timeout: float = 8.0) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            statuses = {item["id"]: item["status"] for item in self.service.snapshot()["snapshot"]["queue"]}
            if all(statuses.get(request_id) in {"completed", "failed", "cancelled"} for request_id in ids):
                return
            time.sleep(0.01)
        self.fail(f"timeout waiting for requests: {self.service.snapshot()}")

    def wait_state(self, state: str, timeout: float = 4.0) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.service.snapshot()["snapshot"]["state"] == state:
                return
            time.sleep(0.01)
        self.fail(f"timeout waiting for service state={state}: {self.service.snapshot()}")

    def assert_emitted_contract_enums(self) -> None:
        states = {"IDLE", "QUEUED", "GENERATING", "BUFFERING", "PLAYING", "STOPPING", "ERROR"}
        statuses = {"queued", "generating", "ready", "playing", "completed", "cancelled", "failed"}
        self.assertTrue(self.events, "expected at least one emitted snapshot")
        for event in self.events:
            self.assertEqual(event.get("type"), "speech_snapshot")
            snapshot = event["snapshot"]
            self.assertIn(snapshot["state"], states)
            for record in snapshot["queue"]:
                self.assertIn(record["status"], statuses)

    def test_ack_snapshot_and_profiles(self) -> None:
        self.adapter.start_gate = threading.Event()
        ack = self.service.handle_command(self.request("hello"))
        self.assertEqual(ack["type"], "speech_ack")
        self.assertEqual(ack["command_id"], "cmd-hello")
        self.assertTrue(ack["accepted"])
        snapshot = self.service.snapshot()["snapshot"]
        self.assertIn(snapshot["state"], {"IDLE", "QUEUED", "GENERATING"})
        self.assertFalse(snapshot["mic_enabled"])
        self.assertEqual({profile["id"] for profile in snapshot["profiles"]}, {"reference-male", "reference-female"})
        self.assertTrue(all({"id", "name", "engines"}.issubset(profile) for profile in snapshot["profiles"]))
        self.adapter.start_gate.set()

    def test_generating_snapshot_exposes_elapsed_start(self) -> None:
        self.adapter.start_gate = threading.Event()
        request_id = self.service.handle_command(self.request("elapsed"))["result"]["request_id"]
        current = self.wait_status(request_id, "generating")
        deadline = time.monotonic() + 2
        while "generation_started_at" not in current.get("metrics", {}) and time.monotonic() < deadline:
            time.sleep(0.01)
            current = self.wait_status(request_id, "generating")
        self.assertIn("generation_started_at", current["metrics"])
        self.assertTrue(any(
            event["snapshot"].get("current_request_id") == request_id
            and any(item["id"] == request_id and "generation_started_at" in item.get("metrics", {})
                    for item in event["snapshot"]["queue"])
            for event in self.events
        ))
        self.adapter.start_gate.set()

    def test_switching_engine_closes_previous_adapter(self) -> None:
        breeze = FakeGenerationAdapter(engine_id="breeze", delay=0.01)
        self.service._adapters = {"cosyvoice": self.adapter, "breeze": breeze}
        first = self.service.handle_command(self.request("cosy"))["result"]["request_id"]
        self.wait_status(first, "completed")
        self.assertEqual(breeze.close_calls, 1)
        command = self.request("breeze")
        command["request"]["engine_id"] = "breeze"
        second = self.service.handle_command(command)["result"]["request_id"]
        self.wait_status(second, "completed")
        self.assertEqual(self.adapter.close_calls, 1)
        self.assertEqual(breeze.close_calls, 1)

    def test_add_to_queue_ignores_interrupt_policy(self) -> None:
        self.adapter.start_gate = threading.Event()
        first = self.service.handle_command(self.request("first"))["result"]["request_id"]
        self.wait_status(first, "generating")
        second = self.service.handle_command(self.request("second", policy="interrupt_current"))["result"]["request_id"]
        third_ack = self.service.handle_command(self.request("third", policy="reject_new"))
        self.assertTrue(third_ack["accepted"])
        self.assertNotIn("interrupt_current", self.adapter.cancel_calls)
        self.assertEqual(self.service.snapshot()["snapshot"]["queue"][0]["id"], first)
        self.adapter.start_gate.set()
        self.wait_all([first, second, third_ack["result"]["request_id"]])
        statuses = {item["id"]: item["status"] for item in self.service.snapshot()["snapshot"]["queue"]}
        self.assertEqual(statuses[first], "completed")
        self.assertEqual(statuses[second], "completed")

    def test_queue_crud_stop_clear_and_fifo(self) -> None:
        self.adapter.start_gate = threading.Event()
        first = self.service.handle_command(self.request("a"))["result"]["request_id"]
        self.wait_status(first, "generating")
        second = self.service.handle_command(self.request("b"))["result"]["request_id"]
        third = self.service.handle_command(self.request("c"))["result"]["request_id"]
        self.assertTrue(self.service.handle_command({"action": "move_down", "id": second})["accepted"])
        self.assertTrue(self.service.handle_command({"action": "remove", "id": third})["accepted"])
        self.assertTrue(self.service.handle_command({"action": "stop_speaking"})["accepted"])
        self.adapter.start_gate.set()
        self.wait_all([first, second, third])
        records = {item["id"]: item for item in self.service.snapshot()["snapshot"]["queue"]}
        self.assertEqual(records[first]["status"], "cancelled")
        self.assertEqual(records[third]["status"], "cancelled")
        clear = self.service.handle_command({"action": "clear_queue", "command_id": "clear"})
        self.assertTrue(clear["accepted"])
        transcript = self.service.snapshot()["snapshot"]["transcript"]
        self.assertEqual([item["text"] for item in transcript], ["b"])

    def test_speak_now_interrupt_and_reject(self) -> None:
        self.adapter.start_gate = threading.Event()
        current = self.service.handle_command(self.request("current"))["result"]["request_id"]
        self.wait_status(current, "generating")
        reject = self.service.handle_command(self.request("reject", enqueue=False, policy="reject_new"))
        self.assertFalse(reject["accepted"])
        urgent = self.service.handle_command(self.request("urgent", enqueue=False, policy="interrupt_current"))
        self.assertTrue(urgent["accepted"])
        self.assertIn("speak_now", self.adapter.cancel_calls)
        self.adapter.start_gate.set()
        self.wait_all([current, urgent["result"]["request_id"]])
        statuses = {item["id"]: item["status"] for item in self.service.snapshot()["snapshot"]["queue"]}
        self.assertEqual(statuses[current], "cancelled")
        self.assertEqual(statuses[urgent["result"]["request_id"]], "completed")

    def test_speak_now_honors_queued_request_policy(self) -> None:
        self.adapter.start_gate = threading.Event()
        current = self.service.handle_command(self.request("current"))["result"]["request_id"]
        self.wait_status(current, "generating")
        reject_id = self.service.handle_command(
            self.request("reject-pending", policy="reject_new")
        )["result"]["request_id"]
        rejected = self.service.handle_command({"action": "speak_now", "id": reject_id})
        self.assertFalse(rejected["accepted"])
        interrupt_id = self.service.handle_command(
            self.request("interrupt-pending", policy="interrupt_current")
        )["result"]["request_id"]
        moved = self.service.handle_command({"action": "speak_now", "id": interrupt_id})
        self.assertTrue(moved["accepted"])
        self.assertIn("speak_now", self.adapter.cancel_calls)
        self.adapter.start_gate.set()
        self.wait_all([current, reject_id, interrupt_id])
        statuses = {item["id"]: item["status"] for item in self.service.snapshot()["snapshot"]["queue"]}
        self.assertEqual(statuses[current], "cancelled")
        self.assertEqual(statuses[interrupt_id], "completed")
        self.assertEqual(statuses[reject_id], "completed")

    def test_wsl_script_waits_for_owned_linux_group(self) -> None:
        job = WslJob(
            root=ROOT,
            job_dir=self.root / "job",
            command=["/usr/bin/python3", "-c", "print('fixture')"],
        )
        script = job._script()
        self.assertIn('printf \'{"pid":%s,"token":"%s"}\\n\' "$$"', script)
        self.assertNotIn("bash -lc", script)
        self.assertIn("AETHERTUNE_TTS_JOB_TOKEN", script)

    @unittest.skipUnless(shutil.which("wsl.exe"), "WSL fixture requires wsl.exe")
    def test_wsl_fixture_host_waits_for_output_and_ownership(self) -> None:
        parent = ROOT / "artifacts" / "sessions" / "_tts-wsl-fixture"
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent) as folder:
            job_dir = Path(folder)
            output = job_dir / "fixture.txt"
            command = [
                "bash",
                "-lc",
                f"sleep 0.35; printf fixture > {to_wsl_path(output)}",
            ]
            job = WslJob(root=ROOT, job_dir=job_dir, command=command)
            job.start()
            code = job.wait(timeout=10)
            self.assertEqual(code, 0)
            self.assertEqual(output.read_text(encoding="utf-8"), "fixture")
            self.assertIsNotNone(job.audit()["pid_record"])

    @unittest.skipUnless(shutil.which("wsl.exe"), "WSL fixture requires wsl.exe")
    def test_wsl_fixture_cancel_verifies_group_absence(self) -> None:
        parent = ROOT / "artifacts" / "sessions" / "_tts-wsl-cancel-fixture"
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent) as folder:
            job_dir = Path(folder)
            job = WslJob(
                root=ROOT,
                job_dir=job_dir,
                command=["/usr/bin/sleep", "30"],
            )
            job.start()
            deadline = time.monotonic() + 5
            while job._read_pid_record() is None and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertIsNotNone(job._read_pid_record())
            audit = job.cancel("fixture_cancel")
            self.assertEqual(audit["event"], "group_cancelled")
            self.assertTrue(audit["identity_verified"])
            again = job.cancel("fixture_cancel_again")
            self.assertEqual(again["event"], "group_cancelled")
            self.assertTrue(again["identity_verified"])
            self.assertTrue(again["idempotent"])
            exit_code = job.wait(timeout=10)
            self.assertEqual(job.poll(), exit_code)
            self.assertIsNotNone(exit_code)

    @unittest.skipUnless(shutil.which("wsl.exe"), "WSL fixture requires wsl.exe")
    def test_wsl_fixture_completed_job_cancel_is_idempotent_cleanup(self) -> None:
        parent = ROOT / "artifacts" / "sessions" / "_tts-wsl-completed-fixture"
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent) as folder:
            job = WslJob(
                root=ROOT,
                job_dir=Path(folder),
                command=["/usr/bin/true"],
            )
            job.start()
            self.assertEqual(job.wait(timeout=10), 0)
            audit = job.cancel("fixture_after_normal_exit")
            self.assertEqual(audit["event"], "group_cancelled")
            self.assertTrue(audit["identity_verified"])
            self.assertTrue(audit["group_absent_before_cancel"])
            again = job.cancel("fixture_after_normal_exit_again")
            self.assertTrue(again["idempotent"])
            self.assertEqual(again["event"], "group_cancelled")

    def test_playback_watchdog_classifies_stalled_driver(self) -> None:
        audio_path = self.root / "watchdog.wav"
        with wave.open(str(audio_path), "wb") as stream:
            stream.setnchannels(1)
            stream.setsampwidth(2)
            stream.setframerate(16000)
            stream.writeframes(b"\x01\x00" * 160)

        class BlockingStream:
            def __init__(self, *args, **kwargs):
                self.aborted = threading.Event()
                self.finished_callback = kwargs["finished_callback"]

            def __enter__(self):
                self.worker = threading.Thread(target=self._stall, daemon=True)
                self.worker.start()
                return self

            def __exit__(self, *args):
                self.abort()
                self.worker.join(timeout=1)
                return False

            def _stall(self):
                while not self.aborted.wait(0.005):
                    pass
                self.finished_callback()

            def abort(self):
                self.aborted.set()

        class CallbackStop(Exception):
            pass

        class CallbackAbort(Exception):
            pass

        fake_sounddevice = types.SimpleNamespace(
            query_hostapis=lambda: [{"name": ROUTE["host_api"]}],
            query_devices=lambda: [
                {
                    "name": ROUTE["output"],
                    "hostapi": 0,
                    "max_output_channels": 2,
                }
            ],
            OutputStream=BlockingStream,
            CallbackStop=CallbackStop,
            CallbackAbort=CallbackAbort,
        )
        previous = sys.modules.get("sounddevice")
        sys.modules["sounddevice"] = fake_sounddevice
        try:
            with self.assertRaises(PlaybackError) as raised:
                SoundDevicePlayback(watchdog_grace_seconds=0.05).play(
                    audio_path, ROUTE, threading.Event()
                )
        finally:
            if previous is None:
                sys.modules.pop("sounddevice", None)
            else:
                sys.modules["sounddevice"] = previous
        self.assertIn("PLAYBACK_TIMEOUT", str(raised.exception))

    def test_playback_open_timeout_is_bounded_and_blocks_reopen(self) -> None:
        audio_path = self.root / "open-timeout.wav"
        with wave.open(str(audio_path), "wb") as stream:
            stream.setnchannels(1)
            stream.setsampwidth(2)
            stream.setframerate(16000)
            stream.writeframes(b"\x01\x00" * 160)

        entered = threading.Event()
        release = threading.Event()

        class SlowOpenStream:
            def __init__(self, *args, **kwargs):
                entered.set()
                release.wait(0.2)

            def abort(self):
                return None

            def close(self):
                return None

        fake_sounddevice = types.SimpleNamespace(
            query_hostapis=lambda: [{"name": ROUTE["host_api"]}],
            query_devices=lambda: [
                {
                    "name": ROUTE["output"],
                    "hostapi": 0,
                    "max_output_channels": 2,
                }
            ],
            OutputStream=SlowOpenStream,
            CallbackStop=type("CallbackStop", (Exception,), {}),
            CallbackAbort=type("CallbackAbort", (Exception,), {}),
        )
        previous = sys.modules.get("sounddevice")
        sys.modules["sounddevice"] = fake_sounddevice
        try:
            playback = SoundDevicePlayback(stream_open_timeout_seconds=0.05)
            started = time.monotonic()
            with self.assertRaises(PlaybackError) as raised:
                playback.play(audio_path, ROUTE, threading.Event())
            elapsed = time.monotonic() - started
            self.assertTrue(entered.is_set())
            self.assertIn("PLAYBACK_OPEN_TIMEOUT", str(raised.exception))
            self.assertLess(elapsed, 0.5)
            release.set()
            time.sleep(0.25)
            with self.assertRaises(PlaybackError) as blocked:
                playback.play(audio_path, ROUTE, threading.Event())
            self.assertIn("AUDIO_BLOCKED", str(blocked.exception))
        finally:
            release.set()
            if previous is None:
                sys.modules.pop("sounddevice", None)
            else:
                sys.modules["sounddevice"] = previous

    def test_service_pauses_pending_after_playback_open_timeout(self) -> None:
        class TimeoutPlayback(NullPlayback):
            def play(self, audio_path, route, cancel_event):
                raise PlaybackError("PLAYBACK_OPEN_TIMEOUT: fixture stream open")

        adapter = FakeGenerationAdapter(delay=0.01)
        service = SpeechService(
            self.root,
            adapters={"cosyvoice": adapter, "breeze": adapter},
            playback=TimeoutPlayback(),
        )

        def wait_local(request_id: str, status: str, timeout: float = 4.0) -> dict:
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                for item in service.snapshot()["snapshot"]["queue"]:
                    if item["id"] == request_id and item["status"] == status:
                        return item
                time.sleep(0.01)
            self.fail(f"timeout waiting for local {request_id}={status}: {service.snapshot()}")

        try:
            first = service.handle_command(self.request("open-timeout-first"))["result"]["request_id"]
            pending = service.handle_command(self.request("open-timeout-pending"))["result"]["request_id"]
            failed = wait_local(first, "failed")
            self.assertEqual(failed["error"]["code"], "PLAYBACK_OPEN_TIMEOUT")
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline and service.snapshot()["snapshot"]["state"] != "ERROR":
                time.sleep(0.01)
            self.assertEqual(service.snapshot()["snapshot"]["state"], "ERROR")
            pending_record = next(
                item for item in service.snapshot()["snapshot"]["queue"] if item["id"] == pending
            )
            self.assertEqual(pending_record["status"], "queued")
            blocked = service.handle_command(self.request("open-timeout-blocked"))
            self.assertFalse(blocked["accepted"])
            self.assertEqual(blocked["error"]["code"], "AUDIO_BLOCKED")
            cleared = service.handle_command({"action": "clear_queue", "command_id": "clear-timeout"})
            self.assertTrue(cleared["accepted"])
            self.assertIn(pending, cleared["result"]["removed_request_ids"])
        finally:
            service.close()

    def test_cancel_during_open_keeps_audio_blocked_guard(self) -> None:
        class CancelDuringOpenPlayback:
            def __init__(self):
                self.entered = threading.Event()
                self.open_blocked = False

            def play(self, audio_path, route, cancel_event):
                del audio_path, route
                self.entered.set()
                while not cancel_event.wait(0.01):
                    pass
                self.open_blocked = True
                raise PlaybackCancelled("playback cancelled while opening output")

            def stop(self):
                return None

        adapter = FakeGenerationAdapter(delay=0.01)
        playback = CancelDuringOpenPlayback()
        service = SpeechService(
            self.root,
            adapters={"cosyvoice": adapter, "breeze": adapter},
            playback=playback,
        )

        def wait_local(request_id: str, status: str, timeout: float = 4.0) -> dict:
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                for item in service.snapshot()["snapshot"]["queue"]:
                    if item["id"] == request_id and item["status"] == status:
                        return item
                time.sleep(0.01)
            self.fail(f"timeout waiting for local {request_id}={status}: {service.snapshot()}")

        try:
            current = service.handle_command(self.request("cancel-during-open"))["result"]["request_id"]
            wait_local(current, "playing")
            self.assertTrue(playback.entered.wait(1.0))
            pending = service.handle_command(self.request("held-after-open-cancel"))["result"]["request_id"]
            self.assertTrue(service.handle_command({"action": "stop_speaking"})["accepted"])
            wait_local(current, "cancelled")
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                snapshot = service.snapshot()["snapshot"]
                if snapshot["state"] == "ERROR" and snapshot["audio_blocked"]:
                    break
                time.sleep(0.01)
            snapshot = service.snapshot()["snapshot"]
            self.assertEqual(snapshot["state"], "ERROR")
            self.assertTrue(snapshot["audio_blocked"])
            pending_record = next(item for item in snapshot["queue"] if item["id"] == pending)
            self.assertEqual(pending_record["status"], "queued")
            blocked = service.handle_command(self.request("after-open-cancel"))
            self.assertFalse(blocked["accepted"])
            self.assertEqual(blocked["error"]["code"], "AUDIO_BLOCKED")
        finally:
            service.close()

    def test_service_reports_startup_audio_error_before_generation(self) -> None:
        class StartupFailurePlayback(NullPlayback):
            def prepare(self):
                raise PlaybackError("DEVICE_INIT_TIMEOUT: fixture PortAudio init")

        service = SpeechService(
            self.root,
            adapters={"cosyvoice": self.adapter, "breeze": self.adapter},
            playback=StartupFailurePlayback(),
        )
        try:
            self.assertEqual(service.snapshot()["snapshot"]["state"], "ERROR")
            ack = service.handle_command(self.request("startup-failure"))
            self.assertFalse(ack["accepted"])
            self.assertEqual(ack["error"]["code"], "AUDIO_INIT_FAILED")
            self.assertFalse(self.adapter.started.is_set())
        finally:
            service.close()

    def test_playback_normalizes_source_to_route_format(self) -> None:
        audio_path = self.root / "normalize.wav"
        with wave.open(str(audio_path), "wb") as stream:
            stream.setnchannels(1)
            stream.setsampwidth(2)
            stream.setframerate(16000)
            stream.writeframes(b"\x01\x00" * 160)

        observed = {"blocks": []}

        class RecordingStream:
            def __init__(self, *args, **kwargs):
                observed.update(kwargs)
                self.callback = kwargs["callback"]
                self.finished_callback = kwargs["finished_callback"]

            def __enter__(self):
                import numpy as np

                outdata = np.zeros((960, 2), dtype="float32")
                status = types.SimpleNamespace(output_underflow=False)
                try:
                    self.callback(outdata, 960, None, status)
                except CallbackStop:
                    pass
                observed["blocks"].append(outdata)
                self.finished_callback()
                return self

            def __exit__(self, *args):
                return False

            def abort(self):
                return None

        class CallbackStop(Exception):
            pass

        class CallbackAbort(Exception):
            pass

        fake_sounddevice = types.SimpleNamespace(
            query_hostapis=lambda: [{"name": ROUTE["host_api"]}],
            query_devices=lambda: [
                {
                    "name": ROUTE["output"],
                    "hostapi": 0,
                    "max_output_channels": 2,
                }
            ],
            OutputStream=RecordingStream,
            CallbackStop=CallbackStop,
            CallbackAbort=CallbackAbort,
        )
        previous = sys.modules.get("sounddevice")
        sys.modules["sounddevice"] = fake_sounddevice
        try:
            result = SoundDevicePlayback(watchdog_grace_seconds=0.05).play(
                audio_path, ROUTE, threading.Event()
            )
        finally:
            if previous is None:
                sys.modules.pop("sounddevice", None)
            else:
                sys.modules["sounddevice"] = previous
        self.assertEqual(observed["samplerate"], 48000)
        self.assertEqual(observed["channels"], 2)
        self.assertEqual(result.source_sample_rate, 16000)
        self.assertEqual(result.source_channels, 1)
        self.assertEqual(result.rendered_sample_rate, 48000)
        self.assertEqual(result.rendered_channels, 2)
        self.assertGreater(sum(len(block) for block in observed["blocks"]), 0)
        self.assertTrue(all(block.shape[1] == 2 for block in observed["blocks"]))

    def test_failed_then_recover_and_profile_snapshot(self) -> None:
        self.adapter.fail_next = True
        failed = self.service.handle_command(self.request("bad"))["result"]["request_id"]
        self.wait_status(failed, "failed")
        good = self.service.handle_command(self.request("good", profile="reference-female"))["result"]["request_id"]
        self.wait_status(good, "completed")
        self.wait_state("IDLE")
        records = self.service.snapshot()["snapshot"]["queue"]
        failed_record = next(item for item in records if item["id"] == failed)
        good_record = next(item for item in records if item["id"] == good)
        self.assertEqual(failed_record["status"], "failed")
        self.assertEqual(good_record["profile_snapshot"]["id"], "reference-female")
        self.assertEqual(self.service.snapshot()["snapshot"]["state"], "IDLE")

    def test_post_play_storage_failure_keeps_completed_status(self) -> None:
        def fail_after_play(*args, **kwargs):
            raise sqlite3.OperationalError("fixture database busy")

        self.service._store.record_completed = fail_after_play
        request_id = self.service.handle_command(self.request("storage-failure"))["result"]["request_id"]
        self.wait_status(request_id, "completed")
        deadline = time.monotonic() + 4
        record = None
        while time.monotonic() < deadline:
            record = next(
                item
                for item in self.service.snapshot()["snapshot"]["queue"]
                if item["id"] == request_id
            )
            if record["error"] is not None:
                break
            time.sleep(0.01)
        self.assertIsNotNone(record["error"])
        self.assertEqual(record["error"]["code"], "TRANSCRIPT_STORAGE_FAILED")
        self.assertEqual(self.service.snapshot()["snapshot"]["transcript"], [])

    def test_mic_rule_agent_rejection_and_transcript_only_after_play(self) -> None:
        wrong = self.service.handle_command({
            **self.request("loopback", enqueue=False),
            "request": {**self.request("loopback")["request"], "source": "stt", "metadata": {"route": ROUTE, "capture_source": "loopback"}},
        })
        self.assertFalse(wrong["accepted"])
        agent = self.service.handle_command({
            **self.request("agent"),
            "request": {**self.request("agent")["request"], "source": "agent"},
        })
        self.assertFalse(agent["accepted"])
        self.adapter.start_gate = threading.Event()
        cancelled = self.service.handle_command(self.request("cancel"))["result"]["request_id"]
        self.wait_status(cancelled, "generating")
        self.service.handle_command({"action": "stop_speaking"})
        self.adapter.start_gate.set()
        cancelled_record = self.wait_status(cancelled, "cancelled")
        self.assertEqual(cancelled_record["error"]["code"], "CANCELLED")
        self.assertEqual(cancelled_record["error"]["message"], "語音已取消")
        self.assertEqual(self.service.snapshot()["snapshot"]["transcript"], [])

    def test_system_source_is_persisted_with_system_provider(self) -> None:
        command = self.request("system-message")
        command["request"]["source"] = "system"
        request_id = self.service.handle_command(command)["result"]["request_id"]
        self.wait_status(request_id, "completed")
        event = self.service.snapshot()["snapshot"]["transcript"][0]
        self.assertEqual(event["source"], "system")
        self.assertEqual(event["provider"], "system")
        self.assertEqual(event["transcript_provider"], "system")

    def test_unverified_cancel_is_retained_as_cleanup_failure(self) -> None:
        self.adapter.start_gate = threading.Event()
        self.adapter.cancel_result = {
            "event": "group_cancel_unverified",
            "reason": "fixture missing pid identity",
        }
        request_id = self.service.handle_command(self.request("unverified-cancel"))["result"]["request_id"]
        self.wait_status(request_id, "generating")
        pending_id = self.service.handle_command(self.request("held-pending"))["result"]["request_id"]
        self.service.handle_command({"action": "stop_speaking"})
        self.adapter.start_gate.set()
        record = self.wait_status(request_id, "cancelled")
        self.assertEqual(record["error"]["code"], "CANCEL_CLEANUP_FAILED")
        self.assertEqual(record["error"]["message"], "語音已取消，但背景程序清理未驗證；請重新啟動服務")
        self.assertFalse(record["error"]["cleanup_verified"])
        self.wait_state("ERROR")
        blocked = self.service.handle_command(self.request("blocked-submit"))
        self.assertFalse(blocked["accepted"])
        self.assertEqual(blocked["error"]["code"], "SERVICE_BLOCKED")
        cleared = self.service.handle_command({"action": "clear_queue", "command_id": "clear-blocked"})
        self.assertTrue(cleared["accepted"])
        self.assertIn(pending_id, cleared["result"]["removed_request_ids"])
        self.assertEqual(self.service.snapshot()["snapshot"]["transcript"], [])

    def test_nested_pid_audit_also_blocks_new_generation(self) -> None:
        self.adapter.start_gate = threading.Event()
        self.adapter.cancel_result = {
            "pid_audit": {
                "events": [
                    {"event": "started"},
                    {"event": "group_cancel_unverified", "identity_verified": False},
                ]
            }
        }
        request_id = self.service.handle_command(self.request("nested-unverified"))["result"]["request_id"]
        self.wait_status(request_id, "generating")
        self.service.handle_command({"action": "stop_speaking"})
        self.adapter.start_gate.set()
        record = self.wait_status(request_id, "cancelled")
        self.assertEqual(record["error"]["code"], "CANCEL_CLEANUP_FAILED")
        self.assertEqual(record["error"]["cleanup_event"], "group_cancel_unverified")
        self.wait_state("ERROR")
        blocked = self.service.handle_command(self.request("blocked-after-nested"))
        self.assertFalse(blocked["accepted"])
        self.assertEqual(blocked["error"]["code"], "SERVICE_BLOCKED")

    def test_emitted_snapshots_use_state_and_request_enums(self) -> None:
        request_id = self.service.handle_command(self.request("enum-check"))["result"]["request_id"]
        self.wait_status(request_id, "completed")
        self.wait_state("IDLE")
        self.assert_emitted_contract_enums()

    def test_twenty_requests_no_fixture_process_left(self) -> None:
        ids = [self.service.handle_command(self.request(f"r{i}"))["result"]["request_id"] for i in range(20)]
        self.wait_all(ids, timeout=12)
        self.assertTrue(all(process.poll() is not None for process in self.adapter.processes))
        self.assertEqual(len(self.service.snapshot()["snapshot"]["transcript"]), 20)
        db = sqlite3.connect(self.root / "artifacts/tts/tts.sqlite3")
        self.assertEqual(db.execute("SELECT COUNT(*) FROM speech_requests").fetchone()[0], 20)
        db.close()


if __name__ == "__main__":
    unittest.main()
