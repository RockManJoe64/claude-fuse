import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
from contextlib import contextmanager
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src" / "langfuse"))

from common import sanitize_metadata


def test_sanitize_metadata_coerces_values_to_str():
    """Non-string values are converted to strings."""
    result = sanitize_metadata({
        "count": 42,
        "ratio": 3.14,
        "flag": True,
        "name": "already-a-string",
    })
    assert result == {
        "count": "42",
        "ratio": "3.14",
        "flag": "True",
        "name": "already-a-string",
    }


def test_sanitize_metadata_truncates_long_values():
    """Values longer than 200 characters are truncated."""
    long_value = "x" * 300
    result = sanitize_metadata({"key": long_value})
    assert result == {"key": "x" * 200}
    assert len(result["key"]) == 200


def test_sanitize_metadata_handles_empty_dict():
    """Empty dict returns empty dict."""
    assert sanitize_metadata({}) == {}


def _make_mock_langfuse():
    """Create a mock Langfuse client with start_as_current_observation as a context manager."""
    mock_lf = MagicMock()
    mock_span = MagicMock()
    mock_lf.start_as_current_observation.return_value.__enter__ = MagicMock(return_value=mock_span)
    mock_lf.start_as_current_observation.return_value.__exit__ = MagicMock(return_value=False)
    return mock_lf, mock_span


def test_session_start_calls_start_as_current_observation():
    """Session start hook uses start_as_current_observation (v4 API), not start_as_current_span."""
    from langfuse_session_start_hook import _create_span_with_timeout

    mock_lf, mock_span = _make_mock_langfuse()

    @contextmanager
    def mock_propagate(session_id):
        yield

    with patch("langfuse_session_start_hook.propagate_session_attributes", mock_propagate):
        result = _create_span_with_timeout(
            mock_lf,
            session_id="test-session",
            source="startup",
            cwd="/test",
            model="claude",
        )

    assert result is True
    mock_lf.start_as_current_observation.assert_called_once()
    assert not hasattr(mock_lf, 'start_as_current_span') or not mock_lf.start_as_current_span.called


def test_stop_hook_flush_no_timeout_arg():
    """Stop hook calls flush() and shutdown() with no arguments (v4 API)."""
    from langfuse_stop_hook import main

    mock_lf = MagicMock()

    hook_input = {
        "session_id": "test-session",
        "transcript_path": "/test/transcript.jsonl",
        "cwd": "/test",
        "hook_event_name": "Stop",
    }

    # Mock Path.resolve() and is_file() to make transcript file validation pass
    # Mock process_transcript to avoid actual file processing
    with patch("langfuse_stop_hook.read_hook_input", return_value=hook_input), \
         patch("langfuse_stop_hook.is_tracing_enabled", return_value=True), \
         patch("langfuse_stop_hook.create_langfuse_client", return_value=mock_lf), \
         patch("langfuse_stop_hook.load_state", return_value={}), \
         patch("langfuse_stop_hook.save_state"), \
         patch("langfuse_stop_hook.Path") as mock_path_class, \
         patch("langfuse_stop_hook.process_transcript", return_value=0), \
         pytest.raises(SystemExit):
        # Set up Path mock to pass file validation
        mock_path_instance = MagicMock()
        mock_path_instance.resolve.return_value = mock_path_instance
        mock_path_instance.is_file.return_value = True
        mock_path_class.return_value = mock_path_instance

        main()

    # flush() and shutdown() should be called with no positional or keyword args
    mock_lf.flush.assert_called_once_with()
    mock_lf.shutdown.assert_called_once_with()


def test_subagent_start_missing_agent_type_uses_fallback():
    """Subagent start hook uses 'unknown' fallback when agent_type is missing."""
    from langfuse_subagent_start_hook import main

    mock_lf, mock_span = _make_mock_langfuse()

    hook_input = {
        "session_id": "test-session",
        "transcript_path": "/test/transcript.jsonl",
        "cwd": "/test",
        "hook_event_name": "SubagentStart",
        "agent_id": "agent-123",
        # agent_type intentionally missing
    }

    @contextmanager
    def mock_propagate(session_id):
        yield

    with patch("langfuse_subagent_start_hook.read_hook_input", return_value=hook_input), \
         patch("langfuse_subagent_start_hook.is_tracing_enabled", return_value=True), \
         patch("langfuse_subagent_start_hook.create_langfuse_client", return_value=mock_lf), \
         patch("langfuse_subagent_start_hook.propagate_session_attributes", mock_propagate), \
         patch("langfuse_subagent_start_hook.load_state", return_value={}), \
         patch("langfuse_subagent_start_hook.save_state"), \
         pytest.raises(SystemExit) as exc_info:
        main()

    # Should exit 0 (success with fallback), not exit 1 (hard failure)
    assert exc_info.value.code == 0
    # Should have called start_as_current_observation with "unknown" as agent_type
    call_kwargs = mock_lf.start_as_current_observation.call_args
    assert "unknown" in call_kwargs.kwargs["name"]


