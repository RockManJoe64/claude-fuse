#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "langfuse>=4.0,<5.0",
# ]
# ///
"""
Sends Claude Code traces to Langfuse after each response.
"""

import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from common import (
    read_hook_input, is_tracing_enabled, create_langfuse_client,
    log, debug, load_state, save_state,
)
from transcript import create_trace, parse_transcript_into_turns


def process_transcript(langfuse, session_id: str, transcript_file: Path, state: dict) -> int:
    """Process a transcript file and create traces for new turns.

    Uses streaming to avoid loading entire files into memory.
    Implements fault-tolerant state management and JSON parsing.
    """
    session_state = state.get(session_id, {})
    last_line = session_state.get("last_line", 0)
    turn_count = session_state.get("turn_count", 0)

    # Validate transcript file path
    try:
        transcript_file = transcript_file.resolve()
        if not transcript_file.is_file():
            log("ERROR", f"Transcript path is not a file: {transcript_file}")
            return 0
    except (OSError, ValueError) as e:
        log("ERROR", f"Invalid transcript file path: {e}")
        return 0

    # Stream the transcript file instead of loading it all at once
    try:
        with open(transcript_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except (IOError, OSError, UnicodeDecodeError) as e:
        log("ERROR", f"Failed to read transcript file: {e}")
        return 0

    total_lines = len(lines)

    if last_line >= total_lines:
        debug(f"No new lines to process (last: {last_line}, total: {total_lines})")
        return 0

    new_messages = []
    skipped_count = 0
    for i in range(last_line, total_lines):
        try:
            line = lines[i].strip()
            if not line:
                continue
            msg = json.loads(line)
            new_messages.append(msg)
        except json.JSONDecodeError as e:
            skipped_count += 1
            debug(f"Skipped invalid JSON at line {i+1}: {e}")
            continue
        except Exception as e:
            skipped_count += 1
            debug(f"Error parsing line {i+1}: {e}")
            continue

    if skipped_count > 0:
        debug(f"Skipped {skipped_count} lines with parsing errors")

    if not new_messages:
        debug(f"No valid messages to process (tried {total_lines - last_line} lines)")
        return 0

    debug(f"Processing {len(new_messages)} new messages")

    try:
        turns = parse_transcript_into_turns(new_messages)
    except Exception as e:
        log("ERROR", f"Failed to parse transcript into turns: {e}")
        return 0

    for i, (user_msg, assistant_msgs, tool_results) in enumerate(turns):
        turn_num = turn_count + i + 1
        try:
            create_trace(langfuse, session_id, turn_num, user_msg, assistant_msgs, tool_results)
        except Exception as e:
            log("ERROR", f"Failed to create trace for turn {turn_num}: {e}")
            continue

    # Safe state update: save to temp file first, then overwrite on success
    new_state = {
        "last_line": total_lines,
        "turn_count": turn_count + len(turns),
        "updated": datetime.now(timezone.utc).isoformat(),
    }

    try:
        # Create temporary backup and save new state safely
        old_state = state.copy()
        state[session_id] = new_state

        # Attempt to save state to temp location first
        temp_file = None
        try:
            with tempfile.NamedTemporaryFile(
                mode='w',
                suffix='.json',
                delete=False,
                encoding='utf-8'
            ) as tmp:
                temp_file = Path(tmp.name)
                json.dump(state, tmp, indent=2)

            # Verify temp file was written
            if not temp_file.exists():
                raise IOError(f"Temp state file not created: {temp_file}")

            # Now save to permanent location
            save_state(state)
            debug(f"State updated successfully for session {session_id}")

        finally:
            # Clean up temp file
            if temp_file and temp_file.exists():
                try:
                    temp_file.unlink()
                except Exception as e:
                    debug(f"Failed to clean up temp file: {e}")

    except Exception as e:
        log("ERROR", f"Failed to update state for session {session_id}: {e}")
        # Revert state in memory to avoid inconsistency
        state = old_state
        raise

    return len(turns)


def main():
    import signal
    import traceback

    script_start = datetime.now()
    debug("Hook started")

    hook_input = read_hook_input()

    if not is_tracing_enabled():
        debug("Tracing disabled")
        sys.exit(0)

    session_id = hook_input.get("session_id")
    transcript_path = hook_input.get("transcript_path")

    if not session_id or not transcript_path:
        debug("Missing session_id or transcript_path")
        sys.exit(0)

    # Validate transcript path
    try:
        transcript_file = Path(transcript_path).resolve()
        if not transcript_file.is_file():
            log("ERROR", f"Transcript not found or not a file: {transcript_file}")
            sys.exit(0)
    except (OSError, ValueError) as e:
        log("ERROR", f"Invalid transcript path: {e}")
        sys.exit(0)

    langfuse = create_langfuse_client()
    if not langfuse:
        sys.exit(0)

    state = load_state()

    turns = 0
    try:
        turns = process_transcript(langfuse, session_id, transcript_file, state)
    except Exception as e:
        log("ERROR", f"Failed to process transcript: {e}")
        debug(f"Traceback: {traceback.format_exc()}")
        # Continue to cleanup phase
    finally:
        # Cleanup: flush and shutdown Langfuse with timeout handling
        try:
            debug("Attempting to flush Langfuse")
            langfuse.flush()
            debug("Langfuse flushed successfully")
        except Exception as e:
            log("WARN", f"Failed to flush Langfuse: {e}")
            debug(f"Flush error details: {traceback.format_exc()}")

        try:
            debug("Attempting to shutdown Langfuse")
            langfuse.shutdown()
            debug("Langfuse shutdown successfully")
        except Exception as e:
            log("WARN", f"Failed to shutdown Langfuse gracefully: {e}")
            debug(f"Shutdown error details: {traceback.format_exc()}")

    duration = (datetime.now() - script_start).total_seconds()
    if turns > 0:
        log("INFO", f"Processed {turns} turns in {duration:.1f}s")
    else:
        debug(f"No turns processed in {duration:.1f}s")

    if duration > 180:
        log("WARN", f"Hook took {duration:.1f}s (>3min), consider optimizing")

    sys.exit(0)


if __name__ == "__main__":
    main()
