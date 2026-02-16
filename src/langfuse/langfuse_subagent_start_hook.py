#!/usr/bin/env python3
"""Tracks subagent start events in Langfuse."""

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.langfuse.common import (
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
    """Main entry point for subagent start hook."""
    hook_input = read_hook_input()

    if not is_tracing_enabled():
        sys.exit(0)

    session_id = hook_input.get("session_id")
    agent_id = hook_input.get("agent_id")
    agent_type = hook_input.get("agent_type")

    if not session_id:
        log("ERROR", "No session_id provided in hook input")
        sys.exit(1)

    langfuse = create_langfuse_client()
    if not langfuse:
        sys.exit(1)

    try:
        with propagate_attributes(session_id=session_id):
            with langfuse.start_as_current_span(
                name=f"Subagent Start: {agent_type}",
                input={"agent_id": agent_id, "agent_type": agent_type},
                metadata={
                    "source": "claude-code",
                    "event": "subagent_start",
                    "agent_type": agent_type,
                    "agent_id": agent_id,
                },
            ) as span:
                span.update(output={"status": "subagent_started"})

        langfuse.flush()

        state = load_state()
        state[session_id] = state.get(session_id, {})
        state[session_id].setdefault("subagents", {})
        state[session_id]["subagents"][agent_id] = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "agent_type": agent_type,
        }
        save_state(state)

    except Exception as e:
        log("ERROR", f"Error tracking subagent start: {str(e)}")
    finally:
        langfuse.shutdown()

    sys.exit(0)


if __name__ == "__main__":
    main()
