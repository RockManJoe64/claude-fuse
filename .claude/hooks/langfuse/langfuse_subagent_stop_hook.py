#!/usr/bin/env python3
# /// script
# dependencies = ["langfuse>=3.14.1"]
# requires-python = ">=3.13"
# ///
"""Tracks subagent stop events in Langfuse."""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from common import (
    read_hook_input,
    is_tracing_enabled,
    create_langfuse_client,
    log,
    debug,
    load_state,
    save_state,
)
from transcript import create_trace, parse_transcript_into_turns

from langfuse import propagate_attributes


def main() -> None:
    """Main entry point for subagent stop hook."""
    hook_input = read_hook_input()

    if not is_tracing_enabled():
        sys.exit(0)

    session_id = hook_input.get("session_id")
    agent_id = hook_input.get("agent_id")
    agent_type = hook_input.get("agent_type")

    if not session_id:
        log("ERROR", "No session_id in hook input")
        sys.exit(1)

    langfuse = create_langfuse_client()
    if not langfuse:
        sys.exit(1)

    try:
        state = load_state()
        subagent_info = state.get(session_id, {}).get("subagents", {}).get(agent_id, {})

        duration_seconds = None
        if "started_at" in subagent_info:
            try:
                started_at = datetime.fromisoformat(subagent_info["started_at"])
                duration_seconds = round(
                    (datetime.now(timezone.utc) - started_at).total_seconds(), 1
                )
            except (ValueError, TypeError):
                pass

        # Parse agent transcript
        total_turns = 0
        agent_transcript_path = hook_input.get("agent_transcript_path")
        if agent_transcript_path:
            transcript_file = Path(agent_transcript_path)
            if transcript_file.exists():
                try:
                    lines = transcript_file.read_text(encoding="utf-8").strip().split("\n")
                    messages = []
                    for line in lines:
                        try:
                            messages.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue

                    turns = parse_transcript_into_turns(messages)
                    total_turns = len(turns)

                    for i, (user_msg, assistant_msgs, tool_results) in enumerate(turns):
                        create_trace(
                            langfuse,
                            session_id,
                            i + 1,
                            user_msg,
                            assistant_msgs,
                            tool_results,
                            name_prefix=f"[{agent_type}]",
                            extra_metadata={"agent_id": agent_id, "agent_type": agent_type},
                        )

                    debug(f"Processed {total_turns} subagent turns for {agent_type} ({agent_id})")
                except Exception as e:
                    log("ERROR", f"Failed to parse agent transcript: {e}")
            else:
                debug(f"Agent transcript not found: {agent_transcript_path}")
        else:
            debug("No agent_transcript_path in hook input")

        # Create lifecycle span
        output = {"status": "subagent_stopped", "agent_type": agent_type, "total_turns": total_turns}
        if duration_seconds is not None:
            output["duration_seconds"] = duration_seconds

        with propagate_attributes(session_id=session_id):
            with langfuse.start_as_current_span(
                name=f"Subagent Stop: {agent_type}",
                input={"agent_id": agent_id, "agent_type": agent_type},
                metadata={
                    "source": "claude-code",
                    "event": "subagent_stop",
                    "agent_type": agent_type,
                    "agent_id": agent_id,
                },
            ) as span:
                span.update(output=output)

        langfuse.flush()

        if session_id in state and "subagents" in state[session_id]:
            state[session_id]["subagents"].pop(agent_id, None)
            save_state(state)

    except Exception as e:
        log("ERROR", f"Failed to track subagent stop: {e}")
    finally:
        langfuse.shutdown()

    sys.exit(0)


if __name__ == "__main__":
    main()
