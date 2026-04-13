import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
from contextlib import contextmanager

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

    mock_lf = MagicMock()
    mock_span = MagicMock()

    # Set up the context manager properly
    mock_ctx = MagicMock()
    mock_ctx.__enter__ = MagicMock(return_value=mock_span)
    mock_ctx.__exit__ = MagicMock(return_value=False)
    mock_lf.start_as_current_observation.return_value = mock_ctx

    @contextmanager
    def mock_propagate_ctx(**kwargs):
        yield

    # Patch both langfuse.propagate_attributes (used by common.propagate_session_attributes)
    # and the propagate_session_attributes itself in the hook module
    with patch("langfuse.propagate_attributes", mock_propagate_ctx):
        with patch("common.get_user_id", return_value="testuser"):
            result = _create_span_with_timeout(
                mock_lf,
                session_id="test-session",
                source="startup",
                cwd="/test",
                model="claude",
            )

    assert result is True
    mock_lf.start_as_current_observation.assert_called_once()
    # Verify start_as_current_span is not called (if it exists)
    if hasattr(mock_lf, 'start_as_current_span'):
        assert not mock_lf.start_as_current_span.called
