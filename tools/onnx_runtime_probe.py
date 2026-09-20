"""以合成輸入執行一個 RVC ONNX 模型，記錄實際使用的 execution provider。

這個 probe 不使用麥克風、不修改音訊裝置，也不會寫入模型或訓練資料。
它只用固定形狀的零值特徵確認 ONNX session 能否真的完成一次推論，並將
provider、輸出摘要與模型 SHA-256 寫成 JSON，避免把 provider 清單誤當成
實際 GPU 運算證據。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import onnxruntime as ort


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def write_result(path: Path, result: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one synthetic RVC ONNX inference and record provider evidence."
    )
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument(
        "--artifact",
        type=Path,
        default=Path("artifacts/onnx-runtime-probe.json"),
    )
    parser.add_argument(
        "--provider",
        default="CUDAExecutionProvider",
        help="優先要求的 ONNX Runtime provider；失敗時保留 CPU fallback。",
    )
    parser.add_argument(
        "--run-id",
        default="",
        help="由呼叫端產生的本次執行識別碼，避免沿用舊 artifact。",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    model = args.model.resolve()
    artifact = args.artifact.resolve()
    started_at = datetime.now(timezone.utc).isoformat()

    result: dict[str, object] = {
        "test": "synthetic-rvc-onnx-inference",
        "run_id": args.run_id,
        "started_at_utc": started_at,
        "model": str(model),
        "requested_provider": args.provider,
        "onnxruntime_version": ort.__version__,
        "available_providers": ort.get_available_providers(),
    }

    if not model.is_file():
        result.update({"status": "error", "error": f"找不到模型：{model}"})
        write_result(artifact, result)
        print(json.dumps(result, ensure_ascii=False))
        return 2

    result["model_sha256"] = sha256_file(model)
    providers = [args.provider, "CPUExecutionProvider"]
    if args.provider == "CPUExecutionProvider":
        providers = ["CPUExecutionProvider"]

    try:
        # 啟用 profiling，讓報告能辨識「實際執行」的 provider，而不是只看
        # session.get_providers() 或 get_available_providers() 的宣告清單。
        options = ort.SessionOptions()
        options.enable_profiling = True
        options.profile_file_prefix = str(artifact.with_suffix(""))
        session = ort.InferenceSession(str(model), options, providers=providers)
        result["session_providers"] = session.get_providers()

        input_names = {item.name for item in session.get_inputs()}
        expected = {"feats", "p_len", "pitch", "pitchf", "sid"}
        missing = sorted(expected - input_names)
        if missing:
            raise RuntimeError(f"不是預期的 RVC ONNX 輸入，缺少：{missing}")

        # 使用短而固定的特徵長度；這是 runtime smoke test，不是聲音品質測試。
        feature_length = 10
        feed = {
            "feats": np.zeros((1, feature_length, 768), dtype=np.float32),
            "p_len": np.array([feature_length], dtype=np.int64),
            "pitch": np.zeros((1, feature_length), dtype=np.int64),
            "pitchf": np.zeros((1, feature_length), dtype=np.float32),
            "sid": np.array([0], dtype=np.int64),
        }
        output = session.run(None, feed)[0]
        profile_path = Path(session.end_profiling())
        result["output_shape"] = list(output.shape)
        result["output_rms"] = float(np.sqrt(np.mean(np.square(output))))
        result["output_peak"] = float(np.max(np.abs(output)))
        result["profile_path"] = str(profile_path)

        executed_providers: set[str] = set()
        if profile_path.is_file():
            profile = json.loads(profile_path.read_text(encoding="utf-8"))
            for event in profile:
                if event.get("cat") == "Node":
                    provider = event.get("args", {}).get("provider")
                    if provider:
                        executed_providers.add(str(provider))
        result["executed_providers"] = sorted(executed_providers)
        result["status"] = "ok"
    except Exception as error:
        result.update({"status": "error", "error": repr(error)})
        write_result(artifact, result)
        print(json.dumps(result, ensure_ascii=False))
        return 2

    write_result(artifact, result)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
