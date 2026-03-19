import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src" / "langfuse"))
from common import get_user_id


def test_cc_langfuse_user_id_takes_precedence():
    """CC_LANGFUSE_USER_ID env var is highest priority."""
    with patch.dict(os.environ, {
        "CC_LANGFUSE_USER_ID": "explicit-user",
        "LANGFUSE_USER_ID": "other-user",
    }):
        assert get_user_id() == "explicit-user"


def test_langfuse_user_id_fallback():
    """LANGFUSE_USER_ID is used when CC_LANGFUSE_USER_ID is not set."""
    env = {"LANGFUSE_USER_ID": "langfuse-user"}
    with patch.dict(os.environ, env, clear=True):
        assert get_user_id() == "langfuse-user"


def test_git_email_fallback():
    """Falls back to git config user.email when no env vars are set."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "dev@example.com\n"

    with patch.dict(os.environ, {}, clear=True):
        with patch("subprocess.run", return_value=mock_result) as mock_sub:
            result = get_user_id()
    assert result == "dev@example.com"
    mock_sub.assert_called_once_with(
        ["git", "config", "user.email"],
        capture_output=True, text=True, timeout=2
    )


def test_git_name_fallback_when_email_empty():
    """Falls back to git config user.name when email is empty."""
    def side_effect(args, **kwargs):
        result = MagicMock()
        if args == ["git", "config", "user.email"]:
            result.returncode = 0
            result.stdout = "\n"
        elif args == ["git", "config", "user.name"]:
            result.returncode = 0
            result.stdout = "Dev Name\n"
        return result

    with patch.dict(os.environ, {}, clear=True):
        with patch("subprocess.run", side_effect=side_effect) as mock_sub:
            result = get_user_id()
    assert result == "Dev Name"
    mock_sub.assert_any_call(
        ["git", "config", "user.name"],
        capture_output=True, text=True, timeout=2
    )


def test_os_getlogin_fallback():
    """Falls back to os.getlogin() when git fails."""
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = ""

    with patch.dict(os.environ, {}, clear=True):
        with patch("subprocess.run", return_value=mock_result):
            with patch("os.getlogin", return_value="osuser"):
                result = get_user_id()
    assert result == "osuser"


def test_username_env_fallback_when_getlogin_raises():
    """Falls back to USERNAME env var when os.getlogin() raises OSError."""
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = ""

    with patch.dict(os.environ, {"USERNAME": "winuser"}, clear=True):
        with patch("subprocess.run", return_value=mock_result):
            with patch("os.getlogin", side_effect=OSError("no tty")):
                result = get_user_id()
    assert result == "winuser"


def test_user_env_fallback():
    """Falls back to USER env var when USERNAME is not set."""
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = ""

    with patch.dict(os.environ, {"USER": "linuxuser"}, clear=True):
        with patch("subprocess.run", return_value=mock_result):
            with patch("os.getlogin", side_effect=OSError("no tty")):
                result = get_user_id()
    assert result == "linuxuser"


def test_unknown_final_fallback():
    """Returns 'unknown' when all other methods fail."""
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = ""

    with patch.dict(os.environ, {}, clear=True):
        with patch("subprocess.run", return_value=mock_result):
            with patch("os.getlogin", side_effect=OSError("no tty")):
                result = get_user_id()
    assert result == "unknown"


def test_subprocess_exception_falls_through():
    """subprocess.run raising an exception falls through to os.getlogin."""
    with patch.dict(os.environ, {}, clear=True):
        with patch("subprocess.run", side_effect=Exception("git not found")):
            with patch("os.getlogin", return_value="fallbackuser"):
                result = get_user_id()
    assert result == "fallbackuser"


def test_returns_non_empty_string_always():
    """get_user_id always returns a non-empty string."""
    with patch.dict(os.environ, {}, clear=True):
        with patch("subprocess.run", side_effect=Exception("fail")):
            with patch("os.getlogin", side_effect=OSError("fail")):
                result = get_user_id()
    assert isinstance(result, str)
    assert len(result) > 0
