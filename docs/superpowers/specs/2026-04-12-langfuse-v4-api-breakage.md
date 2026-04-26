# Langfuse v4 API Breakage — Root Cause Analysis

**Date:** 2026-04-12
**Status:** Open
**Symptom:** `SessionStart:resume hook error — Failed with non-blocking status code: Traceback (most recent call last):`

---

## Summary

All five Langfuse lifecycle hooks (SessionStart, Stop, SubagentStart, SubagentStop, SessionEnd) are failing due to breaking API changes in Langfuse Python SDK v4.x. The hooks were written against the v2/v3 API. The errors are non-blocking (sessions still start), but no tracing data is reaching Langfuse.

---

## Environment

- **OS:** Windows 11 Home 10.0.26200
- **uv:** 0.10.9
- **Langfuse SDK resolved by uv:** 4.2.0
- **Hook runner:** `uv run ~/.claude/hooks/langfuse/<script>.py`
- **No `pyproject.toml`** — hooks directory has no dependency manifest, so `uv run` resolves langfuse from cache at whatever version is available

---

## Root Cause 1: `start_as_current_span` removed in v4.x

**File:** `~/.claude/hooks/langfuse/langfuse_session_start_hook.py`, line 76
**Also affects:** `langfuse_session_end_hook.py`, `langfuse_subagent_start_hook.py`

```python
# Current code (broken)
with langfuse.start_as_current_span(
    name="Session Start",
    input={"source": source, "cwd": cwd},
    ...
) as span:
```

In Langfuse v4.x, `start_as_current_span()` was renamed to `start_as_current_observation()`. Calling the old method raises `AttributeError`, which is caught by the `except Exception` handler in `_create_span_with_timeout()` and logged, but the hook still exits 0 after logging the error — meaning the span is silently never created.

**Reproduction:**
```python
uv run --with langfuse python -c "
from langfuse import Langfuse
l = Langfuse.__new__(Langfuse)
l.start_as_current_span(name='test')
"
# => AttributeError: 'Langfuse' object has no attribute 'start_as_current_span'
```

---

## Root Cause 2: `flush()` and `shutdown()` no longer accept `timeout` kwarg

**File:** `~/.claude/hooks/langfuse/langfuse_stop_hook.py` (and others via internal calls)

In Langfuse v4.x, both `Langfuse.flush()` and `Langfuse.shutdown()` accept only `self` — no `timeout` parameter.

```python
# v4.x signatures
def flush(self): ...
def shutdown(self): ...
```

This produces the recurring log error that has been appearing since 2026-02-15:
```
Failed to flush Langfuse: Langfuse.flush() got an unexpected keyword argument 'timeout'
Failed to shutdown Langfuse gracefully: Langfuse.shutdown() got an unexpected keyword argument 'timeout'
```

**Note:** The session start hook code at line 129 calls `langfuse.flush()` without arguments, so this error may originate from the stop hook or from internal Langfuse client behavior in v4.x.

---

## Root Cause 3: `SubagentStart` hook expects `agent_type` field

**File:** `~/.claude/hooks/langfuse/langfuse_subagent_start_hook.py`

The log shows repeated errors:
```
[ERROR] Invalid or missing agent_type in hook input
```

The hook input schema from Claude Code may not include `agent_type` in all contexts, or the field name may have changed. This affects every subagent spawn.

---

## Impact

- **No tracing data reaches Langfuse** — all hooks fail silently or with logged errors
- **Log file bloat** — `~/.claude/state/langfuse_hook.log` is nearly 1000 lines of repeated errors
- **State file corruption** — intermittent `[Errno 13] Permission denied` and JSON parse errors in the state file, likely from concurrent hook invocations racing on the same file without proper locking on Windows
- **Errors since:** 2026-02-15 (flush/shutdown timeout errors), ongoing

---

## Affected Files

| File | Issue |
|---|---|
| `common.py` | `propagate_session_attributes` uses `propagate_attributes` — still exists in v4.x (OK) |
| `langfuse_session_start_hook.py` | `start_as_current_span` → `start_as_current_observation` |
| `langfuse_session_end_hook.py` | Same `start_as_current_span` issue (presumed) |
| `langfuse_stop_hook.py` | `flush(timeout=...)` and `shutdown(timeout=...)` calls |
| `langfuse_subagent_start_hook.py` | `start_as_current_span` + `agent_type` validation |
| `langfuse_subagent_stop_hook.py` | Same issues as subagent start |

---

## Fix Options

### Option A: Pin Langfuse to last compatible version

Add a `pyproject.toml` to `~/.claude/hooks/langfuse/` (or `~/.claude/hooks/`) that pins `langfuse<3.0`. This is the minimal fix but leaves you on an older SDK.

### Option B: Migrate hooks to Langfuse v4.x API

Update all hooks to use the new API:
1. Replace `start_as_current_span(...)` with `start_as_current_observation(...)` everywhere
2. Remove `timeout` kwargs from `flush()` and `shutdown()` calls
3. Verify `span.update(output=...)` still works on the new observation object
4. Fix `agent_type` validation to handle the actual hook input schema
5. Add a `pyproject.toml` with `langfuse>=4.0` to prevent future silent breakage

### Option C: Both — migrate to v4.x AND pin a range

Migrate the code to v4.x API and pin `langfuse>=4.0,<5.0` in a `pyproject.toml`. This is the most robust approach.

---

## Recommended Fix

**Option C.** The hooks have been silently broken for 2 months. Migrating to v4.x restores functionality, and pinning with a version range prevents the same class of breakage from happening again.
