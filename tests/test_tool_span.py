import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
from contextlib import contextmanager

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hooks"))

from transcript import create_trace


def test_create_trace_sets_as_type_tool_on_tool_spans():
    """Tool spans in create_trace must include as_type='tool'."""
    mock_lf = MagicMock()
    mock_obs = MagicMock()
    mock_lf.start_as_current_observation.return_value.__enter__ = MagicMock(return_value=mock_obs)
    mock_lf.start_as_current_observation.return_value.__exit__ = MagicMock(return_value=False)

    @contextmanager
    def mock_propagate(session_id):
        yield

    with patch("transcript.propagate_session_attributes", mock_propagate):
        create_trace(
            langfuse=mock_lf,
            session_id="sess-1",
            turn_num=0,
            user_msg={"message": {"role": "user", "content": "hello"}},
            assistant_msgs=[{
                "message": {
                    "role": "assistant",
                    "model": "claude-3",
                    "content": [
                        {"type": "tool_use", "name": "read_file", "id": "tu-1", "input": {"path": "x.py"}}
                    ]
                }
            }],
            tool_results=[{
                "message": {
                    "role": "user",
                    "content": [
                        {"type": "tool_result", "tool_use_id": "tu-1", "content": "file contents"}
                    ]
                }
            }],
        )

    # Find all calls to start_as_current_observation
    calls = mock_lf.start_as_current_observation.call_args_list
    # We expect at least trace + generation + tool = 3 calls
    assert len(calls) >= 3

    tool_calls = [c for c in calls if c.kwargs.get("as_type") == "tool"]
    assert len(tool_calls) >= 1, f"Expected at least one tool span, got calls: {[c.kwargs for c in calls]}"

    # Verify the tool span has the correct name and input
    tool_call = tool_calls[0]
    assert "Tool: read_file" in tool_call.kwargs["name"]
    assert tool_call.kwargs["input"] == {"path": "x.py"}
