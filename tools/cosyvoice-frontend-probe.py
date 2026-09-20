"""以固定小輸入實際驗證 CosyVoice speech-tokenizer ONNX provider。

CosyVoice 上游的 CampPlus speaker embedding session 固定使用 CPU；本工具只
測 `speech_tokenizer_v2.onnx`，並以 ONNX Runtime profiling 的 Node provider
作為實際執行證據，不把 `get_available_providers()` 當成 GPU PASS。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe CosyVoice ONNX speech tokenizer provider")
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--library-dir", action="append", default=[])
    args = parser.parse_args()
    if not args.model.is_file():
        raise FileNotFoundError(args.model)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.library_dir:
        old = os.environ.get("LD_LIBRARY_PATH", "")
        os.environ["LD_LIBRARY_PATH"] = ":".join(args.library_dir + ([old] if old else []))

    import onnxruntime as ort

    options = ort.SessionOptions()
    options.enable_profiling = True
    options.profile_file_prefix = str(args.output.with_suffix(".ort-profile"))
    options.log_severity_level = 1
    requested = ["CUDAExecutionProvider", "CPUExecutionProvider"]
    result: dict[str, object] = {
        "status": "BLOCKED",
        "model": str(args.model),
        "requested_providers": requested,
        "available_providers": ort.get_available_providers(),
        "library_dirs": args.library_dir,
        "onnxruntime_version": ort.__version__,
    }
    try:
        session = ort.InferenceSession(str(args.model), sess_options=options, providers=requested)
        result["session_providers"] = session.get_providers()
        inputs: dict[str, np.ndarray] = {}
        for item in session.get_inputs():
            if "length" in item.name.lower():
                inputs[item.name] = np.asarray([50], dtype=np.int32)
            else:
                inputs[item.name] = np.zeros((1, 128, 50), dtype=np.float32)
        outputs = session.run(None, inputs)
        profile_path = Path(session.end_profiling())
        profile_events = json.loads(profile_path.read_text(encoding="utf-8")) if profile_path.is_file() else []
        executed = sorted(
            {
                str(event.get("args", {}).get("provider"))
                for event in profile_events
                if event.get("cat") == "Node" and event.get("args", {}).get("provider")
            }
        )
        result.update(
            {
                "status": "PASS" if "CUDAExecutionProvider" in executed and all(np.isfinite(x).all() for x in outputs) else "WAITING",
                "input_shapes": {key: list(value.shape) for key, value in inputs.items()},
                "output_shapes": [list(value.shape) for value in outputs],
                "finite_outputs": bool(all(np.isfinite(value).all() for value in outputs)),
                "executed_providers": executed,
                "profile_path": str(profile_path),
            }
        )
    except Exception as error:
        result["error"] = f"{type(error).__name__}: {error}"
        try:
            result["profile_path"] = str(Path(session.end_profiling()))  # type: ignore[name-defined]
        except Exception:
            pass
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    sys.exit(main())
