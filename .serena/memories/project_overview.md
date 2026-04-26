# claude-fuse — Project Overview

## Purpose
Provides Claude Code lifecycle hooks that send telemetry to [Langfuse](https://langfuse.com/). Each hook is a standalone Python script invoked by Claude Code via stdin/stdout.

## Tech Stack
- Python 3.13 (dev), 3.11+ (end-user target)
- uv (package manager / script runner)
- langfuse>=4.0,<5.0
- pytest>=9.0.2 (dev dependency)

## Current Structure (pre-restructure)
- `src/langfuse/` — all hook scripts and shared modules
  - `common.py` — shared infrastructure (state, logging, Langfuse client, helpers)
  - `transcript.py` — transcript parsing and trace creation
  - `langfuse_session_start_hook.py` — SessionStart event
  - `langfuse_session_end_hook.py` — SessionEnd event
  - `langfuse_stop_hook.py` — Stop event (per-turn traces)
  - `langfuse_subagent_start_hook.py` — SubagentStart event
  - `langfuse_subagent_stop_hook.py` — SubagentStop event
- `tests/` — pytest tests
- `settings.example.json` — manual hook registration example
- `pyproject.toml` — uv project manifest

## In-Progress Restructure (feature/plugin-restructure branch)
Moving all Python files from `src/langfuse/` → `hooks/`, adding `.claude-plugin/` metadata, and adding PEP 723 headers for standalone `uv run` execution. See `docs/superpowers/plans/2026-04-12-plugin-restructure.md`.

## Key Configuration
Hooks only run when `TRACE_TO_LANGFUSE=true` is set. Required: `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY`. Optional: `CC_LANGFUSE_DEBUG=true`, `CC_LANGFUSE_USER_ID`.
