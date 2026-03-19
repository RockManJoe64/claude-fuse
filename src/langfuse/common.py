"""
Shared infrastructure for Claude Code Langfuse hooks.
"""

import json
import os
import platform
import signal
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from contextlib import contextmanager
from typing import Any

LOG_FILE = Path.home() / ".claude" / "state" / "langfuse_hook.log"
STATE_FILE = Path.home() / ".claude" / "state" / "langfuse_state.json"
DEBUG = os.environ.get("CC_LANGFUSE_DEBUG", "").lower() == "true"


def _acquire_file_lock(file_path: Path, timeout: float = 1.0):
    """Acquire a file lock using platform-specific methods.

    Args:
        file_path: Path to file to lock
        timeout: Lock acquisition timeout in seconds

    Returns:
        File object with lock acquired, or None if lock failed
    """
    try:
        file_obj = open(file_path, "a")

        if platform.system() == "Windows":
            import msvcrt
            start_time = datetime.now()
            while True:
                try:
                    msvcrt.locking(file_obj.fileno(), msvcrt.LK_NBLCK, 1)
                    return file_obj
                except (OSError, IOError):
                    elapsed = (datetime.now() - start_time).total_seconds()
                    if elapsed > timeout:
                        file_obj.close()
                        return None
                    threading.Event().wait(0.01)
        else:
            import fcntl
            try:
                fcntl.flock(file_obj.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                return file_obj
            except (OSError, IOError):
                # Try with blocking if non-blocking fails
                try:
                    signal.alarm(int(timeout) + 1)
                    fcntl.flock(file_obj.fileno(), fcntl.LOCK_EX)
                    signal.alarm(0)
                    return file_obj
                except (OSError, IOError):
                    signal.alarm(0)
                    file_obj.close()
                    return None
    except Exception as e:
        debug(f"Failed to acquire file lock for {file_path}: {e}")
        return None


def _release_file_lock(file_obj):
    """Release a file lock and close the file."""
    if file_obj:
        try:
            if platform.system() != "Windows":
                import fcntl
                fcntl.flock(file_obj.fileno(), fcntl.LOCK_UN)
            file_obj.close()
        except Exception:
            pass


def log(level: str, message: str) -> None:
    """Log a message to the log file with fault tolerance.

    Attempts to create log directory and write message with file locking.
    Failures are silently ignored to prevent hook crashes.
    """
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        file_obj = _acquire_file_lock(LOG_FILE, timeout=0.5)
        if file_obj:
            try:
                file_obj.write(f"{timestamp} [{level}] {message}\n")
                file_obj.flush()
            finally:
                _release_file_lock(file_obj)
    except Exception as e:
        # Silently fail - logging failures should not crash hooks
        pass


def debug(message: str) -> None:
    """Log a debug message (only if DEBUG is enabled)."""
    if DEBUG:
        log("DEBUG", message)


def load_state() -> dict:
    """Load the state file containing session tracking info.

    Returns empty dict on any error (file missing, JSON invalid, I/O error).
    Logs errors when DEBUG is enabled.
    """
    if not STATE_FILE.exists():
        debug("State file does not exist, returning empty state")
        return {}

    try:
        content = STATE_FILE.read_text(encoding="utf-8")
        return json.loads(content)
    except json.JSONDecodeError as e:
        log("ERROR", f"Failed to parse state file JSON: {e}")
        debug(f"State file corrupted at {STATE_FILE}: {e}")
        return {}
    except IOError as e:
        log("ERROR", f"Failed to read state file: {e}")
        debug(f"I/O error reading {STATE_FILE}: {e}")
        return {}
    except Exception as e:
        log("ERROR", f"Unexpected error loading state: {e}")
        return {}


def save_state(state: dict) -> None:
    """Save the state file with fault tolerance and file locking.

    Creates parent directories as needed. Uses file locking to prevent
    race conditions. Failures are logged but do not crash the hook.
    """
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

        # Try to acquire lock and write atomically
        file_obj = _acquire_file_lock(STATE_FILE, timeout=1.0)
        if file_obj:
            try:
                # Truncate and write new content
                file_obj.seek(0)
                file_obj.truncate()
                content = json.dumps(state, indent=2)
                file_obj.write(content)
                file_obj.flush()
                debug(f"Successfully saved state to {STATE_FILE}")
            finally:
                _release_file_lock(file_obj)
        else:
            log("WARNING", f"Failed to acquire lock on state file, retrying with standard write")
            # Fallback to standard write without lock
            STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except json.JSONDecodeError as e:
        log("ERROR", f"Failed to serialize state to JSON: {e}")
    except IOError as e:
        log("ERROR", f"Failed to write state file: {e}")
    except Exception as e:
        log("ERROR", f"Unexpected error saving state: {e}")


# Timeout handler for stdin reads
_stdin_timeout_occurred = False


def _stdin_timeout_handler(signum, frame):
    """Signal handler for stdin read timeout."""
    global _stdin_timeout_occurred
    _stdin_timeout_occurred = True
    raise TimeoutError("stdin read timeout")


def read_hook_input(timeout_seconds: int = 5) -> dict:
    """Read and parse JSON hook input from stdin with timeout and validation.

    Claude Code passes context to all hooks via stdin as JSON with common fields:
    session_id, transcript_path, cwd, permission_mode, hook_event_name,
    plus event-specific fields.

    Args:
        timeout_seconds: Maximum time to wait for stdin input (Unix only)

    Returns:
        Parsed JSON dict, or empty dict on any error
    """
    global _stdin_timeout_occurred
    _stdin_timeout_occurred = False
    old_handler = None

    try:
        # Set timeout on Unix systems
        if platform.system() != "Windows":
            try:
                old_handler = signal.signal(signal.SIGALRM, _stdin_timeout_handler)
                signal.alarm(timeout_seconds)
            except (ValueError, OSError):
                # signal.alarm not available in all contexts
                debug("Could not set stdin timeout (signal.alarm unavailable)")

        raw = sys.stdin.read()

        # Clear alarm
        if platform.system() != "Windows":
            try:
                signal.alarm(0)
            except (ValueError, OSError):
                pass

        if not raw or not raw.strip():
            log("ERROR", "Empty input received from stdin")
            return {}

        parsed = json.loads(raw)

        # Validate required fields
        if not isinstance(parsed, dict):
            log("ERROR", f"Expected JSON object, got {type(parsed).__name__}")
            return {}

        required_fields = {
            "session_id": str,
            "transcript_path": str,
            "cwd": str,
            "hook_event_name": str,
        }

        missing_fields = []
        for field, expected_type in required_fields.items():
            if field not in parsed:
                missing_fields.append(field)
            elif not isinstance(parsed[field], expected_type):
                log(
                    "ERROR",
                    f"Field '{field}' has wrong type: expected {expected_type.__name__}, got {type(parsed[field]).__name__}",
                )

        if missing_fields:
            log("ERROR", f"Hook input missing required fields: {', '.join(missing_fields)}")
            debug(f"Received input keys: {list(parsed.keys())}")
            return {}

        debug(f"Successfully parsed hook input for event: {parsed.get('hook_event_name')}")
        return parsed

    except TimeoutError as e:
        log("ERROR", f"Timeout reading from stdin after {timeout_seconds} seconds: {e}")
        return {}
    except json.JSONDecodeError as e:
        log("ERROR", f"Failed to parse hook input JSON: {e}")
        debug(f"Invalid JSON from stdin: {raw[:200] if 'raw' in locals() else 'N/A'}")
        return {}
    except IOError as e:
        log("ERROR", f"I/O error reading from stdin: {e}")
        return {}
    except Exception as e:
        log("ERROR", f"Unexpected error reading hook input: {e}")
        return {}
    finally:
        # Clean up signal handler
        if old_handler is not None:
            try:
                signal.signal(signal.SIGALRM, old_handler)
                signal.alarm(0)
            except (ValueError, OSError):
                pass


def is_tracing_enabled() -> bool:
    """Check if TRACE_TO_LANGFUSE env var is set to true."""
    return os.environ.get("TRACE_TO_LANGFUSE", "").lower() == "true"


def create_langfuse_client():
    """Initialize and return a Langfuse client, or None on failure."""
    try:
        from langfuse import Langfuse
    except ImportError:
        print(
            "Error: langfuse package not installed. Run: uv add langfuse",
            file=sys.stderr,
        )
        return None

    public_key = os.environ.get("CC_LANGFUSE_PUBLIC_KEY") or os.environ.get(
        "LANGFUSE_PUBLIC_KEY"
    )
    secret_key = os.environ.get("CC_LANGFUSE_SECRET_KEY") or os.environ.get(
        "LANGFUSE_SECRET_KEY"
    )
    host = os.environ.get("CC_LANGFUSE_HOST") or os.environ.get(
        "LANGFUSE_HOST", "https://cloud.langfuse.com"
    )

    if not public_key or not secret_key:
        log(
            "ERROR",
            "Langfuse API keys not set (CC_LANGFUSE_PUBLIC_KEY / CC_LANGFUSE_SECRET_KEY)",
        )
        return None

    try:
        return Langfuse(public_key=public_key, secret_key=secret_key, host=host)
    except Exception as e:
        log("ERROR", f"Failed to initialize Langfuse client: {e}")
        return None


def get_content(msg: dict) -> Any:
    """Extract content from a message."""
    if isinstance(msg, dict):
        if "message" in msg:
            return msg["message"].get("content")
        return msg.get("content")
    return None


def is_tool_result(msg: dict) -> bool:
    """Check if a message contains tool results."""
    content = get_content(msg)
    if isinstance(content, list):
        return any(
            isinstance(item, dict) and item.get("type") == "tool_result"
            for item in content
        )
    return False


def get_tool_calls(msg: dict) -> list:
    """Extract tool use blocks from a message."""
    content = get_content(msg)
    if isinstance(content, list):
        return [
            item
            for item in content
            if isinstance(item, dict) and item.get("type") == "tool_use"
        ]
    return []


def get_text_content(msg: dict) -> str:
    """Extract text content from a message."""
    content = get_content(msg)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text_parts.append(item.get("text", ""))
            elif isinstance(item, str):
                text_parts.append(item)
        return "\n".join(text_parts)
    return ""


def merge_assistant_parts(parts: list) -> dict:
    """Merge multiple assistant message parts into one."""
    if not parts:
        return {}

    merged_content = []
    for part in parts:
        content = get_content(part)
        if isinstance(content, list):
            merged_content.extend(content)
        elif content:
            merged_content.append({"type": "text", "text": str(content)})

    result = parts[0].copy()
    if "message" in result:
        result["message"] = result["message"].copy()
        result["message"]["content"] = merged_content
    else:
        result["content"] = merged_content

    return result


def get_user_id() -> str:
    """Resolve user identity for Langfuse tracking.

    Priority order:
    1. CC_LANGFUSE_USER_ID env var
    2. LANGFUSE_USER_ID env var
    3. git config user.email
    4. git config user.name
    5. os.getlogin()
    6. USERNAME (Windows) or USER (Unix) env var — USERNAME takes precedence
    7. "unknown"
    """
    # 1. Explicit env vars
    user_id = os.environ.get("CC_LANGFUSE_USER_ID", "").strip()
    if user_id:
        return user_id

    user_id = os.environ.get("LANGFUSE_USER_ID", "").strip()
    if user_id:
        return user_id

    # 2. Git config
    try:
        result = subprocess.run(
            ["git", "config", "user.email"],
            capture_output=True, text=True, timeout=2
        )
        if result.returncode == 0:
            user_id = result.stdout.strip()
            if user_id:
                return user_id

        result = subprocess.run(
            ["git", "config", "user.name"],
            capture_output=True, text=True, timeout=2
        )
        if result.returncode == 0:
            user_id = result.stdout.strip()
            if user_id:
                return user_id
    except Exception:
        pass

    # 3. OS username
    try:
        user_id = os.getlogin()
        if user_id:
            return user_id
    except Exception:
        pass

    user_id = os.environ.get("USERNAME") or os.environ.get("USER") or ""
    if user_id:
        return user_id

    return "unknown"


@contextmanager
def propagate_session_attributes(session_id: str):
    """Context manager that propagates session_id and user_id to Langfuse.

    Wraps langfuse.propagate_attributes, resolving user_id via get_user_id().
    Use this instead of calling propagate_attributes directly.
    """
    from langfuse import propagate_attributes
    user_id = get_user_id()
    with propagate_attributes(session_id=session_id, user_id=user_id):
        yield
