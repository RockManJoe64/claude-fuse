#!/usr/bin/env python3
# /// script
# dependencies = ["langfuse>=3.14.1"]
# requires-python = ">=3.13"
# ///
"""Tracks session start events in Langfuse."""

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


def main():
    """Main entry point for session start hook."""
    hook_input = read_hook_input()

    if not is_tracing_enabled():
        sys.exit(0)

    session_id = hook_input.get("session_id")
    source = hook_input.get("source", "startup")
    model = hook_input.get("model", "")

    if not session_id:
        log("ERROR", "No session_id provided in hook input")
        sys.exit(1)

    langfuse = create_langfuse_client()
    if not langfuse:
        sys.exit(1)

    try:
        with propagate_attributes(session_id=session_id):
            with langfuse.start_as_current_span(
                name="Session Start",
                input={"source": source, "cwd": hook_input.get("cwd", "")},
                metadata={
                    "source": "claude-code",
                    "event": "session_start",
                    "start_source": source,
                    "model": model,
                },
            ) as span:
                span.update(output={"status": "session_started"})

        langfuse.flush()

        state = load_state()
        state[session_id] = state.get(session_id, {})
        state[session_id]["started_at"] = datetime.now(timezone.utc).isoformat()
        state[session_id]["source"] = source
        save_state(state)

    except Exception as e:
        log("ERROR", f"Error tracking session start: {str(e)}")
    finally:
        langfuse.shutdown()

    sys.exit(0)


if __name__ == "__main__":
    main()
