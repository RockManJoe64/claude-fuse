import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hooks"))

from common import truncate_text


def test_truncate_text_under_limit_passes_through():
    """Text under max chars is returned unchanged."""
    text = "Hello, world!"
    result, meta = truncate_text(text)
    assert result == text
    assert meta["truncated"] is False


def test_truncate_text_over_limit_is_truncated():
    """Text over max chars is truncated and metadata set."""
    text = "x" * 25000
    result, meta = truncate_text(text)
    assert len(result) == 20000
    assert meta["truncated"] is True
    assert meta["original_chars"] == 25000
    assert meta["truncated_to"] == 20000


def test_truncate_text_exact_limit():
    """Text exactly at limit passes through."""
    text = "x" * 20000
    result, meta = truncate_text(text)
    assert result == text
    assert meta["truncated"] is False


def test_truncate_text_env_override():
    """CC_LANGFUSE_MAX_CHARS env var overrides default."""
    text = "x" * 150
    os.environ["CC_LANGFUSE_MAX_CHARS"] = "100"
    try:
        result, meta = truncate_text(text)
        assert len(result) == 100
        assert meta["truncated"] is True
    finally:
        del os.environ["CC_LANGFUSE_MAX_CHARS"]


def test_truncate_text_empty_string():
    """Empty string is handled gracefully."""
    result, meta = truncate_text("")
    assert result == ""
    assert meta["truncated"] is False
