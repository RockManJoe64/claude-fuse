#!/usr/bin/env python3
"""
Sends Claude Code traces to Langfuse after each response.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from src.langfuse.common import (
    read_hook_input, is_tracing_enabled, create_langfuse_client,
    log, debug, load_state, save_state,
)
from src.langfuse.transcript import create_trace, parse_transcript_into_turns


def process_transcript(langfuse, session_id: str, transcript_file: Path, state: dict) -> int:
    """Process a transcript file and create traces for new turns."""
    session_state = state.get(session_id, {})
    last_line = session_state.get("last_line", 0)
    turn_count = session_state.get("turn_count", 0)

    lines = transcript_file.read_text(encoding='utf-8').strip().split("\n")
    total_lines = len(lines)

    if last_line >= total_lines:
        debug(f"No new lines to process (last: {last_line}, total: {total_lines})")
        return 0

    new_messages = []
    for i in range(last_line, total_lines):
        try:
            msg = json.loads(lines[i])
            new_messages.append(msg)
        except json.JSONDecodeError:
            continue

    if not new_messages:
        return 0

    debug(f"Processing {len(new_messages)} new messages")

    turns = parse_transcript_into_turns(new_messages)

    for i, (user_msg, assistant_msgs, tool_results) in enumerate(turns):
        turn_num = turn_count + i + 1
        create_trace(langfuse, session_id, turn_num, user_msg, assistant_msgs, tool_results)

    state[session_id] = {
        "last_line": total_lines,
        "turn_count": turn_count + len(turns),
        "updated": datetime.now(timezone.utc).isoformat(),
    }
    save_state(state)

    return len(turns)


def main():
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

    transcript_file = Path(transcript_path)
    if not transcript_file.exists():
        debug(f"Transcript not found: {transcript_file}")
        sys.exit(0)

    langfuse = create_langfuse_client()
    if not langfuse:
        sys.exit(0)

    state = load_state()

    try:
        turns = process_transcript(langfuse, session_id, transcript_file, state)
        langfuse.flush()
        duration = (datetime.now() - script_start).total_seconds()
        log("INFO", f"Processed {turns} turns in {duration:.1f}s")
        if duration > 180:
            log("WARN", f"Hook took {duration:.1f}s (>3min), consider optimizing")
    except Exception as e:
        log("ERROR", f"Failed to process transcript: {e}")
        import traceback
        debug(traceback.format_exc())
    finally:
        langfuse.shutdown()

    sys.exit(0)


if __name__ == "__main__":
    main()
