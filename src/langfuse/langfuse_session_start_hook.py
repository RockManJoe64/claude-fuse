#!/usr/bin/env python3
"""Tracks session start events in Langfuse."""

import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import socket
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from common import (
    read_hook_input,
    is_tracing_enabled,
    create_langfuse_client,
    log,
    debug,
    load_state,
    save_state,
)
from langfuse import propagate_attributes


def _validate_hook_input(hook_input: dict) -> bool:
    """Validate required hook input fields.

    Args:
        hook_input: The hook input dictionary to validate

    Returns:
        True if validation passes, False otherwise
    """
    session_id = hook_input.get("session_id")
    if not session_id:
        log("ERROR", "No session_id provided in hook input")
        return False

    source = hook_input.get("source", "startup")
    if not isinstance(source, str) or not source.strip():
        log("ERROR", f"Invalid source value: {source}")
        return False

    model = hook_input.get("model", "")
    if not isinstance(model, str):
        log("ERROR", f"Invalid model value: {model}")
        return False

    return True


def _create_span_with_timeout(
    langfuse,
    session_id: str,
    source: str,
    cwd: str,
    model: str,
    timeout: float = 10.0
) -> bool:
    """Create a span with timeout handling for Langfuse operations.

    Args:
        langfuse: The Langfuse client instance
        session_id: Session ID for the span
        source: Source of the session start
        cwd: Current working directory
        model: Model information
        timeout: Timeout in seconds for the operation

    Returns:
        True if span creation succeeded, False otherwise
    """
    try:
        with propagate_attributes(session_id=session_id):
            with langfuse.start_as_current_span(
                name="Session Start",
                input={"source": source, "cwd": cwd},
                metadata={
                    "source": "claude-code",
                    "event": "session_start",
                    "start_source": source,
                    "model": model,
                },
            ) as span:
                span.update(output={"status": "session_started"})

        return True

    except (socket.timeout, requests.exceptions.Timeout, TimeoutError) as e:
        log(
            "ERROR",
            f"Timeout while creating span: {str(e)}\n"
            f"Stack trace:\n{traceback.format_exc()}"
        )
        return False

    except (socket.error, requests.exceptions.ConnectionError) as e:
        log(
            "ERROR",
            f"Network error while creating span: {str(e)}\n"
            f"Stack trace:\n{traceback.format_exc()}"
        )
        return False

    except Exception as e:
        log(
            "ERROR",
            f"Unexpected error while creating span: {str(e)}\n"
            f"Stack trace:\n{traceback.format_exc()}"
        )
        return False


def _flush_langfuse_with_timeout(
    langfuse,
    timeout: float = 10.0
) -> bool:
    """Flush Langfuse client with timeout handling.

    Args:
        langfuse: The Langfuse client instance
        timeout: Timeout in seconds for the flush operation

    Returns:
        True if flush succeeded, False otherwise
    """
    try:
        langfuse.flush()
        return True

    except (socket.timeout, requests.exceptions.Timeout, TimeoutError) as e:
        log(
            "ERROR",
            f"Timeout while flushing Langfuse: {str(e)}\n"
            f"Stack trace:\n{traceback.format_exc()}"
        )
        return False

    except (socket.error, requests.exceptions.ConnectionError) as e:
        log(
            "ERROR",
            f"Network error while flushing Langfuse: {str(e)}\n"
            f"Stack trace:\n{traceback.format_exc()}"
        )
        return False

    except Exception as e:
        log(
            "ERROR",
            f"Unexpected error while flushing Langfuse: {str(e)}\n"
            f"Stack trace:\n{traceback.format_exc()}"
        )
        return False


def _shutdown_langfuse_safely(langfuse: Optional[object]) -> None:
    """Safely shutdown Langfuse client with null check and error handling.

    Args:
        langfuse: The Langfuse client instance (may be None)
    """
    if langfuse is None:
        debug("Langfuse client is None, skipping shutdown")
        return

    try:
        langfuse.shutdown()
    except (socket.timeout, requests.exceptions.Timeout, TimeoutError) as e:
        log(
            "WARNING",
            f"Timeout while shutting down Langfuse: {str(e)}\n"
            f"Stack trace:\n{traceback.format_exc()}"
        )
    except (socket.error, requests.exceptions.ConnectionError) as e:
        log(
            "WARNING",
            f"Network error while shutting down Langfuse: {str(e)}\n"
            f"Stack trace:\n{traceback.format_exc()}"
        )
    except Exception as e:
        log(
            "WARNING",
            f"Error while shutting down Langfuse: {str(e)}\n"
            f"Stack trace:\n{traceback.format_exc()}"
        )


def main():
    """Main entry point for session start hook."""
    hook_input = read_hook_input()

    if not is_tracing_enabled():
        sys.exit(0)

    # Validate hook input fields
    if not _validate_hook_input(hook_input):
        sys.exit(1)

    session_id = hook_input.get("session_id")
    source = hook_input.get("source", "startup")
    model = hook_input.get("model", "")
    cwd = hook_input.get("cwd", "")

    langfuse = create_langfuse_client()
    if not langfuse:
        sys.exit(1)

    try:
        # Create span with timeout handling
        if not _create_span_with_timeout(langfuse, session_id, source, cwd, model):
            log("ERROR", "Failed to create span, continuing with shutdown")
        else:
            # Flush with timeout handling
            if not _flush_langfuse_with_timeout(langfuse):
                log("ERROR", "Failed to flush Langfuse, continuing")

        # Save state
        try:
            state = load_state()
            state[session_id] = state.get(session_id, {})
            state[session_id]["started_at"] = datetime.now(timezone.utc).isoformat()
            state[session_id]["source"] = source
            save_state(state)
        except Exception as e:
            log(
                "ERROR",
                f"Error saving session state: {str(e)}\n"
                f"Stack trace:\n{traceback.format_exc()}"
            )

    except Exception as e:
        log(
            "ERROR",
            f"Unexpected error in main execution: {str(e)}\n"
            f"Stack trace:\n{traceback.format_exc()}"
        )
    finally:
        # Safely shutdown Langfuse
        _shutdown_langfuse_safely(langfuse)

    sys.exit(0)


if __name__ == "__main__":
    main()
