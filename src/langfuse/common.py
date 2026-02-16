"""
Shared infrastructure for Claude Code Langfuse hooks.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LOG_FILE = Path.home() / ".claude" / "state" / "langfuse_hook.log"
STATE_FILE = Path.home() / ".claude" / "state" / "langfuse_state.json"
DEBUG = os.environ.get("CC_LANGFUSE_DEBUG", "").lower() == "true"


def log(level: str, message: str) -> None:
    """Log a message to the log file."""
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a") as f:
        f.write(f"{timestamp} [{level}] {message}\n")


def debug(message: str) -> None:
    """Log a debug message (only if DEBUG is enabled)."""
    if DEBUG:
        log("DEBUG", message)


def load_state() -> dict:
    """Load the state file containing session tracking info."""
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        return {}


def save_state(state: dict) -> None:
    """Save the state file."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def read_hook_input() -> dict:
    """Read and parse JSON hook input from stdin.

    Claude Code passes context to all hooks via stdin as JSON with common fields:
    session_id, transcript_path, cwd, permission_mode, hook_event_name,
    plus event-specific fields.
    """
    try:
        raw = sys.stdin.read()
        return json.loads(raw)
    except (json.JSONDecodeError, IOError) as e:
        log("ERROR", f"Failed to read hook input from stdin: {e}")
        return {}


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
