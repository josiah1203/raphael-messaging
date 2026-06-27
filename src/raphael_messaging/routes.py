"""API routes for raphael-messaging — Twilio Conversations with local fallback."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request

from raphael_messaging.events import handle_bus_event
from raphael_messaging.store import ConversationsStore
from raphael_messaging.twilio_conversations import TwilioConversationsClient

router = APIRouter(tags=["raphael-messaging"])
_store = ConversationsStore()
_twilio = TwilioConversationsClient()


@router.get("")
def list_conversations(workspace_id: str | None = None) -> dict[str, Any]:
    return {
        "service": "raphael-messaging",
        "twilio_configured": _twilio.enabled,
        "conversations": _store.list_conversations(workspace_id),
    }


@router.post("")
def create_conversation(body: dict[str, Any]) -> dict[str, Any]:
    workspace_id = body.get("workspace_id", "default")
    target_type = body.get("target_type")
    target_id = body.get("target_id")
    friendly_name = body.get("name") or f"{target_type}/{target_id}"

    twilio_sid = None
    if _twilio.enabled:
        result = _twilio.create_conversation(friendly_name)
        if result.get("status") == "created":
            twilio_sid = result["sid"]

    return _store.create_conversation(
        workspace_id,
        target_type,
        target_id,
        twilio_sid,
        name=friendly_name,
    )


@router.post("/events")
def consume_event(body: dict[str, Any]) -> dict[str, str]:
    """HTTP hook for dev without Kafka."""
    handle_bus_event(body)
    return {"status": "processed"}


@router.post("/webhooks/twilio")
async def twilio_webhook(request: Request) -> dict[str, str]:
    """Inbound Twilio Conversations webhook — stores message in local DB."""
    form = await request.form()
    conversation_sid = str(form.get("ConversationSid", ""))
    body = str(form.get("Body", ""))
    author = str(form.get("Author", "unknown"))
    message_sid = str(form.get("MessageSid", ""))

    if not conversation_sid or not body:
        return {"status": "ignored"}

    conversation = _store.find_by_twilio_sid(conversation_sid)
    if conversation:
        _store.add_message(
            conversation["id"],
            body,
            author=author,
            twilio_message_sid=message_sid or None,
            data={"source": "twilio_webhook"},
        )
    return {"status": "processed"}


@router.get("/{conversation_id}/messages")
def list_messages(conversation_id: str) -> dict[str, Any]:
    conversation = _store.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(404, detail="not_found")
    messages = _store.list_messages(conversation_id)
    if _twilio.enabled and conversation.get("twilio_conversation_sid") and not messages:
        remote = _twilio.list_messages(conversation["twilio_conversation_sid"])
        return {"conversation_id": conversation_id, "messages": messages, "twilio_messages": remote}
    return {"conversation_id": conversation_id, "messages": messages}


@router.post("/{conversation_id}/messages")
def send_message(conversation_id: str, body: dict[str, Any]) -> dict[str, Any]:
    conversation = _store.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(404, detail="not_found")
    text = (body.get("body") or "").strip()
    if not text:
        raise HTTPException(400, detail="body_required")
    author = body.get("author", "user")

    twilio_sid = None
    if _twilio.enabled and conversation.get("twilio_conversation_sid"):
        result = _twilio.send_message(conversation["twilio_conversation_sid"], text, author=author)
        if result.get("status") == "sent":
            twilio_sid = result["sid"]

    return _store.add_message(conversation_id, text, author=author, twilio_message_sid=twilio_sid)
