#!/usr/bin/env python3
# /// script
# dependencies = ["langfuse>=3.14.1"]
# requires-python = ">=3.13"
# ///
"""Tracks session end events in Langfuse."""

import sys
from datetime import datetime, timezone

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


def main() -> None:
    """Handle session end event."""
    hook_input = read_hook_input()

    if not is_tracing_enabled():
        sys.exit(0)

    session_id = hook_input.get("session_id")
    reason = hook_input.get("reason", "unknown")

    if not session_id:
        log("ERROR", "No session_id in hook input")
        sys.exit(1)

    langfuse = create_langfuse_client()
    if langfuse is None:
        sys.exit(1)

    try:
        state = load_state()
        session_state = state.get(session_id, {})
        started_at = session_state.get("started_at")
        turn_count = session_state.get("turn_count", 0)

        duration_seconds = None
        if started_at:
            start_time = datetime.fromisoformat(started_at)
            duration_seconds = (datetime.now(timezone.utc) - start_time).total_seconds()

        output = {
            "status": "session_ended",
            "reason": reason,
            "total_turns": turn_count,
        }
        if duration_seconds is not None:
            output["duration_seconds"] = round(duration_seconds, 1)

        with propagate_attributes(session_id=session_id):
            with langfuse.start_as_current_span(
                name="Session End",
                input={"reason": reason},
                metadata={
                    "source": "claude-code",
                    "event": "session_end",
                    "end_reason": reason,
                    "total_turns": str(turn_count),
                },
            ) as span:
                span.update(output=output)

        langfuse.flush()

        if session_id in state:
            del state[session_id]
        save_state(state)

    except Exception as e:
        log("ERROR", f"Failed to track session end: {e}")
    finally:
        langfuse.shutdown()

    sys.exit(0)


if __name__ == "__main__":
    main()
