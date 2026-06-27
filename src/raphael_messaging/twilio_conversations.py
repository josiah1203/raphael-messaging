"""Twilio Conversations adapter — optional; dev mode uses local store only."""

from __future__ import annotations

import os
from typing import Any


class TwilioConversationsClient:
    def __init__(
        self,
        account_sid: str | None = None,
        auth_token: str | None = None,
        service_sid: str | None = None,
    ) -> None:
        self.account_sid = account_sid or os.environ.get("TWILIO_ACCOUNT_SID", "")
        self.auth_token = auth_token or os.environ.get("TWILIO_AUTH_TOKEN", "")
        self.service_sid = service_sid or os.environ.get("TWILIO_CONVERSATIONS_SERVICE_SID", "")

    @property
    def enabled(self) -> bool:
        return bool(self.account_sid and self.auth_token and self.service_sid)

    def _client(self) -> Any:
        from twilio.rest import Client

        return Client(self.account_sid, self.auth_token)

    def create_conversation(self, friendly_name: str) -> dict[str, Any]:
        if not self.enabled:
            return {"status": "skipped", "reason": "no_twilio_config"}
        conversation = (
            self._client()
            .conversations.v1.services(self.service_sid)
            .conversations.create(friendly_name=friendly_name)
        )
        return {"status": "created", "sid": conversation.sid}

    def send_message(self, conversation_sid: str, body: str, author: str = "system") -> dict[str, Any]:
        if not self.enabled:
            return {"status": "skipped", "reason": "no_twilio_config"}
        message = (
            self._client()
            .conversations.v1.services(self.service_sid)
            .conversations(conversation_sid)
            .messages.create(body=body, author=author)
        )
        return {"status": "sent", "sid": message.sid}

    def list_messages(self, conversation_sid: str) -> list[dict[str, Any]]:
        if not self.enabled:
            return []
        messages = (
            self._client()
            .conversations.v1.services(self.service_sid)
            .conversations(conversation_sid)
            .messages.list(limit=50)
        )
        return [
            {
                "sid": m.sid,
                "body": m.body,
                "author": m.author,
                "date_created": str(m.date_created) if m.date_created else None,
            }
            for m in messages
        ]
