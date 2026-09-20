"""Audit local dataset audio files and write a provenance-friendly CSV manifest.

這支工具只讀取音訊 metadata 與檔案 bytes，不會重採樣、降噪、切片或覆寫
dataset/raw。真正的音訊處理應該是後續明確的 pipeline stage，避免把原始證據
與衍生資料混在一起。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
import sys
from pathlib import Path

import numpy as np
import soundfile as sf


MANIFEST_FIELDS = [
    "relative_path",
    "format",
    "subtype",
    "sample_rate",
    "channels",
    "frames",
    "duration_seconds",
    "rms",
    "peak",
    "non_silent_ratio",
    "sha256",
    "source_id",
    "source_sha256",
    "license_or_permission",
    "batch_id",
    "parent_relative_path",
    "derivation",
    "status",
    "manual_notes",
    "notes",
]

SOURCE_REGISTER_FIELDS = [
    "relative_path",
    "source_id",
    "source_sha256",
    "license_or_permission",
    "batch_id",
    "parent_relative_path",
    "derivation",
]


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Hash a file incrementally so large recordings do not fill memory."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def measure_audio(path: Path) -> tuple[float, float, float]:
    """以 block 方式量測音量，避免把長錄音一次載入記憶體。"""

    squared_sum = 0.0
    sample_count = 0
    peak = 0.0
    non_silent_count = 0
    with sf.SoundFile(str(path), mode="r") as audio:
        for block in audio.blocks(blocksize=262144, dtype="float32", always_2d=True):
            absolute = np.abs(block)
            squared_sum += float(np.square(block, dtype=np.float64).sum())
            sample_count += int(block.size)
            peak = max(peak, float(absolute.max(initial=0.0)))
            non_silent_count += int(np.count_nonzero(absolute > 1e-4))
    if sample_count == 0:
        return 0.0, peak, 0.0
    rms = float(np.sqrt(squared_sum / sample_count))
    return rms, peak, float(non_silent_count / sample_count)


def audit_audio(
    path: Path,
    root: Path,
    allowed_rates: set[int],
    source: dict[str, str],
    previous: dict[str, str],
) -> dict[str, str | int]:
    """Read one file's metadata and classify it without changing the file."""

    relative_path = path.relative_to(root).as_posix()
    try:
        info = sf.info(str(path))
        notes: list[str] = []
        if info.format != "WAV":
            notes.append("非 WAV；正式訓練前需明確轉檔並保留來源")
        if info.channels != 1:
            notes.append("不是單聲道")
        if info.samplerate not in allowed_rates:
            notes.append(
                f"取樣率 {info.samplerate} 不在允許集合 "
                f"{sorted(allowed_rates)}"
            )

        rms, peak, non_silent_ratio = measure_audio(path)
        if peak < 1e-4 or rms < 1e-5 or non_silent_ratio < 0.01:
            notes.append("音訊疑似全靜音或有效訊號比例過低；需人工聽測")

        file_hash = sha256_file(path)
        # source-register 是目前有效的來源與授權事實來源；舊 manifest 只可保留
        # 人工備註，不得在來源登記移除或音檔替換後把舊 provenance 補回來。
        provenance = {
            field: source.get(field, "")
            for field in SOURCE_REGISTER_FIELDS
            if field != "relative_path"
        }
        # 原始檔沒有父檔是合法狀態；此時由 derivation 明確寫「原始」即可。
        missing_provenance = [
            field
            for field, value in provenance.items()
            if field != "parent_relative_path" and not value
        ]
        if missing_provenance:
            notes.append(
                "缺少 source-register 欄位：" + ", ".join(missing_provenance)
            )
        registered_hash = (source.get("source_sha256") or "").strip().lower()
        if not registered_hash or not re.fullmatch(r"[0-9a-f]{64}", registered_hash):
            notes.append("source-register 缺少合法 source_sha256；音檔需重新登記")
        elif registered_hash != file_hash:
            notes.append("音檔 SHA-256 與 source-register 的 source_sha256 不一致；需重新審核")

        # 只有人工欄位可以跨次保留；notes 是本次機器判定，不能升格成人工備註。
        manual_notes = (previous.get("manual_notes") or "").strip()
        status = "ok" if not notes else "needs-review"
        rendered_notes = list(notes)
        if manual_notes:
            rendered_notes.append(f"人工備註：{manual_notes}")
        return {
            "relative_path": relative_path,
            "format": info.format,
            "subtype": info.subtype,
            "sample_rate": info.samplerate,
            "channels": info.channels,
            "frames": info.frames,
            "duration_seconds": f"{info.duration:.3f}",
            "rms": f"{rms:.8f}",
            "peak": f"{peak:.8f}",
            "non_silent_ratio": f"{non_silent_ratio:.6f}",
            "sha256": file_hash,
            **provenance,
            "status": status,
            "manual_notes": manual_notes,
            "notes": "; ".join(rendered_notes),
        }
    except Exception as error:  # pragma: no cover - exercised by corrupt inputs
        return {
            "relative_path": relative_path,
            "format": "",
            "subtype": "",
            "sample_rate": "",
            "channels": "",
            "frames": "",
            "duration_seconds": "",
            "rms": "",
            "peak": "",
            "non_silent_ratio": "",
            "sha256": sha256_file(path),
            **{
                field: source.get(field, "")
                for field in SOURCE_REGISTER_FIELDS
                if field != "relative_path"
            },
            "status": "error",
            "manual_notes": (previous.get("manual_notes") or "").strip(),
            "notes": f"metadata 讀取失敗：{error}",
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit WAV files and create a dataset provenance manifest."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("dataset/raw"),
        help="原始音訊根目錄（預設：dataset/raw）",
    )
    parser.add_argument(
        "--source-register",
        type=Path,
        default=Path("dataset/manifests/source-register.csv"),
        help="人工維護的來源／授權／批次登記 CSV",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("dataset/manifests/raw-audit.csv"),
        help="輸出的 CSV manifest（預設：dataset/manifests/raw-audit.csv）",
    )
    parser.add_argument(
        "--sample-rate",
        type=int,
        nargs="+",
        default=[40000, 48000],
        help="接受的訓練取樣率（預設：40000 48000）",
    )
    parser.add_argument(
        "--fail-on-invalid",
        action="store_true",
        help="若有 error 或 needs-normalization，回傳非零狀態",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    manifest = args.manifest.resolve()
    source_register = args.source_register.resolve()
    root.mkdir(parents=True, exist_ok=True)
    manifest.parent.mkdir(parents=True, exist_ok=True)

    source_rows: dict[str, dict[str, str]] = {}
    if source_register.is_file():
        with source_register.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                relative_path = (row.get("relative_path") or "").strip()
                if relative_path:
                    source_rows[relative_path] = row

    # 重新產生 audit 時只保留舊 manifest 的 manual_notes；機器 notes 與 provenance
    # 必須依本次檔案與目前 source-register 重新計算。
    previous_rows: dict[str, dict[str, str]] = {}
    if manifest.is_file():
        with manifest.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                relative_path = (row.get("relative_path") or "").strip()
                if relative_path:
                    previous_rows[relative_path] = row

    rows = [
        audit_audio(
            path,
            root,
            set(args.sample_rate),
            source_rows.get(path.relative_to(root).as_posix(), {}),
            previous_rows.get(path.relative_to(root).as_posix(), {}),
        )
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.suffix.lower() == ".wav"
    ]

    # newline="" 讓 Windows CSV 不產生多餘空白列，便於 Git diff 與後續工具讀取。
    with manifest.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    invalid = sum(row["status"] != "ok" for row in rows)
    print(
        f"audited={len(rows)} invalid={invalid} "
        f"source_register={source_register} manifest={manifest}"
    )
    if args.fail_on_invalid and (not rows or invalid):
        if not rows:
            print("ERROR: dataset/raw 沒有 WAV；不能把空資料集視為通過。", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
