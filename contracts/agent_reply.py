"""Agent Reply extension contract；PLANNED，沒有 API 或自動回覆實作。"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Protocol

AGENT_REPLY_ENABLED = False
AGENT_REPLY_STATUS = "PLANNED"


@dataclass(frozen=True)
class AgentResponseTiming:
    remote_speech_end: str | None = None
    stt_complete: str | None = None
    agent_request_start: str | None = None
    agent_first_token: str | None = None
    agent_complete: str | None = None
    tts_first_audio: str | None = None


@dataclass(frozen=True)
class AgentReply:
    text: str
    emotion: str | None = None
    actions: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class AgentReplyProvider(Protocol):
    # 未來 Provider 只回傳文字／metadata；不得取得 TTS engine 或 playback handle。
    def generate_reply(self, context: dict[str, Any]) -> AgentReply: ...
