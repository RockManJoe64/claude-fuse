import sys
from pathlib import Path

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
