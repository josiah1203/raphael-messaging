"""Kafka event handlers for messaging."""

from __future__ import annotations

from typing import Any

from raphael_messaging.store import ConversationsStore

_store = ConversationsStore()


def handle_bus_event(envelope: dict[str, Any]) -> None:
    event_type = envelope.get("type", "")
    data = envelope.get("data") or {}
    if event_type != "raphael.reviews.created":
        return
    review_id = data.get("id")
    if not review_id:
        return
    workspace_id = data.get("workspace_id", "default")
    if _store.find_by_target(workspace_id, "review", review_id):
        return
    title = data.get("title") or review_id
    _store.create_conversation(
        workspace_id,
        target_type="review",
        target_id=review_id,
        name=f"Review: {title}",
    )
