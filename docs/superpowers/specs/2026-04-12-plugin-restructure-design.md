# Plugin Restructure Design

Restructure the claude-fuse repo to align with Claude Code's expected plugin directory layout, enabling distribution via the plugin marketplace.

## Context

claude-fuse provides Claude Code lifecycle hooks that send telemetry to Langfuse. Today, users clone the repo and manually wire hook commands into `.claude/settings.local.json` pointing at `src/langfuse/`. This works but doesn't scale — it requires manual path setup, a local `uv sync`, and copy-pasting configuration.

Claude Code supports a plugin system with a standardized directory layout, a manifest, and marketplace distribution. Restructuring to this format lets users install with two commands and no manual config.

## Decisions

| Aspect | Decision | Rationale |
|---|---|---|
| Layout | Flat `hooks/` at root | Simplest, aligned with plugin conventions |
| Dependencies | PEP 723 inline headers + `uv run --quiet` | Zero install step; `uv` resolves deps from script headers |
| Python version | `>=3.11` for end users, `>=3.13` for dev | 3.11 is oldest actively supported CPython; 3.13 is dev-local |
| Filenames | Keep current names unchanged | Recognizable to existing users |
| Prerequisite guard | `check_uv.sh` (bash only) | Git Bash covers Windows; one file, not two |
| Import cleanup | Remove `sys.path.insert` hacks | `uv run` adds script dir to `sys.path[0]` automatically |
| Backward compat | Plugin primary, manual as "Advanced" | Plugin is the recommended path; manual costs nothing to keep |
| Distribution | Single-plugin marketplace | Can expand later if needed |
| Verification | Test `${CLAUDE_PLUGIN_ROOT}` before full port | Documented feature, but must verify on Windows + Git Bash |

## Directory Layout

After the restructure:

```
claude-fuse/
├── .claude-plugin/
│   ├── plugin.json                        # plugin manifest
│   └── marketplace.json                   # marketplace catalog
├── hooks/
│   ├── hooks.json                         # event → command config
│   ├── check_uv.sh                        # SessionStart prerequisite guard
│   ├── common.py                          # shared infra (state, logging, client)
│   ├── transcript.py                      # transcript parsing + trace creation
│   ├── langfuse_session_start_hook.py     # SessionStart
│   ├── langfuse_session_end_hook.py       # SessionEnd
│   ├── langfuse_stop_hook.py              # Stop
│   ├── langfuse_subagent_start_hook.py    # SubagentStart
│   └── langfuse_subagent_stop_hook.py     # SubagentStop
├── tests/
│   ├── test_user_id.py
│   └── test_v4_migration.py
├── docs/
├── settings.example.json                  # manual install reference (updated paths)
├── pyproject.toml                         # dev-only (pytest, project metadata)
├── CLAUDE.md
└── README.md
```

### What goes away

- `src/langfuse/` — emptied and deleted (everything moved to `hooks/`)
- `src/langfuse/__init__.py` — not needed; these aren't packages
- `src/langfuse/__pycache__/` — build artifact

### What's new

- `.claude-plugin/plugin.json` — plugin manifest
- `.claude-plugin/marketplace.json` — marketplace catalog
- `hooks/hooks.json` — hook event configuration
- `hooks/check_uv.sh` — prerequisite guard

### What moves

- `src/langfuse/common.py` → `hooks/common.py`
- `src/langfuse/transcript.py` → `hooks/transcript.py`
- All 5 hook scripts → `hooks/`

## Plugin Manifest

`.claude-plugin/plugin.json`:

```json
{
  "name": "claude-fuse",
  "version": "0.1.0",
  "description": "Claude Code hooks for measuring telemetry and usage with Langfuse",
  "author": "RockManJoe64"
}
```

Version mirrors `pyproject.toml`. Claude Code uses this to decide whether to update on reinstall.

## Marketplace Catalog

`.claude-plugin/marketplace.json`:

```json
{
  "plugins": [
    {
      "name": "claude-fuse",
      "description": "Claude Code hooks for measuring telemetry and usage with Langfuse",
      "path": "."
    }
  ]
}
```

Single-plugin marketplace. `"path": "."` means the plugin root is the repo root.

## Hook Configuration

`hooks/hooks.json`:

