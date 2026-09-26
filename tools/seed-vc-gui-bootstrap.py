"""Launch the pinned official Seed-VC GUI from an isolated settings overlay."""

from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path


def main() -> None:
    """Read launcher paths from the process environment and run upstream unchanged."""

    required = {
        "AETHERTUNE_SEED_VC_REPO": "Seed-VC repository",
        "AETHERTUNE_SEED_VC_GUI": "official GUI entry point",
        "AETHERTUNE_SEED_VC_CHECKPOINT": "realtime-tiny checkpoint",
        "AETHERTUNE_SEED_VC_CONFIG": "realtime-tiny config",
        "AETHERTUNE_SEED_VC_VAD_PATH": "verified local ModelScope VAD snapshot",
    }
    resolved: dict[str, Path] = {}
    for key, label in required.items():
        value = os.environ.get(key)
        if not value:
            raise SystemExit(f"BLOCKED: launcher did not provide {label} ({key})")
        path = Path(value).resolve()
        if not path.exists():
            raise SystemExit(f"BLOCKED: {label} does not exist: {path}")
        resolved[key] = path

    vad_path = resolved["AETHERTUNE_SEED_VC_VAD_PATH"]
    vad_files = ("model.pt", "config.yaml", "configuration.json", "am.mvn")
    missing_vad = [name for name in vad_files if not (vad_path / name).is_file() or (vad_path / name).stat().st_size <= 0]
    if missing_vad:
        raise SystemExit(
            "BLOCKED: local ModelScope VAD snapshot is incomplete; implicit download is disabled: "
            + ", ".join(missing_vad)
        )

    # 官方 GUI 會呼叫 AutoModel(model="fsmn-vad")，FunASR 預設會向
    # ModelScope 查詢/更新 cache。改在程序記憶體內把這個名稱解析到已驗證的
    # 本機目錄，並關閉 update；不改第三方原始碼或使用者 profile。
    import funasr

    original_auto_model = funasr.AutoModel

    class LocalCacheAutoModel(original_auto_model):
        def __init__(self, *args, **kwargs):
            if kwargs.get("model") == "fsmn-vad":
                kwargs["model"] = str(vad_path)
                kwargs.pop("model_revision", None)
                kwargs.setdefault("disable_update", True)
            super().__init__(*args, **kwargs)

    funasr.AutoModel = LocalCacheAutoModel

    # 保留官方檔案不變；只把它放到 import path，設定相對路徑則由
    # PowerShell launcher 的 artifacts/seed-vc/gui-session 提供。
    sys.path.insert(0, str(resolved["AETHERTUNE_SEED_VC_REPO"]))
    gui_path = resolved["AETHERTUNE_SEED_VC_GUI"]
    sys.argv = [
        str(gui_path),
        "--checkpoint-path",
        str(resolved["AETHERTUNE_SEED_VC_CHECKPOINT"]),
        "--config-path",
        str(resolved["AETHERTUNE_SEED_VC_CONFIG"]),
        "--fp16",
        "False",
        "--gpu",
        "0",
    ]
    runpy.run_path(str(gui_path), run_name="__main__")


if __name__ == "__main__":
    main()
