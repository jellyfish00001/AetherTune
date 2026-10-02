"""TTS request 的資料驗證；不讀 service 狀態、DB 或裝置。"""

from __future__ import annotations

import copy
from typing import Any, Callable, Mapping, NamedTuple

INTERRUPT_POLICIES = {"queue", "interrupt_current", "reject_new"}
ALLOWED_ENGINES = {"cosyvoice", "breeze"}
ALLOWED_SOURCES = {"manual", "stt", "system", "agent"}


class ValidatedRequest(NamedTuple):
    text: str
    engine_id: str
    profile_id: str
    source: str
    metadata: dict[str, Any]
    priority: int
    profile: dict[str, Any]
    route: dict[str, Any]
    policy: str
    enqueue: bool


def validate_request(
    command: Mapping[str, Any],
    *,
    profiles: Mapping[str, dict[str, Any]],
    default_policy: str,
    validate_postfx: Callable[[Any], dict[str, Any]],
    resolve_route: Callable[[Any], dict[str, Any]],
) -> ValidatedRequest:
    """保留既有錯誤順序與訊息；純資料 validators 由協調器注入。"""
    request = command.get("request")
    if not isinstance(request, Mapping):
        raise ValueError("REQUEST_INVALID: request 必須是 object")
    text = request.get("text")
    engine_id = request.get("engine_id")
    profile_id = request.get("voice_profile_id")
    source = request.get("source")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("REQUEST_INVALID: text 不可為空")
    if len(text) > 20_000:
        raise ValueError("REQUEST_INVALID: text 超過 20000 字元")
    if engine_id not in ALLOWED_ENGINES:
        raise ValueError("BACKEND_UNAVAILABLE: 只允許 cosyvoice 或 breeze；CosyVoice3/Agent 維持 PLANNED")
    if source not in ALLOWED_SOURCES:
        raise ValueError("REQUEST_INVALID: source 必須是 manual、stt、system 或 agent")
    if source == "agent":
        raise ValueError("AGENT_NOT_ALLOWED: agent reply 尚未開放")
    metadata = request.get("metadata", {})
    if not isinstance(metadata, Mapping):
        raise ValueError("REQUEST_INVALID: metadata 必須是 object")
    metadata = copy.deepcopy(dict(metadata))
    # 已接受 request 的音效不受呼叫者後續修改影響，也不在此啟動 DSP 或播放。
    metadata["postfx"] = validate_postfx(metadata.get("postfx"))
    priority = request.get("priority", 0)
    if isinstance(priority, bool) or not isinstance(priority, int):
        raise ValueError("REQUEST_INVALID: priority 必須是整數")
    if source == "stt":
        capture = metadata.get("capture_source")
        if capture != "physical_microphone":
            raise ValueError("CAPTURE_SOURCE_INVALID: stt 僅接受 physical_microphone")
    if not isinstance(profile_id, str) or profile_id not in profiles:
        raise ValueError("REFERENCE_INVALID: voice_profile_id 不存在")
    profile = copy.deepcopy(profiles[profile_id])
    engines = profile.get("engines", [])
    if engine_id not in engines:
        raise ValueError(f"REFERENCE_INVALID: profile 不支援 engine={engine_id}")
    route = resolve_route(metadata.get("route"))
    metadata["route"] = route
    policy = request.get("interrupt_policy", default_policy)
    if policy not in INTERRUPT_POLICIES:
        raise ValueError("REQUEST_INVALID: interrupt_policy 不合法")
    enqueue = command.get("enqueue", True)
    if not isinstance(enqueue, bool):
        raise ValueError("REQUEST_INVALID: enqueue 必須是 boolean")
    return ValidatedRequest(text, engine_id, profile_id, source, metadata, priority,
                            profile, route, policy, enqueue)
