"""Conversations metadata store — local SQLite/Postgres + optional Twilio SID mapping."""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ConversationsStore:
    def __init__(self, db_path: Path | None = None) -> None:
        from raphael_contracts import db as rdb

        self._postgres = rdb.is_postgres()
        if self._postgres:
            rdb.ensure_migrations()
        else:
            self._db = db_path or Path(os.environ.get("RAPHAEL_MESSAGING_DB", "/tmp/raphael-messaging.db"))
            self._db.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(self._db, check_same_thread=False)
            self._init_sqlite()

    def _init_sqlite(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                name TEXT,
                target_type TEXT,
                target_id TEXT,
                twilio_conversation_sid TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                author TEXT,
                body TEXT NOT NULL,
                twilio_message_sid TEXT,
                created_at TEXT NOT NULL,
                data TEXT
            );
            """
        )
        cols = {row[1] for row in self._conn.execute("PRAGMA table_info(conversations)").fetchall()}
        if "name" not in cols:
            self._conn.execute("ALTER TABLE conversations ADD COLUMN name TEXT")
        self._conn.commit()

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def list_conversations(self, workspace_id: str | None = None) -> list[dict[str, Any]]:
        if self._postgres:
            from raphael_contracts import db as rdb

            if workspace_id:
                rows = rdb.pg_fetchall(
                    "SELECT c.id, c.workspace_id, c.name, c.target_type, c.target_id, c.twilio_conversation_sid, c.created_at, "
                    "(SELECT m.body FROM messaging_messages m WHERE m.conversation_id = c.id ORDER BY m.created_at DESC LIMIT 1) AS last_message "
                    "FROM messaging_conversations c WHERE c.workspace_id = %s ORDER BY c.created_at DESC",
                    (workspace_id,),
                )
            else:
                rows = rdb.pg_fetchall(
                    "SELECT c.id, c.workspace_id, c.name, c.target_type, c.target_id, c.twilio_conversation_sid, c.created_at, "
                    "(SELECT m.body FROM messaging_messages m WHERE m.conversation_id = c.id ORDER BY m.created_at DESC LIMIT 1) AS last_message "
                    "FROM messaging_conversations c ORDER BY c.created_at DESC",
                )
        else:
            if workspace_id:
                rows = self._conn.execute(
                    "SELECT c.id, c.workspace_id, c.name, c.target_type, c.target_id, c.twilio_conversation_sid, c.created_at, "
                    "(SELECT m.body FROM messages m WHERE m.conversation_id = c.id ORDER BY m.created_at DESC LIMIT 1) AS last_message "
                    "FROM conversations c WHERE c.workspace_id = ? ORDER BY c.created_at DESC",
                    (workspace_id,),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT c.id, c.workspace_id, c.name, c.target_type, c.target_id, c.twilio_conversation_sid, c.created_at, "
                    "(SELECT m.body FROM messages m WHERE m.conversation_id = c.id ORDER BY m.created_at DESC LIMIT 1) AS last_message "
                    "FROM conversations c ORDER BY c.created_at DESC",
                ).fetchall()
        return [self._conv_row(r) for r in rows]

    def get_conversation(self, conversation_id: str) -> dict[str, Any] | None:
        if self._postgres:
            from raphael_contracts import db as rdb

            row = rdb.pg_fetchone(
                "SELECT id, workspace_id, name, target_type, target_id, twilio_conversation_sid, created_at "
                "FROM messaging_conversations WHERE id = %s",
                (conversation_id,),
            )
        else:
            row = self._conn.execute(
                "SELECT id, workspace_id, name, target_type, target_id, twilio_conversation_sid, created_at "
                "FROM conversations WHERE id = ?",
                (conversation_id,),
            ).fetchone()
        return self._conv_row(row) if row else None

    def find_by_target(
        self,
        workspace_id: str,
        target_type: str,
        target_id: str,
    ) -> dict[str, Any] | None:
        if self._postgres:
            from raphael_contracts import db as rdb

            row = rdb.pg_fetchone(
                "SELECT id, workspace_id, name, target_type, target_id, twilio_conversation_sid, created_at "
                "FROM messaging_conversations WHERE workspace_id = %s AND target_type = %s AND target_id = %s",
                (workspace_id, target_type, target_id),
            )
        else:
            row = self._conn.execute(
                "SELECT id, workspace_id, name, target_type, target_id, twilio_conversation_sid, created_at "
                "FROM conversations WHERE workspace_id = ? AND target_type = ? AND target_id = ?",
                (workspace_id, target_type, target_id),
            ).fetchone()
        return self._conv_row(row) if row else None

    def create_conversation(
        self,
        workspace_id: str,
        target_type: str | None = None,
        target_id: str | None = None,
        twilio_conversation_sid: str | None = None,
        name: str | None = None,
    ) -> dict[str, Any]:
        existing = None
        if target_type and target_id:
            existing = self.find_by_target(workspace_id, target_type, target_id)
        if existing:
            return existing

        cid = f"conv_{uuid.uuid4().hex[:10]}"
        now = self._now()
        friendly = name or (f"{target_type}/{target_id}" if target_type and target_id else workspace_id)

        if self._postgres:
            from raphael_contracts import db as rdb

            rdb.pg_execute(
                "INSERT INTO messaging_conversations "
                "(id, workspace_id, name, target_type, target_id, twilio_conversation_sid, created_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (cid, workspace_id, friendly, target_type, target_id, twilio_conversation_sid, now),
            )
        else:
            self._conn.execute(
                "INSERT INTO conversations (id, workspace_id, name, target_type, target_id, twilio_conversation_sid, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (cid, workspace_id, friendly, target_type, target_id, twilio_conversation_sid, now),
            )
            self._conn.commit()

        return {
            "id": cid,
            "workspace_id": workspace_id,
            "name": friendly,
            "target_type": target_type,
            "target_id": target_id,
            "twilio_conversation_sid": twilio_conversation_sid,
            "created_at": now,
        }

    def set_twilio_sid(self, conversation_id: str, twilio_sid: str) -> None:
        if self._postgres:
            from raphael_contracts import db as rdb

            rdb.pg_execute(
                "UPDATE messaging_conversations SET twilio_conversation_sid = %s WHERE id = %s",
                (twilio_sid, conversation_id),
            )
        else:
            self._conn.execute(
                "UPDATE conversations SET twilio_conversation_sid = ? WHERE id = ?",
                (twilio_sid, conversation_id),
            )
            self._conn.commit()

    def list_messages(self, conversation_id: str) -> list[dict[str, Any]]:
        if self._postgres:
            from raphael_contracts import db as rdb

            rows = rdb.pg_fetchall(
                "SELECT id, conversation_id, author, body, twilio_message_sid, created_at, data "
                "FROM messaging_messages WHERE conversation_id = %s ORDER BY created_at ASC",
                (conversation_id,),
            )
        else:
            rows = self._conn.execute(
                "SELECT id, conversation_id, author, body, twilio_message_sid, created_at, data "
                "FROM messages WHERE conversation_id = ? ORDER BY created_at ASC",
                (conversation_id,),
            ).fetchall()
        return [self._msg_row(r) for r in rows]

    def add_message(
        self,
        conversation_id: str,
        body: str,
        author: str | None = None,
        twilio_message_sid: str | None = None,
        data: dict | None = None,
    ) -> dict[str, Any]:
        mid = f"msg_{uuid.uuid4().hex[:10]}"
        now = self._now()
        data_json = json.dumps(data or {})

        if self._postgres:
            from raphael_contracts import db as rdb

            rdb.pg_execute(
                "INSERT INTO messaging_messages (id, conversation_id, author, body, twilio_message_sid, created_at, data) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)",
                (mid, conversation_id, author, body, twilio_message_sid, now, data_json),
            )
        else:
            self._conn.execute(
                "INSERT INTO messages (id, conversation_id, author, body, twilio_message_sid, created_at, data) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (mid, conversation_id, author, body, twilio_message_sid, now, data_json),
            )
            self._conn.commit()

        return {
            "id": mid,
            "conversation_id": conversation_id,
            "author": author,
            "body": body,
            "twilio_message_sid": twilio_message_sid,
            "created_at": now,
        }

    def find_by_twilio_sid(self, twilio_sid: str) -> dict[str, Any] | None:
        if self._postgres:
            from raphael_contracts import db as rdb

            row = rdb.pg_fetchone(
                "SELECT id, workspace_id, name, target_type, target_id, twilio_conversation_sid, created_at "
                "FROM messaging_conversations WHERE twilio_conversation_sid = %s",
                (twilio_sid,),
            )
        else:
            row = self._conn.execute(
                "SELECT id, workspace_id, name, target_type, target_id, twilio_conversation_sid, created_at "
                "FROM conversations WHERE twilio_conversation_sid = ?",
                (twilio_sid,),
            ).fetchone()
        return self._conv_row(row) if row else None

    @staticmethod
    def _conv_row(row: Any) -> dict[str, Any]:
        if isinstance(row, dict):
            return {
                "id": row["id"],
                "workspace_id": row["workspace_id"],
                "name": row.get("name"),
                "target_type": row.get("target_type"),
                "target_id": row.get("target_id"),
                "twilio_conversation_sid": row.get("twilio_conversation_sid"),
                "created_at": str(row.get("created_at") or ""),
                "last_message": row.get("last_message"),
            }
        last_message = row[7] if len(row) > 7 else None
        return {
            "id": row[0],
            "workspace_id": row[1],
            "name": row[2],
            "target_type": row[3],
            "target_id": row[4],
            "twilio_conversation_sid": row[5],
            "created_at": row[6],
            "last_message": last_message,
        }

    @staticmethod
    def _msg_row(row: Any) -> dict[str, Any]:
        if isinstance(row, dict):
            data = row.get("data")
            if isinstance(data, str):
                data = json.loads(data or "{}")
            return {
                "id": row["id"],
                "conversation_id": row["conversation_id"],
                "author": row.get("author"),
                "body": row["body"],
                "twilio_message_sid": row.get("twilio_message_sid"),
                "created_at": str(row.get("created_at") or ""),
                "data": data or {},
            }
        return {
            "id": row[0],
            "conversation_id": row[1],
            "author": row[2],
            "body": row[3],
            "twilio_message_sid": row[4],
            "created_at": row[5],
            "data": json.loads(row[6] or "{}"),
        }
