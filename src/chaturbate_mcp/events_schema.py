"""The 12 Chaturbate events-feed methods and their ``event["object"]`` shapes.

Shapes distilled from the official Events API documentation (methods/*.html and
objects.html). Used by the ``get_events_schema`` tool so an LLM can interpret raw
events, and asserted by tests to stay in sync.
"""

from __future__ import annotations

USER_OBJ = (
    "user: {username, inFanclub: bool, gender: 'm'|'f'|'t'|'c', hasTokens: bool, "
    "recentTips: 'none'|'some'|'lots'|'tons', isMod: bool}"
)
MSG_OBJ = (
    "message: {color, bgColor, message, font}"
    "  — privateMessage adds fromUser (sender) and toUser (recipient)"
)
MEDIA_OBJ = "media: {id, type: 'photos'|'video', name, tokens}"
TIP_OBJ = "tip: {tokens, isAnon, message}"

# method -> description of the event["object"] payload
EVENT_OBJECT_SHAPES: dict[str, str] = {
    "broadcastStart": f"broadcaster: username, {USER_OBJ}",
    "broadcastStop": f"broadcaster: username, {USER_OBJ}",
    "chatMessage": f"broadcaster: username, {USER_OBJ}, {MSG_OBJ}",
    "fanclubJoin": f"broadcaster: username, {USER_OBJ}",
    "follow": f"broadcaster: username, {USER_OBJ}",
    "mediaPurchase": f"broadcaster: username, {USER_OBJ}, {MEDIA_OBJ}",
    "privateMessage": f"broadcaster: username, {USER_OBJ}, {MSG_OBJ}",
    "roomSubjectChange": "broadcaster: username, subject: str (new room title)",
    "tip": f"broadcaster: username, {USER_OBJ}, {TIP_OBJ}",
    "unfollow": f"broadcaster: username, {USER_OBJ}",
    "userEnter": f"broadcaster: username, {USER_OBJ}",
    "userLeave": f"broadcaster: username, {USER_OBJ}",
}


def events_schema_markdown() -> str:
    """Markdown reference table: every event method and its ``object`` shape."""
    rows = "\n".join(f"| `{m}` | {s} |" for m, s in EVENT_OBJECT_SHAPES.items())
    return (
        "Every event in the feed: `{\"method\": str, \"id\": \"<ts>-<seq>\", \"object\": {...}}`. "
        "`object` always includes `broadcaster` (the room's username); the remaining fields depend on method.\n\n"
        "| method | event[\"object\"] |\n|---|---|\n"
        + rows
        + "\n\nWith a *private*-scope events token, `tip` and `privateMessage` events are included; "
        "a *public*-scope token omits them."
    )
