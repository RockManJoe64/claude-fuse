import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hooks"))

from common import _make_state_key, _get_session_state, _delete_session_state


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


def test_get_session_state_returns_existing_hashed_key():
    """If hashed key exists, return it directly."""
    state = {}
    key = _make_state_key("sess-1", "/path/t.jsonl")
    state[key] = {"offset": 42}
    result = _get_session_state(state, "sess-1", "/path/t.jsonl")
    assert result == {"offset": 42}


def test_get_session_state_migrates_legacy_key():
    """If only legacy unhashed key exists, migrate to hashed key."""
    state = {"sess-1": {"offset": 99}}
    result = _get_session_state(state, "sess-1", "/path/t.jsonl")
    assert result == {"offset": 99}
    # Legacy key should be removed, hashed key should exist
    assert "sess-1" not in state
    key = _make_state_key("sess-1", "/path/t.jsonl")
    assert key in state


def test_get_session_state_creates_new_key():
    """If no key exists, create empty dict at hashed key."""
    state = {}
    result = _get_session_state(state, "sess-1", "/path/t.jsonl")
    assert result == {}
    key = _make_state_key("sess-1", "/path/t.jsonl")
    assert key in state


def test_delete_session_state_removes_both_keys():
    """Delete removes both hashed and legacy keys."""
    state = {
        "sess-1": {"offset": 1},
        _make_state_key("sess-1", "/path/t.jsonl"): {"offset": 2},
    }
    _delete_session_state(state, "sess-1", "/path/t.jsonl")
    assert "sess-1" not in state
    assert _make_state_key("sess-1", "/path/t.jsonl") not in state


def test_delete_session_state_does_not_error_on_missing():
    """Delete on missing keys does not raise."""
    state = {}
    _delete_session_state(state, "sess-1", "/path/t.jsonl")
    assert state == {}
