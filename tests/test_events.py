"""Review event consumer tests."""

from raphael_messaging.events import handle_bus_event
from raphael_messaging.store import ConversationsStore


def test_review_created_spawns_conversation() -> None:
    store = ConversationsStore()
    handle_bus_event(
        {
            "type": "raphael.reviews.created",
            "data": {"id": "rev-auto-1", "title": "Fix board", "workspace_id": "default"},
        }
    )
    conv = store.find_by_target("default", "review", "rev-auto-1")
    assert conv is not None
    assert conv["target_type"] == "review"
    assert conv["name"] == "Review: Fix board"
