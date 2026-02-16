#!/usr/bin/env python3
"""Tracks subagent stop events in Langfuse."""

import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

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

    # Validate agent_type and agent_id (high priority fix)
    if not agent_type or not isinstance(agent_type, str) or agent_type.strip() == "":
        log("ERROR", "Invalid or missing agent_type in hook input")
        sys.exit(1)

    if not agent_id or not isinstance(agent_id, str) or agent_id.strip() == "":
        log("ERROR", "Invalid or missing agent_id in hook input")
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

        # Parse agent transcript with fault tolerance
        total_turns = 0
        agent_transcript_path = hook_input.get("agent_transcript_path")
        if agent_transcript_path:
            # Input validation for file path (medium priority fix)
            if not isinstance(agent_transcript_path, str) or agent_transcript_path.strip() == "":
                debug("Invalid agent_transcript_path: path is empty or not a string")
            else:
                try:
                    transcript_file = Path(agent_transcript_path)

                    # Validate file path exists before attempting to read
                    if not transcript_file.exists():
                        debug(f"Agent transcript not found: {agent_transcript_path}")
                    elif not transcript_file.is_file():
                        log("ERROR", f"Agent transcript path is not a file: {agent_transcript_path}")
                    else:
                        try:
                            messages = []
                            skipped_lines = 0

                            # Streaming for large transcript files (high priority fix)
                            try:
                                with open(transcript_file, "r", encoding="utf-8") as f:
                                    for line_num, line in enumerate(f, 1):
                                        line = line.strip()
                                        if not line:
                                            continue
                                        try:
                                            messages.append(json.loads(line))
                                        except json.JSONDecodeError as je:
                                            skipped_lines += 1
                                            # Add logging for JSON parsing failures (medium priority fix)
                                            debug(f"Skipped invalid JSON at line {line_num}: {str(je)}")
                            except IOError as io_err:
                                log("ERROR", f"Failed to read transcript file: {io_err}")
                                traceback.print_exc()
                                messages = []

                            if skipped_lines > 0:
                                debug(f"Skipped {skipped_lines} invalid JSON lines from transcript")

                            if messages:
                                try:
                                    turns = parse_transcript_into_turns(messages)
                                    total_turns = len(turns)

                                    for i, (user_msg, assistant_msgs, tool_results) in enumerate(turns):
                                        try:
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
                                        except Exception as trace_err:
                                            log("ERROR", f"Failed to create trace for turn {i + 1}: {trace_err}")
                                            traceback.print_exc()
                                            continue

                                    debug(f"Processed {total_turns} subagent turns for {agent_type} ({agent_id})")
                                except Exception as parse_err:
                                    log("ERROR", f"Failed to parse transcript into turns: {parse_err}")
                                    traceback.print_exc()
                            else:
                                debug(f"No valid messages found in transcript: {agent_transcript_path}")

                        except Exception as e:
                            log("ERROR", f"Failed to process agent transcript: {e}")
                            traceback.print_exc()
                except Exception as path_err:
                    log("ERROR", f"Failed to handle agent transcript path: {path_err}")
                    traceback.print_exc()
        else:
            debug("No agent_transcript_path in hook input")

        # Create lifecycle span with exception handling (critical fix)
        output = {"status": "subagent_stopped", "agent_type": agent_type, "total_turns": total_turns}
        if duration_seconds is not None:
            output["duration_seconds"] = duration_seconds

        try:
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
        except Exception as span_err:
            log("ERROR", f"Failed to create Langfuse span: {span_err}")
            traceback.print_exc()

        # Flush with timeout handling (critical fix)
        try:
            langfuse.flush(timeout=10)
        except Exception as flush_err:
            log("ERROR", f"Failed to flush Langfuse: {flush_err}")
            traceback.print_exc()

        # Wrap state cleanup in try/except (critical fix)
        try:
            if session_id in state and "subagents" in state[session_id]:
                state[session_id]["subagents"].pop(agent_id, None)
                save_state(state)
        except Exception as state_err:
            log("ERROR", f"Failed to clean up state: {state_err}")
            traceback.print_exc()

    except Exception as e:
        log("ERROR", f"Failed to track subagent stop: {e}")
    finally:
        langfuse.shutdown()

    sys.exit(0)


if __name__ == "__main__":
    main()
