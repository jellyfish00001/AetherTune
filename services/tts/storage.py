"""TTS session SQLite canonical storage 與即時 exports。"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


class TranscriptStore:
    """每次完成播放立即 commit；exports 可由 DB 重建。"""

    def __init__(self, root: Path, session_id: str, *, started_at: str | None = None) -> None:
        self.root = root.resolve()
        self.session_id = session_id
        self.started_at = started_at or utc_now()
        self.base_dir = self.root / "artifacts" / "tts"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.base_dir / "tts.sqlite3"
        self.session_dir = self.root / "artifacts" / "sessions" / session_id
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._db = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._create_schema()
        with self._lock:
            self._db.execute(
                "INSERT OR IGNORE INTO sessions(session_id, started_at, mode) VALUES(?, ?, ?)",
                (session_id, self.started_at, "text_to_speech"),
            )
            self._db.commit()
        self.export_session()

    def _create_schema(self) -> None:
        with self._lock:
            self._db.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS sessions(
                    session_id TEXT PRIMARY KEY,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    mode TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS transcripts(
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    request_id TEXT NOT NULL UNIQUE,
                    source_id TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    source TEXT NOT NULL,
                    speaker_id TEXT,
                    device_id TEXT,
                    started_at TEXT NOT NULL,
                    ended_at TEXT NOT NULL,
                    language TEXT NOT NULL,
                    text TEXT NOT NULL,
                    confidence REAL,
                    provider TEXT NOT NULL,
                    transcript_provider TEXT NOT NULL,
                    speech_status TEXT NOT NULL,
                    engine_id TEXT NOT NULL,
                    voice_profile_id TEXT NOT NULL,
                    metrics_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS speech_requests(
                    request_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS recent_phrases(
                    text TEXT PRIMARY KEY,
                    last_used_at TEXT NOT NULL,
                    use_count INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS favorites(
                    text TEXT PRIMARY KEY,
                    pinned INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS tts_settings(
                    key TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
            self._db.commit()

    def save_request(self, request: Mapping[str, Any]) -> None:
        """保存每個 queue status；取消項目可追溯但不會進 transcripts。"""

        request_id = str(request["id"])
        payload = {key: value for key, value in request.items() if not str(key).startswith("_")}
        now = utc_now()
        with self._lock:
            self._db.execute(
                """
                INSERT INTO speech_requests(request_id,session_id,created_at,updated_at,status,payload_json)
                VALUES(?,?,?,?,?,?)
                ON CONFLICT(request_id) DO UPDATE SET updated_at=excluded.updated_at,
                    status=excluded.status, payload_json=excluded.payload_json
                """,
                (
                    request_id,
                    str(request.get("session_id", self.session_id)),
                    str(request.get("created_at", now)),
                    now,
                    str(request.get("status", "queued")),
                    _json(payload),
                ),
            )
            self._db.commit()

    def list_requests(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._db.execute(
                "SELECT payload_json FROM speech_requests WHERE session_id=? ORDER BY created_at, request_id",
                (self.session_id,),
            ).fetchall()
        return [json.loads(row["payload_json"]) for row in rows]

    def record_completed(
        self,
        request: Mapping[str, Any],
        *,
        started_at: str,
        ended_at: str,
        metrics: Mapping[str, Any],
        route: Mapping[str, Any],
    ) -> dict[str, Any]:
        """實際播放成功後才建立 manual_text transcript。"""

        source = str(request.get("source", "manual"))
        if source == "stt":
            provider = "backend_stt"
            transcript_provider = "backend_stt"
        elif source == "system":
            provider = "system"
            transcript_provider = "system"
        else:
            provider = "manual_text"
            transcript_provider = "manual_text"
            source = "manual"
        event = {
            "id": str(uuid.uuid4()),
            "session_id": self.session_id,
            "request_id": str(request["id"]),
            "source_id": str(request["id"]),
            # Product contract 的 self 是「本機自己說出來的 utterance」；
            # source 欄位另外保留 manual，方便區分 typed text 與 STT。
            "source_type": "self",
            "source": source,
            "speaker_id": None,
            "device_id": route.get("output"),
            "started_at": started_at,
            "ended_at": ended_at,
            "language": str(request.get("metadata", {}).get("language", "auto"))
            if isinstance(request.get("metadata"), dict)
            else "auto",
            "text": str(request["text"]),
            "confidence": None,
            "provider": provider,
            "transcript_provider": transcript_provider,
            "speech_status": "completed",
            "engine_id": str(request["engine_id"]),
            "voice_profile_id": str(request["voice_profile_id"]),
            "metrics": dict(metrics),
        }
        with self._lock:
            self._db.execute(
                """
                INSERT INTO transcripts(
                    id, session_id, request_id, source_id, source_type, source,
                    speaker_id, device_id, started_at, ended_at, language, text,
                    confidence, provider, transcript_provider, speech_status,
                    engine_id, voice_profile_id, metrics_json
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    event["id"],
                    event["session_id"],
                    event["request_id"],
                    event["source_id"],
                    event["source_type"],
                    event["source"],
                    event["speaker_id"],
                    event["device_id"],
                    event["started_at"],
                    event["ended_at"],
                    event["language"],
                    event["text"],
                    event["confidence"],
                    event["provider"],
                    event["transcript_provider"],
                    event["speech_status"],
                    event["engine_id"],
                    event["voice_profile_id"],
                    _json(event["metrics"]),
                ),
            )
            now = ended_at
            self._db.execute(
                """
                INSERT INTO recent_phrases(text,last_used_at,use_count)
                VALUES(?,?,1)
                ON CONFLICT(text) DO UPDATE SET last_used_at=excluded.last_used_at,
                    use_count=recent_phrases.use_count+1
                """,
                (event["text"], now),
            )
            # 這個 commit 是 acceptance gate：未 commit 的 utterance 不得出現在
            # transcript export，也不應被 snapshot 宣稱為 spoken transcript。
            self._db.commit()
        try:
            self.export_session()
        except OSError as exc:
            self._write_export_error(exc)
        return event

    def list_transcripts(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM transcripts WHERE session_id=? ORDER BY ended_at, id",
                (self.session_id,),
            ).fetchall()
        output = []
        for row in rows:
            item = dict(row)
            item["metrics"] = json.loads(item.pop("metrics_json"))
            output.append(item)
        return output

    def recent_phrases(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._db.execute(
                "SELECT text,last_used_at,use_count FROM recent_phrases ORDER BY last_used_at DESC LIMIT ?",
                (max(1, int(limit)),),
            ).fetchall()
        return [dict(row) for row in rows]

    def set_favorite(self, text: str, pinned: bool = True) -> dict[str, Any]:
        phrase = text.strip()
        if not phrase:
            raise ValueError("favorite text 不可為空")
        now = utc_now()
        with self._lock:
            if pinned:
                self._db.execute(
                    """
                    INSERT INTO favorites(text,pinned,created_at,updated_at) VALUES(?,?,?,?)
                    ON CONFLICT(text) DO UPDATE SET pinned=1, updated_at=excluded.updated_at
                    """,
                    (phrase, 1, now, now),
                )
            else:
                self._db.execute("DELETE FROM favorites WHERE text=?", (phrase,))
            self._db.commit()
        return {"text": phrase, "pinned": bool(pinned), "updated_at": now}

    def load_settings(self) -> dict[str, Any]:
        with self._lock:
            rows = self._db.execute("SELECT key,value_json FROM tts_settings").fetchall()
        output: dict[str, Any] = {}
        for row in rows:
            try:
                output[str(row["key"])] = json.loads(row["value_json"])
            except json.JSONDecodeError:
                continue
        return output

    def save_settings(self, settings: Mapping[str, Any]) -> None:
        now = utc_now()
        with self._lock:
            for key, value in settings.items():
                self._db.execute(
                    """
                    INSERT INTO tts_settings(key,value_json,updated_at) VALUES(?,?,?)
                    ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json,
                        updated_at=excluded.updated_at
                    """,
                    (str(key), _json(value), now),
                )
            self._db.commit()

    def favorites(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._db.execute(
                "SELECT text,pinned,created_at,updated_at FROM favorites ORDER BY updated_at DESC"
            ).fetchall()
        return [{**dict(row), "pinned": bool(row["pinned"])} for row in rows]

    def export_session(self, *, ended_at: str | None = None) -> None:
        transcripts = self.list_transcripts()
        requests = self.list_requests()
        session = {
            "id": self.session_id,
            "started_at": self.started_at,
            "ended_at": ended_at,
            "mode": "text_to_speech",
            "engine_id": "tts",
            "model": None,
            "voice_profile_id": None,
            "reference": None,
            "parameters": {"request_history": "requests.jsonl"},
            "input_device_id": None,
            "output_device_id": None,
            "postfx_preset": None,
            "stt_settings": {"provider": "manual_text", "microphone": "WAITING"},
            "transcript_storage": "sqlite",
            "export_directory": str(self.session_dir),
        }
        (self.session_dir / "session.json").write_text(
            json.dumps(session, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        with (self.session_dir / "transcript.jsonl").open("w", encoding="utf-8", newline="\n") as stream:
            for event in transcripts:
                stream.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
        (self.session_dir / "transcript.txt").write_text(
            "\n".join(f"[{event['started_at']}] {event['text']}" for event in transcripts)
            + ("\n" if transcripts else ""),
            encoding="utf-8",
        )
        with (self.session_dir / "requests.jsonl").open("w", encoding="utf-8", newline="\n") as stream:
            for request in requests:
                stream.write(json.dumps(request, ensure_ascii=False, sort_keys=True) + "\n")

    def _write_export_error(self, exc: BaseException) -> None:
        try:
            (self.session_dir / "export_error.json").write_text(
                json.dumps({"at": utc_now(), "error": str(exc)}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            pass

    def close(self, *, ended_at: str | None = None) -> None:
        try:
            self.export_session(ended_at=ended_at or utc_now())
        except OSError as exc:
            self._write_export_error(exc)
        with self._lock:
            self._db.close()


__all__ = ["TranscriptStore", "utc_now"]
