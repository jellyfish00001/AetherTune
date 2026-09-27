"""可取消、可稽核的 WSL process-group job。

TTS runner 會在 WSL 內建立自己的 ``setsid`` process group。Windows 端只保存
這一個 job 的 pid/token，取消時先用 token 驗證 ``/proc/<pid>/environ``，再對
該 group 發送 TERM/KILL；不以程序名稱或全域掃描方式清理其他 backend。
"""

from __future__ import annotations

import json
import os
import subprocess
import time
import uuid
from pathlib import Path
from threading import Lock
from typing import Mapping, Sequence


class WslJobError(RuntimeError):
    """WSL job 無法安全啟動或取消。"""


def quote_bash(value: str) -> str:
    """以單引號包住一個 bash argument；不讓文字／路徑被 shell 解讀。"""

    return "'" + value.replace("'", "'\\''") + "'"


def to_wsl_path(path: Path | str) -> str:
    """將 Windows drive path 映射到 WSL 的 /mnt/<drive> 路徑。"""

    raw = str(path)
    if len(raw) < 3 or raw[1] != ":":
        raise WslJobError(f"需要 Windows drive path 才能映射 WSL：{raw}")
    return "/mnt/" + raw[0].lower() + raw[2:].replace("\\", "/")


class WslJob:
    """執行一個有明確 identity 的 WSL command。

    ``command`` 是 WSL 內要執行的 argv；本類別負責安全 quoting、setsid、
    stdout/stderr redirection、pid record 及 group cancellation。生成 adapter
    不應直接呼叫 ``wsl.exe``，避免取消時失去 process-group ownership。
    """

    def __init__(
        self,
        *,
        root: Path,
        job_dir: Path,
        command: Sequence[str],
        distro: str = "Ubuntu",
        env: Mapping[str, str] | None = None,
        executable: str = "wsl.exe",
        popen_factory=subprocess.Popen,
        run_factory=subprocess.run,
    ) -> None:
        self.root = root.resolve()
        self.job_dir = job_dir.resolve()
        self.command = [str(part) for part in command]
        self.distro = distro
        self.env = {str(key): str(value) for key, value in (env or {}).items()}
        self.executable = executable
        self._popen_factory = popen_factory
        self._run_factory = run_factory
        self.token = uuid.uuid4().hex
        self.pid_path = self.job_dir / "wsl-pid.json"
        self.cancel_marker_path = self.job_dir / "cancel.marker"
        self.launch_path = self.job_dir / "launch.sh"
        self.cancel_script_path = self.job_dir / "cancel.sh"
        self.stdout_path = self.job_dir / "stdout.log"
        self.stderr_path = self.job_dir / "stderr.log"
        self.cancel_log_path = self.job_dir / "cancel.log"
        self._process: subprocess.Popen | None = None
        self._stdout = None
        self._stderr = None
        self._audit: list[dict] = []
        self._cancel_lock = Lock()
        self._last_cancel_result: dict | None = None

    @property
    def process(self) -> subprocess.Popen | None:
        return self._process

    @property
    def pid(self) -> int | None:
        return self._process.pid if self._process is not None else None

    def _script(self) -> str:
        """Return the file-backed WSL launcher body.

        Keeping this body in a file avoids passing ``$$``, ``$pid`` and nested
        quoted runner arguments through Windows -> wsl.exe -> shell parsing.
        """

        if not self.command:
            raise WslJobError("WSL command 不可為空")
        pid_path = quote_bash(to_wsl_path(self.pid_path))
        token = quote_bash(self.token)
        cancel_marker = quote_bash(to_wsl_path(self.cancel_marker_path))
        argv = " ".join(quote_bash(arg) for arg in self.command)
        # This script is run by ``setsid --wait``.  ``$$`` is therefore
        # expanded inside the Linux process group leader, never by a Windows
        # command shell, and remains the PID/PGID we own.
        return "\n".join(
            [
                "#!/usr/bin/env sh",
                "set -eu",
                f"export AETHERTUNE_TTS_JOB_TOKEN={token}",
                f"if test -f {cancel_marker}; then exit 130; fi",
                f"printf '{{\"pid\":%s,\"token\":\"%s\"}}\\n' \"$$\" {token} > {pid_path}",
                f"if test -f {cancel_marker}; then exit 130; fi",
                f"exec {argv}",
                "",
            ]
        )

    def _cancel_script(self, pid: int) -> str:
        """Return a file-backed, token-checked group cancellation script."""

        token = quote_bash(self.token)
        pid_literal = quote_bash(str(pid))
        return "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -eu",
                f"pid={pid_literal}",
                f"token={token}",
                # A runner can finish between generation completion and the
                # adapter's final cleanup.  If the recorded process group is
                # already absent, cleanup is verified without reading a
                # potentially reused /proc/<pid> identity.
                'if ! kill -0 -- "-$pid" 2>/dev/null; then printf \'group_absent_before_cancel\\n\'; exit 0; fi',
                'test -r "/proc/$pid/environ"',
                'actual=$(tr \'\\0\' \'\\n\' < "/proc/$pid/environ" | sed -n \'s/^AETHERTUNE_TTS_JOB_TOKEN=//p\')',
                'test "$actual" = "$token"',
                'kill -TERM -- "-$pid" || true',
                "for i in 1 2 3 4 5 6 7 8 9 10; do",
                '  if kill -0 -- "-$pid" 2>/dev/null; then sleep 0.1; else exit 0; fi',
                "done",
                'kill -KILL -- "-$pid" || true',
                "sleep 0.1",
                'if kill -0 -- "-$pid" 2>/dev/null; then exit 42; else exit 0; fi',
                "",
            ]
        )

    def start(self) -> "WslJob":
        if self._process is not None:
            raise WslJobError("WSL job 已啟動")
        self.job_dir.mkdir(parents=True, exist_ok=True)
        self.pid_path.unlink(missing_ok=True)
        self.cancel_marker_path.unlink(missing_ok=True)
        self.cancel_script_path.unlink(missing_ok=True)
        self.launch_path.write_text(self._script(), encoding="utf-8", newline="\n")
        self._stdout = self.stdout_path.open("wb")
        self._stderr = self.stderr_path.open("wb")
        child_env = os.environ.copy()
        child_env.update(self.env)
        child_env["AETHERTUNE_TTS_JOB_TOKEN"] = self.token
        command = [
            self.executable,
            "-d",
            self.distro,
            "--exec",
            "setsid",
            "--wait",
            "sh",
            to_wsl_path(self.launch_path),
        ]
        try:
            self._process = self._popen_factory(
                command,
                cwd=str(self.root),
                env=child_env,
                stdin=subprocess.DEVNULL,
                stdout=self._stdout,
                stderr=self._stderr,
                shell=False,
            )
        except Exception:
            self._close_files()
            raise
        self._audit.append(
            {
                "event": "started",
                "at": time.time(),
                "host_pid": self._process.pid,
                "token": self.token,
                "pid_file": str(self.pid_path),
                "launch_file": str(self.launch_path),
                "stdout": str(self.stdout_path),
                "stderr": str(self.stderr_path),
            }
        )
        return self

    def _read_pid_record(self) -> dict | None:
        try:
            record = json.loads(self.pid_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return None
        if not isinstance(record, dict):
            return None
        pid = record.get("pid")
        token = record.get("token")
        if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
            return None
        if token != self.token:
            return None
        return {"pid": pid, "token": token}

    def cancel(self, reason: str = "cancelled") -> dict:
        """只取消本 job 的 WSL group，並回傳可寫入 evidence 的 audit。"""

        # cancel 可能同時由 Stop、worker finally 及 shutdown 呼叫。序列化
        # ownership audit，並保留已驗證的成功結果；第二次呼叫不能因 pid
        # 已消失而把第一次的 group_cancelled 降級成 failed/unverified。
        with self._cancel_lock:
            if self._last_cancel_result is not None:
                result = dict(self._last_cancel_result)
                result["idempotent"] = True
                self._audit.append(
                    {"event": "cancel_reused", "at": time.time(), "reason": reason, "pid": result.get("pid")}
                )
                return result

            requested = {"event": "cancel_requested", "at": time.time(), "reason": reason}
            self._audit.append(requested)
            record = self._read_pid_record()
            if record is None:
                try:
                    self.cancel_marker_path.write_text(reason, encoding="utf-8")
                except OSError:
                    pass
                # setsid 可能尚未寫 pid record；短暫等待 marker 生效或 identity
                # 出現，避免 startup race 直接 terminate host 造成 orphan group。
                deadline = time.monotonic() + 1.0
                while time.monotonic() < deadline:
                    time.sleep(0.05)
                    record = self._read_pid_record()
                    if record is not None:
                        break
                    if self._process is not None and self._process.poll() is not None:
                        break
            if record is None:
                result = {
                    "event": "group_cancel_unverified",
                    "at": time.time(),
                    "reason": "pid record missing or token mismatch",
                    "token": self.token,
                }
                self._audit.append(result)
                # 這是 ownership 無法證明時的最後退路，只針對此 WSL host pid；不
                # 掃描、不依程序名稱殺其他 engine，並保留明確的 unverified audit。
                if self._process is not None and self._process.poll() is None:
                    try:
                        self._process.terminate()
                        result["host_terminate"] = True
                    except OSError as exc:
                        result["host_terminate_error"] = str(exc)
                return result

            pid = record["pid"]
            try:
                self.cancel_script_path.write_text(
                    self._cancel_script(pid), encoding="utf-8", newline="\n"
                )
                self.cancel_log_path.parent.mkdir(parents=True, exist_ok=True)
                with self.cancel_log_path.open("ab") as cancel_log:
                    try:
                        completed = self._run_factory(
                            [
                                self.executable,
                                "-d",
                                self.distro,
                                "--exec",
                                "bash",
                                to_wsl_path(self.cancel_script_path),
                            ],
                            cwd=str(self.root),
                            stdin=subprocess.DEVNULL,
                            stdout=cancel_log,
                            stderr=subprocess.STDOUT,
                            shell=False,
                            check=False,
                            timeout=3,
                        )
                    except subprocess.TimeoutExpired:
                        completed = None
            except (OSError, subprocess.SubprocessError) as exc:
                completed = None
                cancel_error = str(exc)
            else:
                cancel_error = None

            if completed is not None and completed.returncode == 0:
                group_absent_before_cancel = False
                try:
                    group_absent_before_cancel = (
                        "group_absent_before_cancel"
                        in self.cancel_log_path.read_text(encoding="utf-8", errors="replace")
                    )
                except OSError:
                    pass
                result = {
                    "event": "group_cancelled",
                    "at": time.time(),
                    "pid": pid,
                    "token": self.token,
                    "identity_verified": True,
                    "returncode": completed.returncode,
                    "group_absent_before_cancel": group_absent_before_cancel,
                }
                self._last_cancel_result = dict(result)
            else:
                result = {
                    "event": "group_cancel_failed",
                    "at": time.time(),
                    "pid": pid,
                    "token": self.token,
                    "identity_verified": False,
                    "returncode": None if completed is None else completed.returncode,
                }
                if cancel_error:
                    result["error"] = cancel_error
                if self._process is not None and self._process.poll() is None:
                    try:
                        self._process.terminate()
                        result["host_terminate"] = True
                    except OSError as exc:
                        result["host_terminate_error"] = str(exc)
            self._audit.append(result)
            return result

    def wait(self, timeout: float | None = None) -> int | None:
        if self._process is None:
            return None
        try:
            return self._process.wait(timeout=timeout)
        finally:
            self._close_files()

    def poll(self) -> int | None:
        return self._process.poll() if self._process is not None else None

    def audit(self) -> dict:
        return {
            "token": self.token,
            "host_pid": self.pid,
            "pid_record": self._read_pid_record(),
            "cancel_marker": str(self.cancel_marker_path),
            "launch_file": str(self.launch_path),
            "cancel_file": str(self.cancel_script_path),
            "events": list(self._audit),
            "stdout": str(self.stdout_path),
            "stderr": str(self.stderr_path),
            "cancel_log": str(self.cancel_log_path),
        }

    def _close_files(self) -> None:
        for handle in (self._stdout, self._stderr):
            if handle is not None:
                try:
                    handle.close()
                except OSError:
                    pass
        self._stdout = None
        self._stderr = None


__all__ = ["WslJob", "WslJobError", "quote_bash", "to_wsl_path"]
