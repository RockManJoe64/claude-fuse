"""Shared transcript parsing and trace creation for Langfuse hooks."""

from common import (
    get_content,
    get_tool_calls,
    get_text_content,
    is_tool_result,
    merge_assistant_parts,
    debug,
    log,
    propagate_session_attributes,
    sanitize_metadata,
)


def parse_transcript_into_turns(messages: list) -> list[tuple[dict, list, list]]:
    """Groups a list of parsed JSON messages into turns.

    Each turn is a (user_msg, assistant_msgs, tool_results) tuple.
    """
    try:
        # Input validation at function entry
        if not isinstance(messages, list):
            log("ERROR", f"parse_transcript_into_turns: messages must be a list, got {type(messages).__name__}")
            return []

        if not messages:
            debug("parse_transcript_into_turns: empty messages list")
            return []

        turns = []
        current_user = None
        current_assistants = []
        current_assistant_parts = []
        current_msg_id = None
        current_tool_results = []

        for idx, msg in enumerate(messages):
            try:
                # Validate msg structure before accessing
                if not isinstance(msg, dict):
                    log("ERROR", f"parse_transcript_into_turns: message at index {idx} is not a dict, skipping")
                    continue

                # Safely extract role with defensive checks
                role = None
                if msg.get("type"):
                    role = msg.get("type")
                elif "message" in msg and isinstance(msg.get("message"), dict):
                    role = msg["message"].get("role")

                if role == "user":
                    try:
                        if is_tool_result(msg):
                            current_tool_results.append(msg)
                            continue
                    except Exception as e:
                        log("ERROR", f"parse_transcript_into_turns: error checking is_tool_result: {e}")

                    # New user message - finalize previous turn
                    if current_msg_id and current_assistant_parts:
                        try:
                            merged = merge_assistant_parts(current_assistant_parts)
                            if merged:
                                current_assistants.append(merged)
                        except Exception as e:
                            log("ERROR", f"parse_transcript_into_turns: error merging assistant parts: {e}")
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
                        msg_dict = msg.get("message")
                        if isinstance(msg_dict, dict):
                            msg_id = msg_dict.get("id")

                    if not msg_id:
                        current_assistant_parts.append(msg)
                    elif msg_id == current_msg_id:
                        current_assistant_parts.append(msg)
                    else:
                        # New message ID - finalize previous message
                        if current_msg_id and current_assistant_parts:
                            try:
                                merged = merge_assistant_parts(current_assistant_parts)
                                if merged:
                                    current_assistants.append(merged)
                            except Exception as e:
                                log("ERROR", f"parse_transcript_into_turns: error merging assistant parts: {e}")

                        # Start new assistant message
                        current_msg_id = msg_id
                        current_assistant_parts = [msg]

            except Exception as e:
                log("ERROR", f"parse_transcript_into_turns: error processing message at index {idx}: {e}")
                continue

        # Process final turn
        if current_msg_id and current_assistant_parts:
            try:
                merged = merge_assistant_parts(current_assistant_parts)
                if merged:
                    current_assistants.append(merged)
            except Exception as e:
                log("ERROR", f"parse_transcript_into_turns: error merging final assistant parts: {e}")

        if current_user and current_assistants:
            turns.append((current_user, current_assistants, current_tool_results))

        debug(f"parse_transcript_into_turns: parsed {len(turns)} turns from {len(messages)} messages")
        return turns

    except Exception as e:
        log("ERROR", f"parse_transcript_into_turns: unexpected error: {e}")
        return []


