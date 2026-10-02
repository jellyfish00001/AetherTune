"""TTS 公開快照的純資料投影；不讀 DB、不啟動 adapter，也不擁有可變狀態。"""

from __future__ import annotations

import copy
from typing import Any, Iterable, Mapping


def project_request(record: Mapping[str, Any]) -> dict[str, Any]:
    # 每個公開欄位分別深拷貝，保留既有欄位之間的隔離；private runtime 資料不外傳。
    # profile／route 是 request identity 的一部分，不能為縮小 payload 而省略。
    return {key: copy.deepcopy(value) for key, value in record.items() if not key.startswith("_")}


def project_profile(profile: Mapping[str, Any]) -> dict[str, Any]:
    output = copy.deepcopy(dict(profile))
    output.pop("profile_path", None)
    return output


def project_queue(
    requests: Mapping[str, Mapping[str, Any]],
    current_id: str | None,
    pending: Iterable[str],
) -> list[dict[str, Any]]:
    """呼叫端持有 service lock；current、pending、歷史順序及資料完整性都不改。"""
    ordered_ids = [] if current_id is None else [current_id]
    ordered_ids.extend(request_id for request_id in pending if request_id != current_id)
    # requests 的 key 唯一，active set 避免長歷史的 O(n²) list membership。
    active_ids = set(ordered_ids)
    ordered_ids.extend(request_id for request_id in requests if request_id not in active_ids)
    return [project_request(requests[request_id]) for request_id in ordered_ids]
