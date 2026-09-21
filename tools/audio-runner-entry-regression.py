"""Regression checks for dependency-safe TTS runner entry/failure handling."""

from __future__ import annotations

import ast
import json
import tempfile
from pathlib import Path

from audio_runner_failure import (
    clear_stale_outputs,
    output_from_argv,
    write_failure_manifest,
)


assert output_from_argv(["--output", "a.wav"]) == Path("a.wav")
assert output_from_argv(["--output=b.wav"]) == Path("b.wav")
assert output_from_argv(["--help", "--output=c.wav"]) is None

for runner_name in ("breeze-tts2-infer.py", "cosyvoice-infer.py"):
    source_path = Path(__file__).with_name(runner_name)
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    top_level_imports = [
        alias.name
        for node in tree.body
        if isinstance(node, ast.Import)
        for alias in node.names
    ] + [
        alias.name
        for node in tree.body
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    ]
    assert not any(name.startswith(("torch", "torchaudio", "breeze_infer", "cosyvoice", "models")) for name in top_level_imports)
    main_node = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "main")
    calls = [
        (
            node.func.id if isinstance(node.func, ast.Name) else node.func.attr,
            node.lineno,
        )
        for node in ast.walk(main_node)
        if isinstance(node, ast.Call) and isinstance(node.func, (ast.Name, ast.Attribute))
    ]
    clear_line = min(line for name, line in calls if name == "clear_stale_outputs")
    parse_line = min(line for name, line in calls if name == "parse_args")
    assert clear_line < parse_line
    assert "except SystemExit as exc" in source_path.read_text(encoding="utf-8")

with tempfile.TemporaryDirectory(prefix="aethertune-runner-entry-") as temp_dir:
    root = Path(temp_dir)
    output = root / "voice.wav"
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
