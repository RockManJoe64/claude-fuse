import os
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hooks"))

from common import create_langfuse_client


def test_langfuse_base_url_env_fallback():
    """LANGFUSE_BASE_URL env var is used as host fallback."""
    env = {
        "CC_LANGFUSE_PUBLIC_KEY": "pk",
        "CC_LANGFUSE_SECRET_KEY": "sk",
        "LANGFUSE_BASE_URL": "https://custom.langfuse.com",
    }
    with patch.dict(os.environ, env, clear=True):
        with patch("langfuse.Langfuse") as mock_langfuse:
            create_langfuse_client()

    mock_langfuse.assert_called_once()
    call_kwargs = mock_langfuse.call_args.kwargs
    assert call_kwargs["host"] == "https://custom.langfuse.com"


def test_cc_langfuse_base_url_takes_precedence_over_base_url():
    """CC_LANGFUSE_BASE_URL takes precedence over LANGFUSE_BASE_URL."""
    env = {
        "CC_LANGFUSE_PUBLIC_KEY": "pk",
        "CC_LANGFUSE_SECRET_KEY": "sk",
        "CC_LANGFUSE_BASE_URL": "https://cc-custom.langfuse.com",
        "LANGFUSE_BASE_URL": "https://fallback.langfuse.com",
    }
    with patch.dict(os.environ, env, clear=True):
        with patch("langfuse.Langfuse") as mock_langfuse:
            create_langfuse_client()

    call_kwargs = mock_langfuse.call_args.kwargs
    assert call_kwargs["host"] == "https://cc-custom.langfuse.com"


def test_base_url_is_lowest_priority_after_host():
    """CC_LANGFUSE_HOST takes precedence over CC_LANGFUSE_BASE_URL."""
    env = {
        "CC_LANGFUSE_PUBLIC_KEY": "pk",
        "CC_LANGFUSE_SECRET_KEY": "sk",
        "CC_LANGFUSE_HOST": "https://host.langfuse.com",
        "CC_LANGFUSE_BASE_URL": "https://base.url.langfuse.com",
    }
    with patch.dict(os.environ, env, clear=True):
        with patch("langfuse.Langfuse") as mock_langfuse:
            create_langfuse_client()

    call_kwargs = mock_langfuse.call_args.kwargs
    assert call_kwargs["host"] == "https://host.langfuse.com"
