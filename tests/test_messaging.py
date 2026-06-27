"""Messaging tests."""

import uuid

from fastapi.testclient import TestClient

from raphael_messaging.app import app


def test_health() -> None:
    client = TestClient(app)
    assert client.get("/health").json()["service"] == "raphael-messaging"


def test_conversation_local_mode() -> None:
    client = TestClient(app)
    review_id = f"rev_{uuid.uuid4().hex[:8]}"
    created = client.post(
        "/v1/messaging",
        json={
            "workspace_id": "default",
            "target_type": "review",
            "target_id": review_id,
            "name": "Review thread",
        },
    )
    assert created.status_code == 200
    conv = created.json()
    assert conv["workspace_id"] == "default"
    assert conv["name"] == "Review thread"
    assert conv["twilio_conversation_sid"] is None

    msg = client.post(f"/v1/messaging/{conv['id']}/messages", json={"body": "Hello"})
    assert msg.status_code == 200
    listed = client.get(f"/v1/messaging/{conv['id']}/messages")
    assert listed.status_code == 200
    assert len(listed.json()["messages"]) == 1

    inbox = client.get("/v1/messaging").json()["conversations"]
    assert any(c["id"] == conv["id"] and c.get("last_message") == "Hello" for c in inbox)


def test_review_event_creates_conversation() -> None:
    client = TestClient(app)
    review_id = f"rev-auto-{uuid.uuid4().hex[:8]}"
    res = client.post(
        "/v1/messaging/events",
        json={
            "type": "raphael.reviews.created",
            "data": {"id": review_id, "title": "Auto thread", "workspace_id": "default"},
        },
    )
    assert res.status_code == 200
    listed = client.get("/v1/messaging").json()["conversations"]
    assert any(c["target_type"] == "review" and c["target_id"] == review_id for c in listed)


def test_list_messages_not_found() -> None:
    client = TestClient(app)
    res = client.get("/v1/messaging/conv-does-not-exist/messages")
    assert res.status_code == 404


def test_send_message_requires_body() -> None:
    client = TestClient(app)
    review_id = f"rev_{uuid.uuid4().hex[:8]}"
    conv = client.post(
        "/v1/messaging",
        json={"workspace_id": "default", "target_type": "review", "target_id": review_id},
    ).json()
    res = client.post(f"/v1/messaging/{conv['id']}/messages", json={"body": "  "})
    assert res.status_code == 400


def test_list_empty_workspace() -> None:
    client = TestClient(app)
    workspace_id = f"ws-empty-{uuid.uuid4().hex[:8]}"
    listed = client.get(f"/v1/messaging?workspace_id={workspace_id}").json()["conversations"]
    assert listed == []
