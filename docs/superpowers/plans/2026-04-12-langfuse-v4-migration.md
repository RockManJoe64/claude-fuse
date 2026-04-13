# Langfuse v4 SDK Migration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate all Langfuse hooks from the removed v3 API to v4, harden validation, add metadata coercion, pin the SDK version, and add test coverage.

**Architecture:** Six call sites swap `start_as_current_span` → `start_as_current_observation`. Two call sites drop `timeout` kwargs from `flush()`/`shutdown()`. Subagent hooks soften validation to log+fallback instead of hard exit. A new `sanitize_metadata` helper in `common.py` ensures all metadata values are `str` (v4 requirement). Tests mock the Langfuse client to verify the new API calls.

**Tech Stack:** Python 3.13+, Langfuse Python SDK v4, pytest, unittest.mock

**Spec:** `docs/superpowers/specs/2026-04-12-langfuse-v4-migration-design.md`

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `pyproject.toml` | Modify | Version pin `langfuse>=4.0,<5.0` |
| `src/langfuse/common.py` | Modify | Add `sanitize_metadata()` helper |
| `src/langfuse/transcript.py` | Modify | Swap `start_as_current_span` → `start_as_current_observation` (2 sites), use `sanitize_metadata` in `build_metadata` |
| `src/langfuse/langfuse_session_start_hook.py` | Modify | Swap `start_as_current_span` → `start_as_current_observation` |
| `src/langfuse/langfuse_session_end_hook.py` | Modify | Swap `start_as_current_span` → `start_as_current_observation` |
| `src/langfuse/langfuse_stop_hook.py` | Modify | Remove `timeout` from `flush()` and `shutdown()` |
| `src/langfuse/langfuse_subagent_start_hook.py` | Modify | Swap `start_as_current_span` → `start_as_current_observation`, soften `agent_id`/`agent_type` validation |
| `src/langfuse/langfuse_subagent_stop_hook.py` | Modify | Swap `start_as_current_span` → `start_as_current_observation`, remove `flush(timeout=...)`, soften `agent_type`/`agent_id` validation |
| `tests/test_v4_migration.py` | Create | 7 tests for migration changes |

---

### Task 1: Add `sanitize_metadata` helper and tests

**Files:**
- Modify: `src/langfuse/common.py:455` (append after `propagate_session_attributes`)
- Create: `tests/test_v4_migration.py`

- [ ] **Step 1: Write the failing tests for `sanitize_metadata`**

Create `tests/test_v4_migration.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src" / "langfuse"))

from common import sanitize_metadata


def test_sanitize_metadata_coerces_values_to_str():
    """Non-string values are converted to strings."""
    result = sanitize_metadata({
        "count": 42,
        "ratio": 3.14,
        "flag": True,
        "name": "already-a-string",
    })
    assert result == {
        "count": "42",
        "ratio": "3.14",
        "flag": "True",
        "name": "already-a-string",
    }


def test_sanitize_metadata_truncates_long_values():
    """Values longer than 200 characters are truncated."""
    long_value = "x" * 300
    result = sanitize_metadata({"key": long_value})
    assert result == {"key": "x" * 200}
    assert len(result["key"]) == 200


def test_sanitize_metadata_handles_empty_dict():
    """Empty dict returns empty dict."""
    assert sanitize_metadata({}) == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_v4_migration.py -v`

Expected: FAIL with `ImportError: cannot import name 'sanitize_metadata' from 'common'`

- [ ] **Step 3: Implement `sanitize_metadata` in `common.py`**

Add at the end of `src/langfuse/common.py` (after `propagate_session_attributes`):

```python
def sanitize_metadata(meta: dict) -> dict[str, str]:
    """Coerce metadata values to str for Langfuse v4 compatibility.

    Langfuse v4 requires metadata to be dict[str, str] with values
    limited to 200 characters. Non-string values are converted via str().
    """
    return {str(k): str(v)[:200] for k, v in meta.items()}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_v4_migration.py -v`

Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/langfuse/common.py tests/test_v4_migration.py
git commit -m "feat: add sanitize_metadata helper for Langfuse v4 compatibility"
```

---

### Task 2: Migrate `transcript.py` — swap API + wire in `sanitize_metadata`

**Files:**
- Modify: `src/langfuse/transcript.py:3` (imports), `transcript.py:269-275` (`build_metadata`), `transcript.py:284` (span), `transcript.py:320` (tool span)

- [ ] **Step 1: Update import in `transcript.py`**

Add `sanitize_metadata` to the import from `common` at line 3:

```python
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
```

- [ ] **Step 2: Update `build_metadata` to apply `sanitize_metadata`**

In `transcript.py`, replace the `build_metadata` function (lines 269-278):

```python
        def build_metadata(base):
            try:
                if not isinstance(base, dict):
                    base = {}
                if extra_metadata and isinstance(extra_metadata, dict):
                    return sanitize_metadata({**base, **extra_metadata})
                return sanitize_metadata(base)
            except Exception as e:
                log("ERROR", f"create_trace: error building metadata: {e}")
                return sanitize_metadata(base) if isinstance(base, dict) else {}
