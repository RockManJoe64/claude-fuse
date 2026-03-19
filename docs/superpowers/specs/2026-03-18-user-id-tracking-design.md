# Design: User ID Tracking in Langfuse Hooks

**Date:** 2026-03-18
**Status:** Approved

## Overview

Add `user_id` tracking to all Langfuse traces emitted by claude-fuse hooks. This enables per-user analytics in the Langfuse Users dashboard — including token usage, trace counts, and cost aggregation by user.

## Goals

- Attach a `user_id` to every Langfuse trace (turns, session start/end, subagent traces)
- Zero required configuration — resolve user identity automatically via a fallback chain
- Allow explicit override via environment variable for multi-user or CI environments

## Non-Goals

- Persisting `user_id` to the state file
- Per-turn user identity changes (user_id is resolved once per hook invocation)
- Authentication or access control

## User ID Resolution

Resolved in priority order, using the first non-empty value:

1. `CC_LANGFUSE_USER_ID` env var
2. `LANGFUSE_USER_ID` env var
3. `git config user.email` (subprocess, 2s timeout)
4. `git config user.name` (subprocess, 2s timeout, fallback if email is empty)
5. `os.getlogin()` with fallback to `os.environ.get('USERNAME') or os.environ.get('USER')`
6. `"unknown"` (always-present final fallback)

Git config lookups use `subprocess.run` with `timeout=2` and `capture_output=True`. Any subprocess error is caught and falls through silently.

`os.getlogin()` can raise `OSError` in environments without a controlling terminal (e.g. CI); this is caught and falls back to environment variables.

## Architecture

### New: `get_user_id()` in `common.py`

A function that implements the resolution chain above and returns a non-empty string.

### New: `propagate_session_attributes(session_id)` in `common.py`

A context manager wrapping Langfuse's `propagate_attributes`, always injecting both `session_id` and `user_id`:

```python
@contextmanager
def propagate_session_attributes(session_id: str):
    user_id = get_user_id()
    from langfuse import propagate_attributes
    with propagate_attributes(session_id=session_id, user_id=user_id):
        yield
```

### Changed: `langfuse_session_start_hook.py`

- Import `propagate_session_attributes` from `common` instead of `propagate_attributes` from `langfuse`
- Replace `propagate_attributes(session_id=session_id)` with `propagate_session_attributes(session_id)`

### Changed: `transcript.py`

- Import `propagate_session_attributes` from `common` instead of `propagate_attributes` from `langfuse`
- Replace `propagate_attributes(session_id=session_id)` with `propagate_session_attributes(session_id)` inside `create_trace`

### Changed: `langfuse_session_end_hook.py`

- Import `propagate_session_attributes` from `common` instead of `propagate_attributes` from `langfuse`
- Replace `propagate_attributes(session_id=session_id)` with `propagate_session_attributes(session_id)`

### Changed: `langfuse_subagent_start_hook.py`

- Import `propagate_session_attributes` from `common` instead of `propagate_attributes` from `langfuse`
- Replace `propagate_attributes(session_id=session_id)` with `propagate_session_attributes(session_id)`

### Changed: `langfuse_subagent_stop_hook.py`

- Import `propagate_session_attributes` from `common` instead of `propagate_attributes` from `langfuse`
- Replace `propagate_attributes(session_id=session_id)` at line 154 with `propagate_session_attributes(session_id)` (this file creates its own lifecycle span in addition to delegating to `create_trace`)

## Configuration

Add to `settings.example.json` `env` block (optional):

```json
"CC_LANGFUSE_USER_ID": "your-username-or-email"
```

Add to README "Environment Variables" section:

- **CC_LANGFUSE_USER_ID** (optional): Explicit user identifier for Langfuse tracking. If not set, falls back to `LANGFUSE_USER_ID`, then git config email/name, then OS username.

## Error Handling

- All fallback steps are wrapped in try/except — no step can crash a hook
- Git subprocess calls use `timeout=2` to avoid blocking
- Final fallback `"unknown"` ensures `user_id` is always a valid string passed to Langfuse

## Files Changed

| File | Change |
|------|--------|
| `src/langfuse/common.py` | Add `get_user_id()` and `propagate_session_attributes()` |
| `src/langfuse/langfuse_session_start_hook.py` | Use `propagate_session_attributes` |
| `src/langfuse/transcript.py` | Use `propagate_session_attributes` |
| `src/langfuse/langfuse_session_end_hook.py` | Use `propagate_session_attributes` |
| `src/langfuse/langfuse_subagent_start_hook.py` | Use `propagate_session_attributes` |
| `src/langfuse/langfuse_subagent_stop_hook.py` | Use `propagate_session_attributes` |
| `settings.example.json` | Add `CC_LANGFUSE_USER_ID` env var (optional) |
| `README.md` | Document `CC_LANGFUSE_USER_ID` and fallback chain |
