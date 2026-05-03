import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hooks"))

from common import _make_state_key


def test_make_state_key_is_consistent():
    """Same inputs always produce the same key."""
    key1 = _make_state_key("sess-123", "/path/to/transcript.jsonl")
    key2 = _make_state_key("sess-123", "/path/to/transcript.jsonl")
    assert key1 == key2


def test_make_state_key_uses_sha256():
    """Key is a SHA256 hex digest."""
    key = _make_state_key("sess-123", "/path/to/transcript.jsonl")
    assert len(key) == 64
    # Verify it's valid hex
    int(key, 16)


def test_different_transcript_paths_produce_different_keys():
    """Same session_id with different transcript paths yields different keys."""
    key1 = _make_state_key("sess-123", "/path/a/transcript.jsonl")
    key2 = _make_state_key("sess-123", "/path/b/transcript.jsonl")
    assert key1 != key2


def test_different_sessions_produce_different_keys():
    """Different session_ids yield different keys."""
    key1 = _make_state_key("sess-1", "/path/transcript.jsonl")
    key2 = _make_state_key("sess-2", "/path/transcript.jsonl")
    assert key1 != key2
