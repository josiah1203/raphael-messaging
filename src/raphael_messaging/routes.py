"""API routes for raphael-messaging."""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["raphael-messaging"])
_db = Path(os.environ.get("RAPHAEL_MESSAGING_DB", "/tmp/raphael-messaging.db"))
_conn = sqlite3.connect(_db, check_same_thread=False)
_conn.execute(
    """CREATE TABLE IF NOT EXISTS items (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        body TEXT,
        created_at TEXT NOT NULL
    )"""
)
_conn.commit()
_items: list[dict[str, Any]] = []


@router.get("")
def list_items() -> dict[str, Any]:
    rows = _conn.execute("SELECT id, name, body, created_at FROM items ORDER BY created_at DESC").fetchall()
    return {"service": "raphael-messaging", "items": [{"id": r[0], "name": r[1], "body": r[2], "created_at": r[3]} for r in rows]}


@router.post("")
def create_item(body: dict[str, Any]) -> dict[str, Any]:
    iid = body.get("id", f"item-{int(datetime.now(timezone.utc).timestamp())}")
    now = datetime.now(timezone.utc).isoformat()
    _conn.execute("INSERT INTO items (id, name, body, created_at) VALUES (?, ?, ?, ?)", (iid, body.get("name", iid), body.get("body", ""), now))
    _conn.commit()
    return {"id": iid, "name": body.get("name", iid), "created_at": now}


@router.get("/{item_id}")
def get_item(item_id: str) -> dict[str, Any]:
    row = _conn.execute("SELECT id, name, body, created_at FROM items WHERE id = ?", (item_id,)).fetchone()
    if not row:
        raise HTTPException(404, detail="not_found")
    return {"id": row[0], "name": row[1], "body": row[2], "created_at": row[3]}