def test_subagent_start_missing_agent_id_uses_fallback():
    """Subagent start hook uses 'unknown-agent' fallback when agent_id is missing."""
    from langfuse_subagent_start_hook import main

    mock_lf, mock_span = _make_mock_langfuse()

    hook_input = {
        "session_id": "test-session",
        "transcript_path": "/test/transcript.jsonl",
        "cwd": "/test",
        "hook_event_name": "SubagentStart",
        "agent_type": "Explore",
        # agent_id intentionally missing
    }

    @contextmanager
    def mock_propagate(session_id):
        yield

    with patch("langfuse_subagent_start_hook.read_hook_input", return_value=hook_input), \
         patch("langfuse_subagent_start_hook.is_tracing_enabled", return_value=True), \
         patch("langfuse_subagent_start_hook.create_langfuse_client", return_value=mock_lf), \
         patch("langfuse_subagent_start_hook.propagate_session_attributes", mock_propagate), \
         patch("langfuse_subagent_start_hook.load_state", return_value={}), \
         patch("langfuse_subagent_start_hook.save_state"), \
         pytest.raises(SystemExit) as exc_info:
        main()

    # Should exit 0 (success with fallback), not exit 1 (hard failure)
    assert exc_info.value.code == 0
    # Should have called start_as_current_observation with the input containing "unknown-agent"
    call_kwargs = mock_lf.start_as_current_observation.call_args
    assert call_kwargs.kwargs["input"]["agent_id"] == "unknown-agent"


def test_subagent_stop_missing_agent_type_uses_fallback():
    """Subagent stop hook uses 'unknown' fallback when agent_type is missing."""
    from langfuse_subagent_stop_hook import main

    mock_lf = MagicMock()
    mock_lf.start_as_current_observation.return_value.__enter__ = MagicMock(return_value=MagicMock())
    mock_lf.start_as_current_observation.return_value.__exit__ = MagicMock(return_value=False)

    hook_input = {
        "session_id": "test-session",
        "transcript_path": "/test/transcript.jsonl",
        "cwd": "/test",
        "hook_event_name": "SubagentStop",
        "agent_id": "agent-123",
        # agent_type intentionally missing
    }

    @contextmanager
    def mock_propagate(session_id):
        yield

    with patch("langfuse_subagent_stop_hook.read_hook_input", return_value=hook_input), \
         patch("langfuse_subagent_stop_hook.is_tracing_enabled", return_value=True), \
         patch("langfuse_subagent_stop_hook.create_langfuse_client", return_value=mock_lf), \
         patch("langfuse_subagent_stop_hook.propagate_session_attributes", mock_propagate), \
         patch("langfuse_subagent_stop_hook.load_state", return_value={}), \
         patch("langfuse_subagent_stop_hook.save_state"), \
         pytest.raises(SystemExit) as exc_info:
        main()

    # Should exit 0 (success with fallback), not exit 1 (hard failure)
    assert exc_info.value.code == 0
    # Should have called start_as_current_observation with "unknown" as agent_type
    call_kwargs = mock_lf.start_as_current_observation.call_args
    assert "unknown" in call_kwargs.kwargs["name"]


def test_subagent_stop_missing_agent_id_uses_fallback():
    """Subagent stop hook uses 'unknown-agent' fallback when agent_id is missing."""
    from langfuse_subagent_stop_hook import main

    mock_lf = MagicMock()
    mock_lf.start_as_current_observation.return_value.__enter__ = MagicMock(return_value=MagicMock())
    mock_lf.start_as_current_observation.return_value.__exit__ = MagicMock(return_value=False)

    hook_input = {
        "session_id": "test-session",
        "transcript_path": "/test/transcript.jsonl",
        "cwd": "/test",
        "hook_event_name": "SubagentStop",
        "agent_type": "Explore",
        # agent_id intentionally missing
    }

    @contextmanager
    def mock_propagate(session_id):
        yield

    with patch("langfuse_subagent_stop_hook.read_hook_input", return_value=hook_input), \
         patch("langfuse_subagent_stop_hook.is_tracing_enabled", return_value=True), \
         patch("langfuse_subagent_stop_hook.create_langfuse_client", return_value=mock_lf), \
         patch("langfuse_subagent_stop_hook.propagate_session_attributes", mock_propagate), \
         patch("langfuse_subagent_stop_hook.load_state", return_value={}), \
         patch("langfuse_subagent_stop_hook.save_state"), \
         pytest.raises(SystemExit) as exc_info:
        main()

    # Should exit 0 (success with fallback), not exit 1 (hard failure)
    assert exc_info.value.code == 0
    # Should have called start_as_current_observation with the input containing "unknown-agent"
    call_kwargs = mock_lf.start_as_current_observation.call_args
    assert call_kwargs.kwargs["input"]["agent_id"] == "unknown-agent"