def create_trace(langfuse, session_id, turn_num, user_msg, assistant_msgs, tool_results, name_prefix="", extra_metadata=None) -> None:
    """Creates a Langfuse trace for a single turn."""
    try:
        # Input validation at function entry
        if langfuse is None:
            log("ERROR", "create_trace: langfuse client is None")
            return

        if not isinstance(session_id, str) or not session_id:
            log("ERROR", f"create_trace: session_id must be a non-empty string, got {type(session_id).__name__}")
            return

        if not isinstance(turn_num, int) or turn_num < 0:
            log("ERROR", f"create_trace: turn_num must be a non-negative integer, got {turn_num}")
            return

        if not isinstance(user_msg, dict):
            log("ERROR", f"create_trace: user_msg must be a dict, got {type(user_msg).__name__}")
            return

        if not isinstance(assistant_msgs, list):
            log("ERROR", f"create_trace: assistant_msgs must be a list, got {type(assistant_msgs).__name__}")
            return

        if not isinstance(tool_results, list):
            log("ERROR", f"create_trace: tool_results must be a list, got {type(tool_results).__name__}")
            return

        # Extract user text with error handling
        try:
            user_text = get_text_content(user_msg)
        except Exception as e:
            log("ERROR", f"create_trace: error extracting user text: {e}")
            user_text = ""

        # Extract final output with error handling
        final_output = ""
        if assistant_msgs:
            try:
                final_output = get_text_content(assistant_msgs[-1])
            except Exception as e:
                log("ERROR", f"create_trace: error extracting final output: {e}")
                final_output = ""

        # Extract model with error handling and defensive checks
        model = "claude"
        if assistant_msgs:
            try:
                first_msg = assistant_msgs[0]
                if isinstance(first_msg, dict) and "message" in first_msg:
                    msg_dict = first_msg.get("message")
                    if isinstance(msg_dict, dict):
                        model = msg_dict.get("model", "claude")
            except Exception as e:
                log("ERROR", f"create_trace: error extracting model: {e}")
                model = "claude"

        # Extract tool calls with comprehensive error handling
        all_tool_calls = []
        try:
            # Add performance limit for large tool call lists
            tool_call_count = 0
            max_tool_calls = 1000  # Prevent performance issues with extremely large lists

            for assistant_msg in assistant_msgs:
                try:
                    tool_calls = get_tool_calls(assistant_msg)
                    if not isinstance(tool_calls, list):
                        log("ERROR", f"create_trace: get_tool_calls returned non-list: {type(tool_calls).__name__}")
                        continue

                    for tool_call in tool_calls:
                        if tool_call_count >= max_tool_calls:
                            log("WARNING", f"create_trace: exceeded maximum tool calls ({max_tool_calls}), truncating")
                            break

                        try:
                            if not isinstance(tool_call, dict):
                                log("ERROR", f"create_trace: tool_call is not a dict, skipping")
                                continue

                            tool_name = tool_call.get("name", "unknown")
                            tool_input = tool_call.get("input", {})
                            tool_id = tool_call.get("id", "")

                            # Validate types
                            if not isinstance(tool_name, str):
                                tool_name = str(tool_name)
                            if not isinstance(tool_input, dict):
                                tool_input = {}
                            if not isinstance(tool_id, str):
                                tool_id = str(tool_id)

                            tool_output = None
                            try:
                                # Search for tool output in results
                                for tr in tool_results:
                                    if not isinstance(tr, dict):
                                        continue
                                    try:
                                        tr_content = get_content(tr)
                                        if isinstance(tr_content, list):
                                            for item in tr_content:
                                                if isinstance(item, dict) and item.get("tool_use_id") == tool_id:
                                                    tool_output = item.get("content")
                                                    break
                                    except Exception as e:
                                        log("ERROR", f"create_trace: error processing tool result: {e}")
                                        continue
                            except Exception as e:
                                log("ERROR", f"create_trace: error searching tool results: {e}")

                            all_tool_calls.append({
                                "name": tool_name,
                                "input": tool_input,
                                "output": tool_output,
                                "id": tool_id
                            })
                            tool_call_count += 1
                        except Exception as e:
                            log("ERROR", f"create_trace: error processing tool_call: {e}")
                            continue

                except Exception as e:
                    log("ERROR", f"create_trace: error getting tool_calls from assistant message: {e}")
                    continue

        except Exception as e:
            log("ERROR", f"create_trace: unexpected error extracting tool calls: {e}")
            all_tool_calls = []

        # Build trace names with error handling
        try:
            turn_name = f"{name_prefix} Turn {turn_num}" if name_prefix else f"Turn {turn_num}"
            gen_name = f"{name_prefix} Claude Response" if name_prefix else "Claude Response"
        except Exception as e:
            log("ERROR", f"create_trace: error building trace names: {e}")
            turn_name = f"Turn {turn_num}"
            gen_name = "Claude Response"

        def build_metadata(base):
            try:
                if not isinstance(base, dict):
                    base = {}
                if extra_metadata and isinstance(extra_metadata, dict):
                    return sanitize_metadata({**base, **extra_metadata})
                return sanitize_metadata(base)
            except Exception as e:
                log("ERROR", f"create_trace: error building metadata: {e}")
                try:
                    return sanitize_metadata(base) if isinstance(base, dict) else {}
                except Exception:
                    return {}

        # Create trace with comprehensive error handling for Langfuse API calls
        try:
            with propagate_session_attributes(session_id):
                try:
                    with langfuse.start_as_current_observation(
                        name=turn_name,
                        input={"role": "user", "content": user_text},
                        metadata=build_metadata({"source": "claude-code", "turn_number": turn_num}),
                    ) as trace_span:
                        if trace_span is None:
                            log("ERROR", "create_trace: trace_span is None after starting span")
                            return

                        try:
                            with langfuse.start_as_current_observation(
                                name=gen_name,
                                as_type="generation",
                                model=model,
                                input={"role": "user", "content": user_text},
                                output={"role": "assistant", "content": final_output},
                                metadata=build_metadata({"tool_count": len(all_tool_calls)}),
                            ) as generation:
                                if generation is None:
                                    log("ERROR", "create_trace: generation observation is None")
                                else:
                                    debug("create_trace: created generation observation")
                        except Exception as e:
                            log("ERROR", f"create_trace: error creating generation observation: {e}")

                        # Create tool spans with defensive loop
                        try:
                            for tool_call in all_tool_calls:
                                try:
                                    if not isinstance(tool_call, dict):
                                        log("ERROR", f"create_trace: tool_call is not dict in loop, skipping")
                                        continue

                                    tool_name = tool_call.get("name", "unknown")
                                    tool_span_name = f"{name_prefix} Tool: {tool_name}" if name_prefix else f"Tool: {tool_name}"

                                    with langfuse.start_as_current_observation(
                                        name=tool_span_name,
                                        input=tool_call.get("input", {}),
                                        metadata=build_metadata({
                                            "tool_name": tool_call.get("name", "unknown"),
                                            "tool_id": tool_call.get("id", "")
                                        }),
                                    ) as tool_span:
                                        if tool_span is None:
                                            log("ERROR", f"create_trace: tool_span is None for {tool_name}")
                                        else:
                                            try:
                                                tool_span.update(output=tool_call.get("output"))
                                                debug(f"create_trace: created span for tool: {tool_name}")
                                            except Exception as e:
                                                log("ERROR", f"create_trace: error updating tool_span output: {e}")
                                except Exception as e:
                                    log("ERROR", f"create_trace: error creating tool span: {e}")
                                    continue

                        except Exception as e:
                            log("ERROR", f"create_trace: error in tool spans loop: {e}")

                        # Update trace span output
                        try:
                            trace_span.update(output={"role": "assistant", "content": final_output})
                            debug(f"create_trace: updated trace span for turn {turn_num}")
                        except Exception as e:
                            log("ERROR", f"create_trace: error updating trace_span output: {e}")

                except Exception as e:
                    log("ERROR", f"create_trace: error in propagate_attributes context: {e}")

        except Exception as e:
            log("ERROR", f"create_trace: error creating Langfuse trace: {e}")
            return

        debug(f"create_trace: completed trace for turn {turn_num} with {len(all_tool_calls)} tool calls")

    except Exception as e:
        log("ERROR", f"create_trace: unexpected outer error: {e}")
