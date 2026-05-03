#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "langfuse>=4.0,<5.0",
# ]
# ///
"""Tracks session end events in Langfuse."""

import sys
import traceback
from datetime import datetime, timezone

from common import (
    read_hook_input,
    is_tracing_enabled,
    create_langfuse_client,
    log,
    debug,
    load_state,
    save_state,
    propagate_session_attributes,
    _get_session_state,
    _delete_session_state,
)


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
        transcript_path = hook_input.get("transcript_path", "")
        session_state = _get_session_state(state, session_id, transcript_path)
        started_at = session_state.get("started_at")
        turn_count = session_state.get("turn_count", 0)

        # Parse duration with fault tolerance
        duration_seconds = None
        if started_at:
            try:
                start_time = datetime.fromisoformat(started_at)
                duration_seconds = (datetime.now(timezone.utc) - start_time).total_seconds()

                # Validate duration_seconds is positive and reasonable (within 24 hours)
                if duration_seconds < 0:
                    log("ERROR", f"Invalid duration_seconds (negative): {duration_seconds}")
                    duration_seconds = None
                elif duration_seconds > 86400:  # 24 hours
                    log("ERROR", f"Duration_seconds exceeds 24 hours: {duration_seconds}")
                    duration_seconds = None
            except ValueError as e:
                log("ERROR", f"Failed to parse started_at timestamp '{started_at}': {e}")
                duration_seconds = None

        output = {
            "status": "session_ended",
            "reason": reason,
            "total_turns": turn_count,
        }
        if duration_seconds is not None:
            output["duration_seconds"] = round(duration_seconds, 1)

        # Wrap Langfuse operations with timeout and error handling
        try:
            with propagate_session_attributes(session_id):
                with langfuse.start_as_current_observation(
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
        except TimeoutError as e:
            log("ERROR", f"Timeout during Langfuse span operation: {e}\n{traceback.format_exc()}")
        except Exception as e:
            log("ERROR", f"Failed to create/update session end span: {e}\n{traceback.format_exc()}")

        # Flush with error handling
        try:
            langfuse.flush()
        except TimeoutError as e:
            log("ERROR", f"Timeout during langfuse.flush(): {e}\n{traceback.format_exc()}")
        except Exception as e:
            log("ERROR", f"Failed to flush Langfuse: {e}\n{traceback.format_exc()}")

        # Delete session state with fault tolerance
        state_saved = False
        try:
            if session_id in state:
                # Save state to temp variable before deletion
                state_backup = dict(state)
                _delete_session_state(state, session_id, transcript_path)
                save_state(state)
                state_saved = True
        except Exception as e:
            log("ERROR", f"Failed to delete session state for {session_id}: {e}
{traceback.format_exc()}")
            if not state_saved:
                try:
                    # Attempt to restore from backup if save failed
                    state_backup = dict(state)
                    save_state(state_backup)
                except Exception as restore_error:
                    log("ERROR", f"Failed to restore state backup: {restore_error}")

    except Exception as e:
        log("ERROR", f"Failed to track session end: {e}\n{traceback.format_exc()}")
    finally:
        # Shutdown with null check and error handling
        if langfuse is not None:
            try:
                langfuse.shutdown()
            except Exception as e:
                log("ERROR", f"Failed to shutdown Langfuse client: {e}\n{traceback.format_exc()}")

    sys.exit(0)


if __name__ == "__main__":
    main()
