#!/usr/bin/env python3
# /// script
# dependencies = ["langfuse>=3.14.1"]
# requires-python = ">=3.13"
# ///
"""
Sends Claude Code traces to Langfuse after each response.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from common import (
    read_hook_input, is_tracing_enabled, create_langfuse_client,
    log, debug, load_state, save_state,
    get_content, is_tool_result, get_tool_calls, get_text_content,
    merge_assistant_parts,
)
from langfuse import propagate_attributes



def create_trace(
    langfuse,
    session_id: str,
    turn_num: int,
    user_msg: dict,
    assistant_msgs: list,
    tool_results: list,
) -> None:
    """Create a Langfuse trace for a single turn using the new SDK API."""
    # Extract user text
    user_text = get_text_content(user_msg)

    # Extract final assistant text
    final_output = ""
    if assistant_msgs:
        final_output = get_text_content(assistant_msgs[-1])

    # Get model info from first assistant message
    model = "claude"
    if assistant_msgs and isinstance(assistant_msgs[0], dict) and "message" in assistant_msgs[0]:
        model = assistant_msgs[0]["message"].get("model", "claude")

    # Collect all tool calls and results
    all_tool_calls = []
    for assistant_msg in assistant_msgs:
        tool_calls = get_tool_calls(assistant_msg)
        for tool_call in tool_calls:
            tool_name = tool_call.get("name", "unknown")
            tool_input = tool_call.get("input", {})
            tool_id = tool_call.get("id", "")

            # Find matching tool result
            tool_output = None
            for tr in tool_results:
                tr_content = get_content(tr)
                if isinstance(tr_content, list):
                    for item in tr_content:
                        if isinstance(item, dict) and item.get("tool_use_id") == tool_id:
                            tool_output = item.get("content")
                            break

            all_tool_calls.append({
                "name": tool_name,
                "input": tool_input,
                "output": tool_output,
                "id": tool_id,
            })

    # Create trace using the new API with context managers
    with propagate_attributes(session_id=session_id):
        with langfuse.start_as_current_span(
            name=f"Turn {turn_num}",
            input={"role": "user", "content": user_text},
            metadata={
                "source": "claude-code",
                "turn_number": turn_num,
            },
        ) as trace_span:
            # Create generation for the LLM response
            with langfuse.start_as_current_observation(
                name="Claude Response",
                as_type="generation",
                model=model,
                input={"role": "user", "content": user_text},
                output={"role": "assistant", "content": final_output},
                metadata={
                    "tool_count": len(all_tool_calls),
                },
            ) as generation:
                pass  # Generation is auto-completed when exiting context

            # Create spans for tool calls
            for tool_call in all_tool_calls:
                with langfuse.start_as_current_span(
                    name=f"Tool: {tool_call['name']}",
                    input=tool_call["input"],
                    metadata={
                        "tool_name": tool_call["name"],
                        "tool_id": tool_call["id"],
                    },
                ) as tool_span:
                    tool_span.update(output=tool_call["output"])
                debug(f"Created span for tool: {tool_call['name']}")

            # Update trace with output
            trace_span.update(output={"role": "assistant", "content": final_output})

    debug(f"Created trace for turn {turn_num}")


def process_transcript(langfuse, session_id: str, transcript_file: Path, state: dict) -> int:
    """Process a transcript file and create traces for new turns."""
    # Get previous state for this session
    session_state = state.get(session_id, {})
    last_line = session_state.get("last_line", 0)
    turn_count = session_state.get("turn_count", 0)

    # Read transcript
    lines = transcript_file.read_text(encoding='utf-8').strip().split("\n")
    total_lines = len(lines)

    if last_line >= total_lines:
        debug(f"No new lines to process (last: {last_line}, total: {total_lines})")
        return 0

    # Parse new messages
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

    # Group messages into turns (user -> assistant(s) -> tool_results)
    turns = 0
    current_user = None
    current_assistants = []
    current_assistant_parts = []
    current_msg_id = None
    current_tool_results = []

    for msg in new_messages:
        role = msg.get("type") or (msg.get("message", {}).get("role"))

        if role == "user":
            # Check if this is a tool result
            if is_tool_result(msg):
                current_tool_results.append(msg)
                continue

            # New user message - finalize previous turn
            if current_msg_id and current_assistant_parts:
                merged = merge_assistant_parts(current_assistant_parts)
                current_assistants.append(merged)
                current_assistant_parts = []
                current_msg_id = None

            if current_user and current_assistants:
                turns += 1
                turn_num = turn_count + turns
                create_trace(langfuse, session_id, turn_num, current_user, current_assistants, current_tool_results)

            # Start new turn
            current_user = msg
            current_assistants = []
            current_assistant_parts = []
            current_msg_id = None
            current_tool_results = []

        elif role == "assistant":
            msg_id = None
            if isinstance(msg, dict) and "message" in msg:
                msg_id = msg["message"].get("id")

            if not msg_id:
                # No message ID, treat as continuation
                current_assistant_parts.append(msg)
            elif msg_id == current_msg_id:
                # Same message ID, add to current parts
                current_assistant_parts.append(msg)
            else:
                # New message ID - finalize previous message
                if current_msg_id and current_assistant_parts:
                    merged = merge_assistant_parts(current_assistant_parts)
                    current_assistants.append(merged)

                # Start new assistant message
                current_msg_id = msg_id
                current_assistant_parts = [msg]

    # Process final turn
    if current_msg_id and current_assistant_parts:
        merged = merge_assistant_parts(current_assistant_parts)
        current_assistants.append(merged)

    if current_user and current_assistants:
        turns += 1
        turn_num = turn_count + turns
        create_trace(langfuse, session_id, turn_num, current_user, current_assistants, current_tool_results)

    # Update state
    state[session_id] = {
        "last_line": total_lines,
        "turn_count": turn_count + turns,
        "updated": datetime.now(timezone.utc).isoformat(),
    }
    save_state(state)

    return turns


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
