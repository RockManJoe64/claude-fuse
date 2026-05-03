# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
uv sync

# Run all tests
uv run pytest

# Run a single test file
uv run pytest tests/test_user_id.py

# Run a single test by name
uv run pytest tests/test_user_id.py::test_cc_langfuse_user_id_takes_precedence
```

There is no build or lint step — this is a pure Python hooks project.

## Architecture

This project provides Claude Code lifecycle hooks that send telemetry to [Langfuse](https://langfuse.com/). Each hook is a standalone Python script invoked by Claude Code via stdin/stdout.

**Hook scripts** (`hooks/`):
- `langfuse_session_start_hook.py` — fires on `SessionStart`, creates a span in Langfuse
- `langfuse_session_end_hook.py` — fires on `SessionEnd`, records duration and turn count
- `langfuse_stop_hook.py` — fires after every Claude turn (`Stop`), parses the transcript and creates per-turn traces
- `langfuse_subagent_start_hook.py` / `langfuse_subagent_stop_hook.py` — fire when Task agents start/stop

**Shared modules**:
- `common.py` — all shared infrastructure: state load/save (`~/.claude/state/claudefuse_state.json`), logging (`~/.claude/state/claudefuse_hooks.log`), stdin JSON parsing, Langfuse client init, message content helpers, `get_user_id()`, and the `propagate_session_attributes()` context manager
- `transcript.py` — transcript parsing (`parse_transcript_into_turns`) and trace creation (`create_trace`); imports from `common` using a relative import (scripts are standalone, run directly with `uv run`)

**Data flow**: Claude Code passes a JSON blob via stdin to each hook (fields: `session_id`, `transcript_path`, `cwd`, `hook_event_name`, plus event-specific fields). The stop hook streams the transcript file, groups messages into turns, and sends each turn as a Langfuse trace with nested generation and tool spans.

**State file**: Hooks share mutable state (processed line counts, subagent info) via `~/.claude/state/claudefuse_state.json` with file locking (platform-specific: `msvcrt` on Windows, `fcntl` on Unix).

## Key Configuration

Hooks only run when `TRACE_TO_LANGFUSE=true` is set. Required env vars: `LANGFUSE_PUBLIC_KEY` (or `CC_LANGFUSE_PUBLIC_KEY`) and `LANGFUSE_SECRET_KEY` (or `CC_LANGFUSE_SECRET_KEY`). Optional: `CC_LANGFUSE_DEBUG=true` enables verbose logging, `CC_LANGFUSE_USER_ID` sets an explicit user identity.

For plugin users, hooks are configured automatically via `hooks/hooks.json`. For manual setup, hook commands are registered in `.claude/settings.json` or `.claude/settings.local.json` (see `settings.example.json`).

## Tests

Tests are in `tests/` and use `pytest` with `unittest.mock`. Test files add `hooks/` to `sys.path` directly — there is no package install. Tests patch `langfuse.propagate_attributes` and `subprocess.run` to avoid real network/git calls.
