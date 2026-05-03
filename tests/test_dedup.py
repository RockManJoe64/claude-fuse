import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hooks"))

from transcript import _deduplicate_assistant_messages


def test_deduplicate_keeps_last_occurrence():
    """Duplicate IDs: last occurrence wins."""
    msgs = [
        {"message": {"id": "msg-1", "content": "first"}},
        {"message": {"id": "msg-1", "content": "second"}},
    ]
    result = _deduplicate_assistant_messages(msgs)
    assert len(result) == 1
    assert result[0]["message"]["content"] == "second"


def test_deduplicate_preserves_order_of_first_appearance():
    """Order is based on first appearance of each ID."""
    msgs = [
        {"message": {"id": "msg-1", "content": "a"}},
        {"message": {"id": "msg-2", "content": "b"}},
        {"message": {"id": "msg-1", "content": "c"}},
    ]
    result = _deduplicate_assistant_messages(msgs)
    assert len(result) == 2
    assert result[0]["message"]["id"] == "msg-1"
    assert result[0]["message"]["content"] == "c"
    assert result[1]["message"]["id"] == "msg-2"
    assert result[1]["message"]["content"] == "b"


def test_deduplicate_handles_no_id():
    """Messages without id are preserved as-is."""
    msgs = [
        {"message": {"content": "no id 1"}},
        {"message": {"content": "no id 2"}},
    ]
    result = _deduplicate_assistant_messages(msgs)
    assert len(result) == 2
    assert result[0]["message"]["content"] == "no id 1"
    assert result[1]["message"]["content"] == "no id 2"


def test_deduplicate_mixed_id_and_no_id():
    """Mix of messages with and without id."""
    msgs = [
        {"message": {"id": "msg-1", "content": "a"}},
        {"message": {"content": "no id"}},
        {"message": {"id": "msg-1", "content": "b"}},
    ]
    result = _deduplicate_assistant_messages(msgs)
    assert len(result) == 2
    assert result[0]["message"]["content"] == "b"
    assert result[1]["message"]["content"] == "no id"


def test_deduplicate_empty_list():
    """Empty list returns empty list."""
    assert _deduplicate_assistant_messages([]) == []
