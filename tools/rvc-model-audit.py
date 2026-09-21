"""驗證 RVC 角色模型的檔案完整性與 provenance metadata。

這支工具不會把未知資料猜成真實值，也不會自動把 candidate 升成 ready。
檔案存在與 hash 正確只代表 integrity；來源、授權、訓練版本、資料批次與
驗證證據缺一時，結果仍是 WAITING。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_FIELDS = [
    "model_id",
    "weights_relative_path",
    "index_relative_path",
    "weights_sha256",
    "index_sha256",
    "sample_rate",
    "f0",
    "version",
    "dataset_batch_id",
    "rvc_revision",
    "trained_at",
    "source_url",
    "license_or_permission",
    "training_environment",
    "status",
]
READY_FIELDS = REQUIRED_FIELDS + ["verification_artifact"]
UNKNOWN = {"", "unknown", "pending", "pending-manual", "replace_with_sha256"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def value(row: dict[str, str], field: str) -> str:
    return (row.get(field) or "").strip()


def resolve_repo_path(raw: str) -> tuple[Path | None, str | None]:
    normalized = (raw or "").strip().replace("\\", "/")
    if not normalized:
        return None, None
    raw_path = Path(normalized)
    candidate = raw_path if raw_path.is_absolute() else ROOT / raw_path
    candidate = candidate.resolve()
    try:
        candidate.relative_to(ROOT)
    except ValueError:
        return None, "path 超出 repository root"
    return candidate, candidate.relative_to(ROOT).as_posix()


def is_unknown(value_text: str) -> bool:
    normalized = (value_text or "").strip().lower()
    return not normalized or normalized in UNKNOWN or bool(
        re.fullmatch(
            r"(?:unknown|pending|pending-manual|tbd|todo|n/?a|not[-_ ]?(?:provided|verified)|replace_with_sha256)(?:[-_ ].*)?",
            normalized,
        )
    )


def verify_artifact_file(
    artifact: Any,
    label: str,
    expected_relative: str,
    expected_sha256: str,
    issues: list[str],
) -> dict[str, Any]:
    evidence: dict[str, Any] = {"label": label}
    if not isinstance(artifact, dict):
        issues.append(f"verification_artifact 缺少 {label} object")
        return evidence
    raw_path = str(artifact.get("path") or "").strip()
    declared_hash = str(artifact.get("sha256") or "").strip().lower()
    evidence.update({"path": raw_path, "sha256": declared_hash})
    path, relative = resolve_repo_path(raw_path)
    if path is None or relative is None:
        issues.append(f"verification_artifact {label} path 無效或超出 repository root")
        return evidence
    evidence["relative_path"] = relative
    if relative.lower() != expected_relative.lower():
        issues.append(f"verification_artifact {label} path 與 register 不一致")
    if not path.is_file():
        issues.append(f"verification_artifact {label} 不存在")
        return evidence
    if not re.fullmatch(r"[0-9a-f]{64}", declared_hash):
        issues.append(f"verification_artifact {label} sha256 不是合法 SHA-256")
    else:
        actual_hash = sha256_file(path)
        evidence["actual_sha256"] = actual_hash
        if actual_hash != declared_hash:
            issues.append(f"verification_artifact {label} SHA-256 不一致")
        if actual_hash != expected_sha256.lower():
            issues.append(f"verification_artifact {label} SHA-256 與 register 不一致")
    return evidence


def validate_verification_artifact(
    raw_artifact_path: str,
    model_id: str,
    expected_weights_relative: str,
    expected_weights_sha256: str,
    expected_index_relative: str,
    expected_index_sha256: str,
    issues: list[str],
) -> dict[str, Any]:
    evidence: dict[str, Any] = {"path": raw_artifact_path}
    artifact_path, artifact_relative = resolve_repo_path(raw_artifact_path)
    if artifact_path is None or artifact_relative is None or not artifact_path.is_file():
        issues.append("verification_artifact 不存在或不在 repository root 內")
        return evidence
    evidence["relative_path"] = artifact_relative
    try:
        payload = json.loads(artifact_path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        issues.append(f"verification_artifact 無法解析 JSON：{exc}")
        return evidence
    if not isinstance(payload, dict):
        issues.append("verification_artifact JSON 根節點必須是 object")
        return evidence
    artifact_status = str(payload.get("status") or "").strip().upper()
    evidence["status"] = artifact_status or None
    if artifact_status != "PASS":
        issues.append(f"verification_artifact status 必須是 PASS（目前 {artifact_status or '空白'}）")
    artifact_model_id = str(payload.get("model_id") or "").strip()
    if artifact_model_id and artifact_model_id != model_id:
        issues.append("verification_artifact model_id 與 register 不一致")
    evidence["model_id"] = artifact_model_id or None

    model_evidence = verify_artifact_file(
        payload.get("model"), "model", expected_weights_relative, expected_weights_sha256, issues
    )
    index_evidence = verify_artifact_file(
        payload.get("index"), "index", expected_index_relative, expected_index_sha256, issues
    )
    for label in ("input", "output"):
        item = payload.get(label)
        if not isinstance(item, dict):
            issues.append(f"verification_artifact 缺少 {label} object")
            continue
        raw_path = str(item.get("path") or "").strip()
        declared_hash = str(item.get("sha256") or "").strip().lower()
        path, relative = resolve_repo_path(raw_path)
        if path is None or relative is None or not path.is_file():
            issues.append(f"verification_artifact {label} path 不存在或超出 repository root")
            continue
        if not re.fullmatch(r"[0-9a-f]{64}", declared_hash):
            issues.append(f"verification_artifact {label} sha256 不是合法 SHA-256")
            continue
        actual_hash = sha256_file(path)
        if actual_hash != declared_hash:
            issues.append(f"verification_artifact {label} SHA-256 不一致")
        evidence[label] = {"relative_path": relative, "sha256": declared_hash, "actual_sha256": actual_hash}
    evidence["model"] = model_evidence
    evidence["index"] = index_evidence
    return evidence


def audit_row(row: dict[str, str], seen_ids: set[str], registered_weights: set[str], registered_indexes: set[str]) -> dict[str, Any]:
    model_id = value(row, "model_id") or "<missing-model-id>"
    issues: list[str] = []
    metadata_waiting: list[str] = []
    if model_id in seen_ids:
        issues.append("model_id 重複")
    seen_ids.add(model_id)

    for field in REQUIRED_FIELDS:
        if field not in row:
            issues.append(f"缺少 CSV 欄位 {field}")
        elif is_unknown(value(row, field)):
            metadata_waiting.append(field)

    status = value(row, "status").lower()
    if status not in {"candidate", "ready", "retired"}:
        issues.append("status 必須是 candidate、ready 或 retired")
    if value(row, "f0").lower() not in {"fcpe", "rmvpe"}:
        metadata_waiting.append("f0")

    row_result: dict[str, Any] = {"model_id": model_id, "declared_status": status, "issues": issues, "metadata_waiting": sorted(set(metadata_waiting))}
    for field, suffix in (("weights_relative_path", ".pth"), ("index_relative_path", ".index")):
        raw = value(row, field)
        path, relative = resolve_repo_path(raw) if raw else (None, None)
        row_result[field] = relative or raw
        if not raw or not raw.lower().endswith(suffix):
            issues.append(f"{field} 必須是 {suffix} 路徑")
        if path is None:
            issues.append(f"{field} 路徑無效")
        elif not path.is_file():
            issues.append(f"{field} 不存在")
        else:
            actual = sha256_file(path)
            expected = value(row, f"{field.split('_')[0]}_sha256").lower()
            if not re.fullmatch(r"[0-9a-f]{64}", expected or ""):
                issues.append(f"{field.split('_')[0]}_sha256 不是合法 SHA-256")
            elif actual != expected:
                issues.append(f"{field.split('_')[0]} SHA-256 不一致")
            if field == "weights_relative_path":
                registered_weights.add(relative or raw)
            else:
                registered_indexes.add(relative or raw)

    verification = value(row, "verification_artifact")
    verification_evidence: dict[str, Any] | None = None
    if status == "ready":
        for field in READY_FIELDS:
            if is_unknown(value(row, field)):
                issues.append(f"ready gate 缺少 {field}")
        if verification and not is_unknown(verification):
            weights_relative = resolve_repo_path(value(row, "weights_relative_path"))[1] or value(row, "weights_relative_path")
            indexes_relative = resolve_repo_path(value(row, "index_relative_path"))[1] or value(row, "index_relative_path")
            verification_evidence = validate_verification_artifact(
                verification,
                model_id,
                weights_relative,
                value(row, "weights_sha256"),
                indexes_relative,
                value(row, "index_sha256"),
                issues,
            )
        else:
            issues.append("ready gate 缺少 verification_artifact")
    if issues:
        result_status = "BLOCKED"
    elif metadata_waiting or status != "ready":
        result_status = "WAITING"
    else:
        result_status = "PASS"
    row_result.update({"result": result_status, "verification_artifact": verification, "verification_evidence": verification_evidence})
    return row_result


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit RVC model register and provenance metadata")
    parser.add_argument("--register", type=Path, default=ROOT / "models" / "model-register.csv")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "rvc-model-audit" / "rvc-model-audit.json")
    parser.add_argument("--fail-on-waiting", action="store_true")
    args = parser.parse_args()
    register = args.register if args.register.is_absolute() else ROOT / args.register
    output = args.output if args.output.is_absolute() else ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, str]] = []
    errors: list[str] = []
    if not register.is_file():
        errors.append(f"register 不存在：{register}")
    else:
        with register.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
    seen_ids: set[str] = set()
    registered_weights: set[str] = set()
    registered_indexes: set[str] = set()
    audited = [audit_row(row, seen_ids, registered_weights, registered_indexes) for row in rows]
    all_weights = {p.relative_to(ROOT).as_posix() for p in (ROOT / "models" / "weights").glob("*.pth")}
    all_indexes = {p.relative_to(ROOT).as_posix() for p in (ROOT / "models" / "indexes").glob("*.index")}
    unregistered_weights = sorted(all_weights - registered_weights)
    unregistered_indexes = sorted(all_indexes - registered_indexes)
    if unregistered_weights:
        errors.append("未登記 weights：" + ", ".join(unregistered_weights))
    if unregistered_indexes:
        errors.append("未登記 indexes：" + ", ".join(unregistered_indexes))
    if errors:
        overall = "BLOCKED"
    elif any(item["result"] == "BLOCKED" for item in audited):
        overall = "BLOCKED"
    elif any(item["result"] == "WAITING" for item in audited):
        overall = "WAITING"
    elif audited:
        overall = "PASS"
    else:
        overall = "BLOCKED"
    report = {
        "status": overall,
        "register": str(register),
        "required_fields": REQUIRED_FIELDS,
        "rows": audited,
        "unregistered_weights": unregistered_weights,
        "unregistered_indexes": unregistered_indexes,
        "errors": errors,
    }
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": overall, "rows": len(audited), "output": str(output), "errors": errors, "row_results": audited}, ensure_ascii=False, indent=2))
    if overall == "BLOCKED" or (args.fail_on_waiting and overall == "WAITING"):
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
