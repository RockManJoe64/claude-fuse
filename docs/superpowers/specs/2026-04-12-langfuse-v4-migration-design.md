# Langfuse v4 SDK Migration — Design Spec

**Date:** 2026-04-12
**Status:** Approved
**Approach:** B — Full migration (API + robustness fixes + tests)
**RCA:** [2026-04-12-langfuse-v4-api-breakage.md](2026-04-12-langfuse-v4-api-breakage.md)
**Migration guide:** [Langfuse Python v3 → v4](https://langfuse.com/docs/sdk/python/upgrade-v3-to-v4)

---

## Goal

Restore Langfuse tracing for all five Claude Code lifecycle hooks by migrating from the removed v3 API to the v4 API, hardening validation, and pinning the SDK version range to prevent future silent breakage.

---

## 1. API Migration: `start_as_current_span` → `start_as_current_observation`

In Langfuse v4, `start_span()` / `start_as_current_span()` were replaced by the unified `start_observation()` / `start_as_current_observation()` API. The `as_type` parameter defaults to `"span"`, so no extra argument is needed for span-type observations.

### Call sites to update

| File | Line | Context |
|---|---|---|
| `langfuse_session_start_hook.py` | 76 | Session Start span |
| `langfuse_session_end_hook.py` | 76 | Session End span |
| `langfuse_subagent_start_hook.py` | 56 | Subagent Start span |
| `langfuse_subagent_stop_hook.py` | 154 | Subagent Stop span |
| `transcript.py` | 284 | Turn trace span |
| `transcript.py` | 320 | Tool spans |

**No change needed:** `transcript.py:294` already uses `start_as_current_observation(as_type="generation")`.

### Replacement pattern

```python
# Before (v3)
with langfuse.start_as_current_span(name="X", input={...}, metadata={...}) as span:

# After (v4)
with langfuse.start_as_current_observation(name="X", input={...}, metadata={...}) as span:
```

Parameters are identical — this is a method rename only.

---

## 2. Remove `timeout` kwargs from `flush()` and `shutdown()`

In v4, both `Langfuse.flush()` and `Langfuse.shutdown()` accept only `self`.

### Call sites to update

| File | Line | Current | Fix |
|---|---|---|---|
| `langfuse_stop_hook.py` | 191 | `langfuse.flush(timeout=30)` | `langfuse.flush()` |
| `langfuse_stop_hook.py` | 199 | `langfuse.shutdown(timeout=30)` | `langfuse.shutdown()` |
| `langfuse_subagent_stop_hook.py` | 171 | `langfuse.flush(timeout=10)` | `langfuse.flush()` |

All other `flush()`/`shutdown()` calls already use no arguments.

---

## 3. Soften `agent_type`/`agent_id` validation

The Claude Code docs confirm both fields are always present for `SubagentStart`/`SubagentStop` events, but hard-failing with `sys.exit(1)` is brittle. An edge case or schema change would silently kill all subagent tracing.

### Change

Replace `sys.exit(1)` with log warning + fallback default:

| File | Field | Fallback |
|---|---|---|
| `langfuse_subagent_start_hook.py` | `agent_id` | `"unknown-agent"` |
| `langfuse_subagent_start_hook.py` | `agent_type` | `"unknown"` |
| `langfuse_subagent_stop_hook.py` | `agent_type` | `"unknown"` |
| `langfuse_subagent_stop_hook.py` | `agent_id` | `"unknown-agent"` |

The `session_id` check remains a hard failure — without it there's nothing meaningful to trace.

---

## 4. Metadata string coercion

Langfuse v4 requires metadata to be `dict[str, str]` with values ≤200 characters. Non-string values are coerced by the SDK with a warning. We proactively convert to avoid noisy warnings.

### New helper in `common.py`

```python
def sanitize_metadata(meta: dict) -> dict[str, str]:
    """Coerce metadata values to str for Langfuse v4 compatibility."""
    return {str(k): str(v)[:200] for k, v in meta.items()}
```

### Call sites

- `transcript.py:269` — update `build_metadata()` helper to apply `sanitize_metadata` as a final step; this covers all metadata in `create_trace` including `turn_number` (int at line 287) and `tool_count` (int at line 300)
- Hook files pass only string metadata values today (e.g. `"total_turns": str(turn_count)` in `langfuse_session_end_hook.py:83`), so no changes needed there — but `sanitize_metadata` is available if future metadata includes non-string values

---

## 5. Test coverage

New file: `tests/test_v4_migration.py`

| Test | What it verifies |
|---|---|
| `test_sanitize_metadata_coerces_values_to_str` | int/float/bool values become strings |
| `test_sanitize_metadata_truncates_long_values` | values >200 chars are truncated |
| `test_sanitize_metadata_handles_empty_dict` | empty dict edge case |
| `test_session_start_calls_start_as_current_observation` | mocks Langfuse, asserts `start_as_current_observation` is called |
| `test_stop_hook_flush_no_timeout_arg` | asserts `flush()` called with no arguments |
| `test_subagent_start_missing_agent_type_uses_fallback` | hook doesn't exit, uses `"unknown"` |
| `test_subagent_start_missing_agent_id_uses_fallback` | hook doesn't exit, uses `"unknown-agent"` |

Testing approach: `unittest.mock` patches, no real Langfuse/network calls, `sys.path` manipulation to import from `src/langfuse/` (matches existing pattern in `test_user_id.py`).

---

## 6. Version pin in `pyproject.toml`

```toml
# Before
dependencies = ["langfuse>=3.14.1"]

# After
dependencies = ["langfuse>=4.0,<5.0"]
```

Prevents future silent breakage from major version upgrades.

---

## Files changed

| File | Changes |
|---|---|
| `pyproject.toml` | Version pin `langfuse>=4.0,<5.0` |
| `src/langfuse/common.py` | Add `sanitize_metadata()` helper |
| `src/langfuse/langfuse_session_start_hook.py` | `start_as_current_span` → `start_as_current_observation` |
| `src/langfuse/langfuse_session_end_hook.py` | `start_as_current_span` → `start_as_current_observation` |
| `src/langfuse/langfuse_stop_hook.py` | Remove `timeout` from `flush()`/`shutdown()` |
| `src/langfuse/langfuse_subagent_start_hook.py` | `start_as_current_span` → `start_as_current_observation`, soften validation |
| `src/langfuse/langfuse_subagent_stop_hook.py` | `start_as_current_span` → `start_as_current_observation`, remove `flush(timeout=...)`, soften validation |
| `src/langfuse/transcript.py` | `start_as_current_span` → `start_as_current_observation`, use `sanitize_metadata` |
| `tests/test_v4_migration.py` | New — 7 tests covering migration changes |

---

## Out of scope

- Structural refactoring (extracting shared flush/shutdown helper, reducing error-handling boilerplate) — follow-up work
- OpenTelemetry span filtering configuration — not used by these hooks
- `update_current_trace` / `update_trace` migration — not used by these hooks
- Public API namespace remapping (`api.*`) — not used by these hooks
