"""Schema-table integrity tests for the 12 events methods."""

from chaturbate_mcp.events_schema import EVENT_OBJECT_SHAPES, events_schema_markdown

EXPECTED_METHODS = {
    "broadcastStart",
    "broadcastStop",
    "chatMessage",
    "fanclubJoin",
    "follow",
    "mediaPurchase",
    "privateMessage",
    "roomSubjectChange",
    "tip",
    "unfollow",
    "userEnter",
    "userLeave",
}


def test_exactly_twelve_methods():
    assert set(EVENT_OBJECT_SHAPES) == EXPECTED_METHODS
    assert len(EVENT_OBJECT_SHAPES) == 12


def test_markdown_has_one_row_per_method():
    md = events_schema_markdown()
    assert md.count("| `") == 12
    assert "| method |" in md
    assert "object" in md


def test_tip_row_carries_expected_subshapes():
    row = EVENT_OBJECT_SHAPES["tip"]
    assert "broadcaster" in row and "tip:" in row and "isAnon" in row and "tokens" in row
    assert "user:" in row and "recentTips" in row


def test_private_message_carries_from_to_user_note():
    row = EVENT_OBJECT_SHAPES["privateMessage"]
    assert "fromUser" in row and "toUser" in row
    assert "message:" in row


def test_media_purchase_carries_media_shape():
    row = EVENT_OBJECT_SHAPES["mediaPurchase"]
    assert "media:" in row and "photos" in row and "video" in row and "tokens" in row


def test_room_subject_change_carries_subject():
    row = EVENT_OBJECT_SHAPES["roomSubjectChange"]
    assert "subject" in row


def test_markdown_mentions_public_scope_privacy_note():
    assert "public" in events_schema_markdown().lower()