```

- [ ] **Step 3: Replace `start_as_current_span` with `start_as_current_observation` at line 284**

Replace:
```python
                    with langfuse.start_as_current_span(
```

With:
```python
                    with langfuse.start_as_current_observation(
```

- [ ] **Step 4: Replace `start_as_current_span` with `start_as_current_observation` at line 320**

Replace:
```python
                                    with langfuse.start_as_current_span(
```

With:
```python
                                    with langfuse.start_as_current_observation(
```

- [ ] **Step 5: Run existing tests to check for regressions**

Run: `uv run pytest -v`

Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add src/langfuse/transcript.py
git commit -m "feat: migrate transcript.py to Langfuse v4 API and wire in sanitize_metadata"
```

---

### Task 3: Migrate session start hook

**Files:**
- Modify: `src/langfuse/langfuse_session_start_hook.py:76`
- Modify: `tests/test_v4_migration.py` (add test)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_v4_migration.py`:

```python
import os
from unittest.mock import MagicMock, patch, call
from contextlib import contextmanager


def _make_mock_langfuse():
    """Create a mock Langfuse client with start_as_current_observation as a context manager."""
    mock_lf = MagicMock()
    mock_span = MagicMock()
    mock_lf.start_as_current_observation.return_value.__enter__ = MagicMock(return_value=mock_span)
    mock_lf.start_as_current_observation.return_value.__exit__ = MagicMock(return_value=False)
    return mock_lf, mock_span


def test_session_start_calls_start_as_current_observation():
    """Session start hook uses start_as_current_observation (v4 API), not start_as_current_span."""
    from langfuse_session_start_hook import _create_span_with_timeout

    mock_lf, mock_span = _make_mock_langfuse()

    @contextmanager
    def mock_propagate(**kwargs):
        yield

    with patch("langfuse_session_start_hook.propagate_session_attributes", mock_propagate):
        result = _create_span_with_timeout(
            mock_lf,
            session_id="test-session",
            source="startup",
            cwd="/test",
            model="claude",
        )

    assert result is True
    mock_lf.start_as_current_observation.assert_called_once()
    assert not hasattr(mock_lf, 'start_as_current_span') or not mock_lf.start_as_current_span.called
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_v4_migration.py::test_session_start_calls_start_as_current_observation -v`

Expected: FAIL — the hook still calls `start_as_current_span`, so `start_as_current_observation` is never called.

- [ ] **Step 3: Replace `start_as_current_span` with `start_as_current_observation` in session start hook**

In `src/langfuse/langfuse_session_start_hook.py` line 76, replace:

```python
            with langfuse.start_as_current_span(
```

With:

```python
            with langfuse.start_as_current_observation(
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_v4_migration.py::test_session_start_calls_start_as_current_observation -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/langfuse/langfuse_session_start_hook.py tests/test_v4_migration.py
git commit -m "feat: migrate session start hook to Langfuse v4 API"
```

---

### Task 4: Migrate session end hook

**Files:**
- Modify: `src/langfuse/langfuse_session_end_hook.py:76`

- [ ] **Step 1: Replace `start_as_current_span` with `start_as_current_observation`**

In `src/langfuse/langfuse_session_end_hook.py` line 76, replace:

```python
                with langfuse.start_as_current_span(
```

With:

```python
                with langfuse.start_as_current_observation(
```

- [ ] **Step 2: Run all tests to check for regressions**

Run: `uv run pytest -v`

Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git add src/langfuse/langfuse_session_end_hook.py
git commit -m "feat: migrate session end hook to Langfuse v4 API"
```

---

### Task 5: Migrate stop hook — remove `timeout` kwargs

**Files:**
- Modify: `src/langfuse/langfuse_stop_hook.py:191,199`
- Modify: `tests/test_v4_migration.py` (add test)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_v4_migration.py`:

```python
def test_stop_hook_flush_no_timeout_arg():
    """Stop hook calls flush() and shutdown() with no arguments (v4 API)."""
    from langfuse_stop_hook import main

    mock_lf = MagicMock()

    hook_input = {
        "session_id": "test-session",
        "transcript_path": "/nonexistent/transcript.jsonl",
        "cwd": "/test",
        "hook_event_name": "Stop",
    }

    with patch("langfuse_stop_hook.read_hook_input", return_value=hook_input), \
         patch("langfuse_stop_hook.is_tracing_enabled", return_value=True), \
         patch("langfuse_stop_hook.create_langfuse_client", return_value=mock_lf), \
         patch("langfuse_stop_hook.load_state", return_value={}), \
         patch("langfuse_stop_hook.save_state"), \
         pytest.raises(SystemExit):
        main()

    # flush() and shutdown() should be called with no positional or keyword args
    mock_lf.flush.assert_called_once_with()
    mock_lf.shutdown.assert_called_once_with()
```

Add these imports to the top of `tests/test_v4_migration.py` (after the existing imports):

```python
import pytest
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_v4_migration.py::test_stop_hook_flush_no_timeout_arg -v`

Expected: FAIL — `flush` is called with `timeout=30`

- [ ] **Step 3: Remove `timeout` from `flush()` at line 191**

In `src/langfuse/langfuse_stop_hook.py` line 191, replace:

```python
            langfuse.flush(timeout=30)
```

With:

```python
            langfuse.flush()
```

- [ ] **Step 4: Remove `timeout` from `shutdown()` at line 199**

In `src/langfuse/langfuse_stop_hook.py` line 199, replace:

```python
            langfuse.shutdown(timeout=30)
```

With:

```python
            langfuse.shutdown()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_v4_migration.py::test_stop_hook_flush_no_timeout_arg -v`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/langfuse/langfuse_stop_hook.py tests/test_v4_migration.py
git commit -m "fix: remove timeout kwargs from flush/shutdown in stop hook (v4 API)"
```

---

### Task 6: Migrate subagent start hook — swap API + soften validation

**Files:**
- Modify: `src/langfuse/langfuse_subagent_start_hook.py:38-44,56`
- Modify: `tests/test_v4_migration.py` (add tests)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_v4_migration.py`:

```python
def test_subagent_start_missing_agent_type_uses_fallback():
    """Subagent start hook uses 'unknown' fallback when agent_type is missing."""
    from langfuse_subagent_start_hook import main

    mock_lf = MagicMock()
    mock_lf.start_as_current_observation.return_value.__enter__ = MagicMock(return_value=MagicMock())
    mock_lf.start_as_current_observation.return_value.__exit__ = MagicMock(return_value=False)

    hook_input = {
        "session_id": "test-session",
        "transcript_path": "/test/transcript.jsonl",
        "cwd": "/test",
        "hook_event_name": "SubagentStart",
        "agent_id": "agent-123",
        # agent_type intentionally missing
    }

    @contextmanager
    def mock_propagate(**kwargs):
        yield

    with patch("langfuse_subagent_start_hook.read_hook_input", return_value=hook_input), \
         patch("langfuse_subagent_start_hook.is_tracing_enabled", return_value=True), \
         patch("langfuse_subagent_start_hook.create_langfuse_client", return_value=mock_lf), \
         patch("langfuse_subagent_start_hook.propagate_session_attributes", mock_propagate), \
         patch("langfuse_subagent_start_hook.load_state", return_value={}), \
         patch("langfuse_subagent_start_hook.save_state"), \
         pytest.raises(SystemExit) as exc_info:
        main()

    # Should exit 0 (success with fallback), not exit 1 (hard failure)
    assert exc_info.value.code == 0
    # Should have called start_as_current_observation with "unknown" as agent_type
    call_kwargs = mock_lf.start_as_current_observation.call_args
    assert "unknown" in call_kwargs.kwargs["name"]


def test_subagent_start_missing_agent_id_uses_fallback():
    """Subagent start hook uses 'unknown-agent' fallback when agent_id is missing."""
    from langfuse_subagent_start_hook import main

    mock_lf = MagicMock()
    mock_lf.start_as_current_observation.return_value.__enter__ = MagicMock(return_value=MagicMock())
    mock_lf.start_as_current_observation.return_value.__exit__ = MagicMock(return_value=False)

    hook_input = {
        "session_id": "test-session",
        "transcript_path": "/test/transcript.jsonl",
        "cwd": "/test",
        "hook_event_name": "SubagentStart",
        "agent_type": "Explore",
        # agent_id intentionally missing
    }

    @contextmanager
    def mock_propagate(**kwargs):
        yield

    with patch("langfuse_subagent_start_hook.read_hook_input", return_value=hook_input), \
         patch("langfuse_subagent_start_hook.is_tracing_enabled", return_value=True), \
         patch("langfuse_subagent_start_hook.create_langfuse_client", return_value=mock_lf), \
         patch("langfuse_subagent_start_hook.propagate_session_attributes", mock_propagate), \
         patch("langfuse_subagent_start_hook.load_state", return_value={}), \
         patch("langfuse_subagent_start_hook.save_state"), \
         pytest.raises(SystemExit) as exc_info:
        main()

    # Should exit 0 (success with fallback), not exit 1 (hard failure)
    assert exc_info.value.code == 0
    # Should have called start_as_current_observation with the input containing "unknown-agent"
    call_kwargs = mock_lf.start_as_current_observation.call_args
    assert call_kwargs.kwargs["input"]["agent_id"] == "unknown-agent"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_v4_migration.py::test_subagent_start_missing_agent_type_uses_fallback tests/test_v4_migration.py::test_subagent_start_missing_agent_id_uses_fallback -v`

Expected: FAIL — hooks call `sys.exit(1)` on missing fields

- [ ] **Step 3: Soften validation in subagent start hook**

In `src/langfuse/langfuse_subagent_start_hook.py`, replace lines 37-44:

```python
    # Validate required fields for subagent tracking
    if not agent_id:
        log("ERROR", "No agent_id provided in hook input")
        sys.exit(1)

    if not agent_type:
        log("ERROR", "No agent_type provided in hook input")
        sys.exit(1)
```

With:

```python
    # Use fallback defaults for missing subagent fields
    if not agent_id:
        log("WARNING", "No agent_id provided in hook input, using fallback")
        agent_id = "unknown-agent"

    if not agent_type:
        log("WARNING", "No agent_type provided in hook input, using fallback")
        agent_type = "unknown"
```

- [ ] **Step 4: Replace `start_as_current_span` with `start_as_current_observation` at line 56**

In `src/langfuse/langfuse_subagent_start_hook.py` line 56, replace:

```python
                    with langfuse.start_as_current_span(
```

With:

```python
                    with langfuse.start_as_current_observation(
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_v4_migration.py -v`

Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add src/langfuse/langfuse_subagent_start_hook.py tests/test_v4_migration.py
git commit -m "feat: migrate subagent start hook to v4 API and soften validation"
```

---

### Task 7: Migrate subagent stop hook — swap API + remove `timeout` + soften validation

**Files:**
- Modify: `src/langfuse/langfuse_subagent_stop_hook.py:41-47,154,171`

- [ ] **Step 1: Soften validation**

In `src/langfuse/langfuse_subagent_stop_hook.py`, replace lines 40-47:

```python
    # Validate agent_type and agent_id (high priority fix)
    if not agent_type or not isinstance(agent_type, str) or agent_type.strip() == "":
        log("ERROR", "Invalid or missing agent_type in hook input")
        sys.exit(1)

    if not agent_id or not isinstance(agent_id, str) or agent_id.strip() == "":
        log("ERROR", "Invalid or missing agent_id in hook input")
        sys.exit(1)
```

With:

```python
    # Use fallback defaults for missing subagent fields
    if not agent_type or not isinstance(agent_type, str) or agent_type.strip() == "":
        log("WARNING", "Invalid or missing agent_type in hook input, using fallback")
        agent_type = "unknown"

    if not agent_id or not isinstance(agent_id, str) or agent_id.strip() == "":
        log("WARNING", "Invalid or missing agent_id in hook input, using fallback")
        agent_id = "unknown-agent"
```

- [ ] **Step 2: Replace `start_as_current_span` with `start_as_current_observation` at line 154**

In `src/langfuse/langfuse_subagent_stop_hook.py` line 154, replace:

```python
                with langfuse.start_as_current_span(
```

With:

```python
                with langfuse.start_as_current_observation(
```

- [ ] **Step 3: Remove `timeout` from `flush()` at line 171**

In `src/langfuse/langfuse_subagent_stop_hook.py` line 171, replace:

```python
            langfuse.flush(timeout=10)
```

With:

```python
            langfuse.flush()
```

- [ ] **Step 4: Run all tests**

Run: `uv run pytest -v`

Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add src/langfuse/langfuse_subagent_stop_hook.py
git commit -m "feat: migrate subagent stop hook to v4 API, remove flush timeout, soften validation"
```

---

### Task 8: Pin Langfuse version and run full test suite

**Files:**
- Modify: `pyproject.toml:7`

- [ ] **Step 1: Update version pin**

In `pyproject.toml` line 7, replace:

```toml
    "langfuse>=3.14.1",
```

With:

```toml
    "langfuse>=4.0,<5.0",
```

- [ ] **Step 2: Sync dependencies**

Run: `uv sync`

Expected: Resolves and installs langfuse 4.x

- [ ] **Step 3: Run full test suite**

Run: `uv run pytest -v`

Expected: All tests pass (existing + new migration tests)

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: pin langfuse>=4.0,<5.0 to prevent future silent breakage"
```
