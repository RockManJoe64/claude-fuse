"""Shared transcript parsing and trace creation for Langfuse hooks."""

from src.langfuse.common import (
    get_content,
    get_tool_calls,
    get_text_content,
    is_tool_result,
    merge_assistant_parts,
    debug,
)
from langfuse import propagate_attributes


def parse_transcript_into_turns(messages: list) -> list[tuple[dict, list, list]]:
    """Groups a list of parsed JSON messages into turns.

    Each turn is a (user_msg, assistant_msgs, tool_results) tuple.
    """
    turns = []
    current_user = None
    current_assistants = []
    current_assistant_parts = []
    current_msg_id = None
    current_tool_results = []

    for msg in messages:
        role = msg.get("type") or msg.get("message", {}).get("role")

        if role == "user":
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
                turns.append((current_user, current_assistants, current_tool_results))

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
                current_assistant_parts.append(msg)
            elif msg_id == current_msg_id:
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
        turns.append((current_user, current_assistants, current_tool_results))

    return turns


def create_trace(langfuse, session_id, turn_num, user_msg, assistant_msgs, tool_results, name_prefix="", extra_metadata=None) -> None:
    """Creates a Langfuse trace for a single turn."""
    user_text = get_text_content(user_msg)
    final_output = ""
    if assistant_msgs:
        final_output = get_text_content(assistant_msgs[-1])

    model = "claude"
    if assistant_msgs and isinstance(assistant_msgs[0], dict) and "message" in assistant_msgs[0]:
        model = assistant_msgs[0]["message"].get("model", "claude")

    all_tool_calls = []
    for assistant_msg in assistant_msgs:
        tool_calls = get_tool_calls(assistant_msg)
        for tool_call in tool_calls:
            tool_name = tool_call.get("name", "unknown")
            tool_input = tool_call.get("input", {})
            tool_id = tool_call.get("id", "")
            tool_output = None
            for tr in tool_results:
                tr_content = get_content(tr)
                if isinstance(tr_content, list):
                    for item in tr_content:
                        if isinstance(item, dict) and item.get("tool_use_id") == tool_id:
                            tool_output = item.get("content")
                            break
            all_tool_calls.append({"name": tool_name, "input": tool_input, "output": tool_output, "id": tool_id})

    turn_name = f"{name_prefix} Turn {turn_num}" if name_prefix else f"Turn {turn_num}"
    gen_name = f"{name_prefix} Claude Response" if name_prefix else "Claude Response"

    def build_metadata(base):
        if extra_metadata:
            return {**base, **extra_metadata}
        return base

    with propagate_attributes(session_id=session_id):
        with langfuse.start_as_current_span(
            name=turn_name,
            input={"role": "user", "content": user_text},
            metadata=build_metadata({"source": "claude-code", "turn_number": turn_num}),
        ) as trace_span:
            with langfuse.start_as_current_observation(
                name=gen_name,
                as_type="generation",
                model=model,
                input={"role": "user", "content": user_text},
                output={"role": "assistant", "content": final_output},
                metadata=build_metadata({"tool_count": len(all_tool_calls)}),
            ) as generation:
                pass

            for tool_call in all_tool_calls:
                tool_span_name = f"{name_prefix} Tool: {tool_call['name']}" if name_prefix else f"Tool: {tool_call['name']}"
                with langfuse.start_as_current_span(
                    name=tool_span_name,
                    input=tool_call["input"],
                    metadata=build_metadata({"tool_name": tool_call["name"], "tool_id": tool_call["id"]}),
                ) as tool_span:
                    tool_span.update(output=tool_call["output"])
                debug(f"Created span for tool: {tool_call['name']}")

            trace_span.update(output={"role": "assistant", "content": final_output})

    debug(f"Created trace for turn {turn_num}")
