#!/usr/bin/env python3
"""Tracks subagent start events in Langfuse."""

import sys
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
    propagate_session_attributes,
)


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

    # Validate required fields for subagent tracking
    if not agent_id:
        log("ERROR", "No agent_id provided in hook input")
        sys.exit(1)

    if not agent_type:
        log("ERROR", "No agent_type provided in hook input")
        sys.exit(1)

    langfuse = create_langfuse_client()
    if not langfuse:
        sys.exit(1)

    try:
        # Wrap propagate_attributes in try/except for specific error handling
        try:
            with propagate_session_attributes(session_id):
                # Wrap start_as_current_span with timeout handling
                try:
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
                except TimeoutError as e:
                    log("ERROR", f"Timeout during span creation: {str(e)}")
                    debug(f"Timeout stack trace: {repr(e)}")
                except Exception as e:
                    log("ERROR", f"Failed to create span: {str(e)}")
                    debug(f"Span creation error stack trace: {repr(e)}")
                    raise
        except Exception as e:
            log("ERROR", f"Error in propagate_attributes context: {str(e)}")
            debug(f"Propagate attributes error stack trace: {repr(e)}")
            raise

        # Wrap flush with timeout handling
        try:
            langfuse.flush()
        except TimeoutError as e:
            log("ERROR", f"Timeout during langfuse flush: {str(e)}")
            debug(f"Flush timeout stack trace: {repr(e)}")
        except Exception as e:
            log("ERROR", f"Failed to flush langfuse: {str(e)}")
            debug(f"Flush error stack trace: {repr(e)}")

        # Load and validate state structure before modification
        try:
            state = load_state()
            if not isinstance(state, dict):
                log("WARNING", "State is not a dict, reinitializing")
                state = {}

            # Validate and initialize session state
            if session_id not in state or not isinstance(state[session_id], dict):
                state[session_id] = {}

            if "subagents" not in state[session_id] or not isinstance(
                state[session_id]["subagents"], dict
            ):
                state[session_id]["subagents"] = {}

            # Update subagent information
            state[session_id]["subagents"][agent_id] = {
                "started_at": datetime.now(timezone.utc).isoformat(),
                "agent_type": agent_type,
            }

            # Wrap save_state in try/except for specific error handling
            try:
                save_state(state)
            except IOError as e:
                log("ERROR", f"IOError saving state: {str(e)}")
                debug(f"IO error stack trace: {repr(e)}")
            except Exception as e:
                log("ERROR", f"Unexpected error saving state: {str(e)}")
                debug(f"Save state error stack trace: {repr(e)}")

        except Exception as e:
            log("ERROR", f"Error managing state: {str(e)}")
            debug(f"State management error stack trace: {repr(e)}")

    except Exception as e:
        log("ERROR", f"Error tracking subagent start: {str(e)}")
        debug(f"Main error stack trace: {repr(e)}")
    finally:
        # Add null check before shutdown
        if langfuse is not None:
            try:
                langfuse.shutdown()
            except Exception as e:
                log("ERROR", f"Error during langfuse shutdown: {str(e)}")
                debug(f"Shutdown error stack trace: {repr(e)}")
        else:
            debug("Langfuse client was None, skipping shutdown")

    sys.exit(0)


if __name__ == "__main__":
    main()
