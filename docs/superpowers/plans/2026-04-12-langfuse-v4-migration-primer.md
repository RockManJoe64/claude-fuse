# Langfuse v4 Migration — Session Primer

## Problem

All five Langfuse lifecycle hooks (SessionStart, SessionEnd, Stop, SubagentStart, SubagentStop) have been silently broken since ~2026-02-15. No tracing data reaches Langfuse. The cause: the Langfuse Python SDK upgraded from v3 to v4, introducing breaking API changes. The hooks were written against v3 and the project had no version pin, so `uv run` resolved v4 automatically and the hooks started failing.

Three root causes:
1. `start_as_current_span()` was removed in v4 — renamed to `start_as_current_observation()`. Every hook that creates a span fails with `AttributeError`.
2. `flush()` and `shutdown()` no longer accept a `timeout` keyword argument. The stop hook and subagent stop hook pass `timeout=30` / `timeout=10`, causing `TypeError`.
3. The subagent hooks hard-fail (`sys.exit(1)`) when `agent_type` or `agent_id` is missing from hook input, which is brittle and kills all subagent tracing on any edge case.

## Intent

Restore Langfuse tracing by migrating all hooks to the v4 API, hardening validation, and pinning the SDK version to prevent future silent breakage.

## Summary of Changes

1. **API migration** — Replace `langfuse.start_as_current_span(...)` with `langfuse.start_as_current_observation(...)` at 6 call sites across 5 files. Parameters are identical; this is a method rename only. (`transcript.py:294` already uses the v4 API for generations — no change needed there.)

2. **Remove `timeout` kwargs** — Drop `timeout=30` from `flush()` and `shutdown()` in `langfuse_stop_hook.py`, and `timeout=10` from `flush()` in `langfuse_subagent_stop_hook.py`. Three call sites total.

3. **Soften subagent validation** — Replace `sys.exit(1)` with log warning + fallback defaults (`"unknown"` for `agent_type`, `"unknown-agent"` for `agent_id`) in both `langfuse_subagent_start_hook.py` and `langfuse_subagent_stop_hook.py`. The `session_id` check stays as a hard failure.

4. **Metadata string coercion** — Add a `sanitize_metadata()` helper to `common.py` that coerces all values to `str` and truncates to 200 chars (v4 requires `dict[str, str]`). Wire it into `build_metadata()` in `transcript.py`.

5. **Version pin** — Change `pyproject.toml` from `langfuse>=3.14.1` to `langfuse>=4.0,<5.0`.

6. **Tests** — New `tests/test_v4_migration.py` with 7 tests covering: `sanitize_metadata` behavior, session start hook calling the v4 API, stop hook calling `flush()`/`shutdown()` without arguments, and subagent start hook using fallback defaults.

## References

- Design spec: `docs/superpowers/specs/2026-04-12-langfuse-v4-migration-design.md`
- Implementation plan: `docs/superpowers/plans/2026-04-12-langfuse-v4-migration.md`
- Root cause analysis: `docs/superpowers/specs/2026-04-12-langfuse-v4-api-breakage.md`