```json
{
  "description": "Langfuse telemetry hooks for Claude Code",
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PLUGIN_ROOT}/hooks/check_uv.sh"
          },
          {
            "type": "command",
            "command": "uv run --quiet ${CLAUDE_PLUGIN_ROOT}/hooks/langfuse_session_start_hook.py"
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "uv run --quiet ${CLAUDE_PLUGIN_ROOT}/hooks/langfuse_stop_hook.py"
          }
        ]
      }
    ],
    "SubagentStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "uv run --quiet ${CLAUDE_PLUGIN_ROOT}/hooks/langfuse_subagent_start_hook.py"
          }
        ]
      }
    ],
    "SubagentStop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "uv run --quiet ${CLAUDE_PLUGIN_ROOT}/hooks/langfuse_subagent_stop_hook.py"
          }
        ]
      }
    ],
    "SessionEnd": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "uv run --quiet ${CLAUDE_PLUGIN_ROOT}/hooks/langfuse_session_end_hook.py"
          }
        ]
      }
    ]
  }
}
```

- `"hooks"` wrapper key is the plugin format (user `settings.json` omits it)
- `check_uv.sh` runs first in `SessionStart`; non-zero exit surfaces a clear error
- `--quiet` suppresses `uv`'s dependency resolution output
- No `matcher` fields — hooks fire on every event of their type

## PEP 723 Inline Script Metadata

Each hook script gets a PEP 723 header declaring its dependencies:

```python
#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "langfuse>=4.0,<5.0",
# ]
# ///
```

- `requires-python = ">=3.11"` — oldest actively supported CPython; langfuse v4 supports `>=3.10`
- `langfuse>=4.0,<5.0` — identical across all scripts to maximize `uv` cache hits
- Additional dependencies (e.g., `requests`) added per-script as needed
- `common.py` and `transcript.py` do not get PEP 723 headers — they're imported, not run directly

## Prerequisite Guard

`hooks/check_uv.sh`:

```bash
#!/usr/bin/env bash
# Verify that uv is installed before running Langfuse hooks.

if ! command -v uv &>/dev/null; then
  echo "claude-fuse: 'uv' is required but not found." >&2
  echo "Install it: curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
  echo "Windows:    powershell -c \"irm https://astral.sh/uv/install.ps1 | iex\"" >&2
  exit 1
fi

exit 0
```

- Runs first in `SessionStart` before any Python hooks
- Exits non-zero with install instructions if `uv` is missing
- Exits 0 silently on success
- Works on Unix and Windows Git Bash

## Import Cleanup

Hook scripts currently use a `sys.path.insert` hack to find `common.py`:

```python
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from common import (...)
```

This is removed. When `uv run` executes a script, Python adds the script's directory to `sys.path[0]`. Since `common.py` and `transcript.py` are in the same `hooks/` directory, bare imports work:

```python
from common import (...)
```

## Test Changes

Tests update their `sys.path.insert` target from `src/langfuse` to `hooks`:

```python
# Before
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src" / "langfuse"))

# After
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hooks"))
```

Tests still need the hack because `pytest` runs from the repo root, not from `hooks/`.

## Settings Example (Manual Install)

`settings.example.json` stays in the repo for manual users. Commands update to reflect new paths:

```json
{
  "command": "uv run hooks/langfuse_session_start_hook.py"
}
```

No `${CLAUDE_PLUGIN_ROOT}`, no `--quiet`, no `check_uv.sh` — manual users run from the cloned repo root and presumably already have `uv`.

## `${CLAUDE_PLUGIN_ROOT}` Verification

Before porting all hook logic, verify that `${CLAUDE_PLUGIN_ROOT}` expands correctly in `uv run` command strings:

1. Scaffold a minimal plugin with one hook that prints its resolved path
2. Install locally: `/plugin marketplace add ./path-to-repo` then `/plugin install`
3. Trigger `SessionStart` and confirm the path resolves

**Fallback:** If `${CLAUDE_PLUGIN_ROOT}` does not expand, replace `uv run` commands in `hooks.json` with thin wrapper shell scripts that resolve their own directory:

```bash
#!/usr/bin/env bash
DIR="$(cd "$(dirname "$0")" && pwd)"
exec uv run --quiet "$DIR/langfuse_session_start_hook.py"
```

## End User Install Flow

```bash
# 1. Add the marketplace (one-time)
/plugin marketplace add RockManJoe64/claude-fuse

# 2. Install the plugin
/plugin install claude-fuse@RockManJoe64/claude-fuse

# 3. Set env vars (shell profile, .claude/settings.local.json, direnv, etc.)
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com
```

## CLAUDE.md Updates

Update hook paths from `src/langfuse/` to `hooks/` in the Commands and Architecture sections. No structural changes.

## README.md Updates

- Lead with plugin install as the primary path
- Required env vars section
- Trusted workspace callout
- "Advanced: Manual Setup" section at the bottom with `settings.example.json` approach
