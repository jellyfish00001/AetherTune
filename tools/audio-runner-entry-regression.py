"""Regression checks for dependency-safe TTS runner entry/failure handling.

這裡使用真正的 runner subprocess 驗證 help、parser failure 與 stale
artifact cleanup；AST 檢查只補充確認第三方模型 import 沒有回到 module top-level。
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

from audio_runner_failure import (
    clear_stale_outputs,
    output_from_argv,
    write_failure_manifest,
)


def assert_output_scan() -> None:
    """確認預掃描和 argparse 的別名、最後值及 help 例外一致。"""

    assert output_from_argv(["--output", "first.wav", "--output=last.wav"]) == Path("last.wav")
    assert output_from_argv(["--out", "first.wav", "--out=last.wav"]) == Path("last.wav")
    assert output_from_argv(["--output", "first.wav", "--out", "last.wav"]) == Path("last.wav")
    assert output_from_argv(["--output", "first.wav", "--unknown"]) == Path("first.wav")
    assert output_from_argv(["--output", "first.wav", "--help"]) is None
    assert output_from_argv(["--output", "first.wav", "-h"]) is None


def assert_top_level_imports_are_safe(source_path: Path) -> None:
    """確認模型／音訊第三方依賴只在 main 內延後載入。"""

    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(source_path))
    forbidden = (
        "torch",
        "torchaudio",
        "soundfile",
        "audio_output_validation",
        "breeze_infer",
        "cosyvoice",
        "models",
    )
    for node in tree.body:
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            modules = [node.module or ""]
        else:
            continue
        assert not any(
            module == name or module.startswith(f"{name}.")
            for module in modules
            for name in forbidden
        ), f"第三方 runner import 不得在 top-level: {source_path}: {modules}"

    main_node = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "main"
    )
    calls = [
        (node.func.id if isinstance(node.func, ast.Name) else node.func.attr, node.lineno)
        for node in ast.walk(main_node)
        if isinstance(node, ast.Call) and isinstance(node.func, (ast.Name, ast.Attribute))
    ]
    clear_line = min(line for name, line in calls if name == "clear_stale_outputs")
    parse_line = min(line for name, line in calls if name == "parse_args")
    assert clear_line < parse_line
    assert "except SystemExit as exc" in source


def run_runner(runner: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    """以目前 Python 環境真正啟動 runner，保留 stdout/stderr 供失敗診斷。"""

    return subprocess.run(
        [sys.executable, str(runner), *args],
        cwd=runner.parent.parent,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )


def assert_help_preserves_stale(runner: Path, root: Path) -> None:
    output = root / f"{runner.stem}-help.wav"
    manifest = output.with_suffix(".json")
    output.write_bytes(b"old-help")
    manifest.write_text('{"status":"PASS","marker":"old-help"}', encoding="utf-8")
    result = run_runner(runner, ["--output", str(output), "--help"])
    assert result.returncode == 0, result.stderr
    assert output.read_bytes() == b"old-help"
    assert json.loads(manifest.read_text(encoding="utf-8"))["marker"] == "old-help"


def assert_parse_failure_cleans(
    runner: Path, root: Path, option_args: Callable[[Path], list[str]], case_name: str
) -> None:
    output = root / f"{runner.stem}-{case_name}.wav"
    manifest = output.with_suffix(".json")
    output.write_bytes(b"old-parse")
    manifest.write_text('{"status":"PASS","marker":"old-parse"}', encoding="utf-8")
    result = run_runner(runner, [*option_args(output), "--definitely-invalid"])
    assert result.returncode == 2, (result.returncode, result.stdout, result.stderr)
    assert not output.exists(), output
    failure = json.loads(manifest.read_text(encoding="utf-8"))
    assert failure["status"] == "FAIL", failure
    assert failure["output"]["path"] == str(output), failure
    assert failure["backend"]


def main() -> int:
    assert_output_scan()
    runner_root = Path(__file__).parent
    runners = [runner_root / "breeze-tts2-infer.py", runner_root / "cosyvoice-infer.py"]
    for runner in runners:
        assert_top_level_imports_are_safe(runner)

    with tempfile.TemporaryDirectory(prefix="aethertune-runner-entry-") as temp_dir:
        root = Path(temp_dir)
        for runner in runners:
            assert_help_preserves_stale(runner, root)
            assert_parse_failure_cleans(runner, root, lambda path: ["--output", str(path)], "output-separated")
            assert_parse_failure_cleans(runner, root, lambda path: [f"--output={path}"], "output-equals")
            assert_parse_failure_cleans(runner, root, lambda path: ["--out", str(path)], "out-separated")
            assert_parse_failure_cleans(runner, root, lambda path: [f"--out={path}"], "out-equals")

        output = root / "helper.wav"
        manifest = output.with_suffix(".json")
        output.write_bytes(b"old")
        manifest.write_text('{"status":"PASS"}', encoding="utf-8")
        assert clear_stale_outputs(output) == manifest
        assert not output.exists() and not manifest.exists()
        write_failure_manifest(output, "test-runner", RuntimeError("parse failure"))
        failure = json.loads(manifest.read_text(encoding="utf-8"))
        assert failure["status"] == "FAIL"
        assert failure["backend"] == "test-runner"

    print("PASS audio runner entry/failure regression")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
