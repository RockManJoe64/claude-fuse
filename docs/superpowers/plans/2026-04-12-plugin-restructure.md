# Plugin Restructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure claude-fuse from a manual `settings.json` setup to a distributable Claude Code plugin with marketplace support.

**Architecture:** Move all Python hook scripts and shared modules from `src/langfuse/` to `hooks/` at the repo root. Add `.claude-plugin/plugin.json` manifest and `hooks/hooks.json` configuration. Add PEP 723 inline script metadata to each hook script so `uv run` resolves dependencies without a project install. Keep `settings.example.json` as a manual install fallback.

**Tech Stack:** Python 3.11+ (end user), Python 3.13 (dev), uv, langfuse v4, pytest

**Branch:** All commits go on `feature/plugin-restructure` (not `develop`).

---

## File Map

### New files

| File | Purpose |
|---|---|
| `.claude-plugin/plugin.json` | Plugin manifest (name, version, description, author) |
| `.claude-plugin/marketplace.json` | Single-plugin marketplace catalog |
| `hooks/hooks.json` | Event → command configuration with `${CLAUDE_PLUGIN_ROOT}` paths |
| `hooks/check_uv.sh` | SessionStart prerequisite guard — exits non-zero if `uv` missing |

### Moved files (git mv)

| From | To |
|---|---|
| `src/langfuse/common.py` | `hooks/common.py` |
| `src/langfuse/transcript.py` | `hooks/transcript.py` |
| `src/langfuse/langfuse_session_start_hook.py` | `hooks/langfuse_session_start_hook.py` |
| `src/langfuse/langfuse_session_end_hook.py` | `hooks/langfuse_session_end_hook.py` |
| `src/langfuse/langfuse_stop_hook.py` | `hooks/langfuse_stop_hook.py` |
| `src/langfuse/langfuse_subagent_start_hook.py` | `hooks/langfuse_subagent_start_hook.py` |
| `src/langfuse/langfuse_subagent_stop_hook.py` | `hooks/langfuse_subagent_stop_hook.py` |

### Deleted files

| File | Reason |
|---|---|
| `src/langfuse/__init__.py` | Not needed — hooks are standalone scripts, not a package |
| `src/langfuse/__pycache__/` | Build artifact |
| `src/` directory | Empty after moves |

### Modified files

| File | Change |
|---|---|
| `hooks/langfuse_session_start_hook.py` | Remove `sys.path.insert` hack, remove `from pathlib import Path`, add PEP 723 header |
| `hooks/langfuse_session_end_hook.py` | Remove `sys.path.insert` hack, remove `from pathlib import Path`, add PEP 723 header |
| `hooks/langfuse_stop_hook.py` | Remove `sys.path.insert` hack (keep `Path` — used for transcript file), add PEP 723 header |
| `hooks/langfuse_subagent_start_hook.py` | Remove `sys.path.insert` hack, remove `from pathlib import Path`, add PEP 723 header |
| `hooks/langfuse_subagent_stop_hook.py` | Remove `sys.path.insert` hack (keep `Path` — used for transcript file), add PEP 723 header |
| `tests/test_user_id.py` | Update `sys.path.insert` target from `src/langfuse` to `hooks` |
| `tests/test_v4_migration.py` | Update `sys.path.insert` target from `src/langfuse` to `hooks` |
| `settings.example.json` | Update hook command paths from `src/langfuse/` to `hooks/` |
| `CLAUDE.md` | Update paths from `src/langfuse/` to `hooks/`, update Architecture and Tests sections |
| `README.md` | Restructure: plugin install as primary, manual as "Advanced" section |

---

### Task 1: Create plugin metadata files

**Files:**
- Create: `.claude-plugin/plugin.json`
- Create: `.claude-plugin/marketplace.json`

- [ ] **Step 1: Create `.claude-plugin/plugin.json`**

```json
{
  "name": "claude-fuse",
  "version": "0.1.0",
  "description": "Claude Code hooks for measuring telemetry and usage with Langfuse",
  "author": "RockManJoe64"
}
```

- [ ] **Step 2: Create `.claude-plugin/marketplace.json`**

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

- [ ] **Step 3: Commit**

```bash
git add .claude-plugin/plugin.json .claude-plugin/marketplace.json
git commit -m "feat: add plugin manifest and marketplace catalog"
```

---

### Task 2: Create hook configuration and prerequisite guard

**Files:**
- Create: `hooks/hooks.json`
- Create: `hooks/check_uv.sh`

- [ ] **Step 1: Create `hooks/hooks.json`**

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

- [ ] **Step 2: Create `hooks/check_uv.sh`**

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

- [ ] **Step 3: Make `check_uv.sh` executable**

```bash
chmod +x hooks/check_uv.sh
```

- [ ] **Step 4: Commit**

```bash
git add hooks/hooks.json hooks/check_uv.sh
git commit -m "feat: add hook configuration and uv prerequisite guard"
```

---

### Task 3: Move Python files from `src/langfuse/` to `hooks/`

**Files:**
- Move: all 7 Python files from `src/langfuse/` to `hooks/`
- Delete: `src/langfuse/__init__.py`, `src/langfuse/__pycache__/`, `src/` directory

- [ ] **Step 1: Move all Python source files with git mv**

```bash
git mv src/langfuse/common.py hooks/common.py
git mv src/langfuse/transcript.py hooks/transcript.py
git mv src/langfuse/langfuse_session_start_hook.py hooks/langfuse_session_start_hook.py
git mv src/langfuse/langfuse_session_end_hook.py hooks/langfuse_session_end_hook.py
git mv src/langfuse/langfuse_stop_hook.py hooks/langfuse_stop_hook.py
git mv src/langfuse/langfuse_subagent_start_hook.py hooks/langfuse_subagent_start_hook.py
git mv src/langfuse/langfuse_subagent_stop_hook.py hooks/langfuse_subagent_stop_hook.py
```

- [ ] **Step 2: Remove leftover files and directories**

```bash
git rm src/langfuse/__init__.py
rm -rf src/langfuse/__pycache__
rmdir src/langfuse
rmdir src
```

- [ ] **Step 3: Commit the move**

```bash
git add -A
git commit -m "refactor: move hook scripts from src/langfuse/ to hooks/"
```

---

### Task 4: Add PEP 723 headers and clean up imports in hook scripts

**Files:**
- Modify: `hooks/langfuse_session_start_hook.py`
- Modify: `hooks/langfuse_session_end_hook.py`
- Modify: `hooks/langfuse_stop_hook.py`
- Modify: `hooks/langfuse_subagent_start_hook.py`
- Modify: `hooks/langfuse_subagent_stop_hook.py`

For each hook script, make two changes:
1. Add a PEP 723 inline script metadata block after the shebang
2. Remove the `sys.path.insert(0, ...)` line
3. Remove `from pathlib import Path` if it was only used for the `sys.path.insert` hack

The PEP 723 headers must be identical across scripts (except `langfuse_session_start_hook.py` which also needs `requests`) to maximize `uv` cache hits.

- [ ] **Step 1: Edit `hooks/langfuse_session_start_hook.py`**

Add PEP 723 header after the shebang line. Remove the `sys.path.insert` line. Remove `from pathlib import Path` (only used for the path hack).

Replace the top of the file (lines 1-12):

```python
#!/usr/bin/env python3
"""Tracks session start events in Langfuse."""

import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import socket
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
```

With:

```python
#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "langfuse>=4.0,<5.0",
#   "requests",
# ]
# ///
"""Tracks session start events in Langfuse."""

import sys
import traceback
from datetime import datetime, timezone
from typing import Optional
import socket
import requests
```

- [ ] **Step 2: Edit `hooks/langfuse_session_end_hook.py`**

Replace the top of the file (lines 1-9):

```python
#!/usr/bin/env python3
"""Tracks session end events in Langfuse."""

import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
```

With:

```python
#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "langfuse>=4.0,<5.0",
# ]
# ///
"""Tracks session end events in Langfuse."""

import sys
import traceback
from datetime import datetime, timezone
```

- [ ] **Step 3: Edit `hooks/langfuse_stop_hook.py`**

This script uses `Path` for transcript file handling (not just the path hack), so keep `from pathlib import Path`.

Replace the top of the file (lines 1-12):

```python
#!/usr/bin/env python3
"""
Sends Claude Code traces to Langfuse after each response.
"""

import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
```

With:

```python
#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "langfuse>=4.0,<5.0",
# ]
# ///
"""
Sends Claude Code traces to Langfuse after each response.
"""

import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
```

- [ ] **Step 4: Edit `hooks/langfuse_subagent_start_hook.py`**

Replace the top of the file (lines 1-8):

```python
#!/usr/bin/env python3
"""Tracks subagent start events in Langfuse."""

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
```

With:

```python
#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "langfuse>=4.0,<5.0",
# ]
# ///
"""Tracks subagent start events in Langfuse."""

import sys
from datetime import datetime, timezone
```

- [ ] **Step 5: Edit `hooks/langfuse_subagent_stop_hook.py`**

This script uses `Path` for transcript file handling, so keep `from pathlib import Path`.

Replace the top of the file (lines 1-10):

```python
#!/usr/bin/env python3
"""Tracks subagent stop events in Langfuse."""

import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
```

With:

```python
#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "langfuse>=4.0,<5.0",
# ]
# ///
"""Tracks subagent stop events in Langfuse."""

import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
```

- [ ] **Step 6: Verify all hook scripts have consistent PEP 723 headers**

```bash
grep -A5 "# /// script" hooks/langfuse_*.py
```

Expected: all 5 scripts show `requires-python = ">=3.11"` and `langfuse>=4.0,<5.0`. Only `langfuse_session_start_hook.py` additionally lists `requests`.

- [ ] **Step 7: Commit**

```bash
git add hooks/langfuse_session_start_hook.py hooks/langfuse_session_end_hook.py hooks/langfuse_stop_hook.py hooks/langfuse_subagent_start_hook.py hooks/langfuse_subagent_stop_hook.py
git commit -m "feat: add PEP 723 inline script metadata and remove sys.path hacks"
```

---

### Task 5: Update test imports and verify tests pass

**Files:**
- Modify: `tests/test_user_id.py`
- Modify: `tests/test_v4_migration.py`

- [ ] **Step 1: Edit `tests/test_user_id.py` line 7**

Replace:

```python
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src" / "langfuse"))
```

With:

```python
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hooks"))
```

- [ ] **Step 2: Edit `tests/test_v4_migration.py` line 7**

Replace:

```python
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src" / "langfuse"))
```

With:

```python
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hooks"))
```

- [ ] **Step 3: Run tests to verify they pass**

```bash
uv run pytest tests/ -v
```

Expected: all tests pass. If any fail, the issue is likely an import path problem — check that `hooks/common.py` and `hooks/transcript.py` exist and the `sys.path.insert` points to the right directory.

- [ ] **Step 4: Commit**

```bash
git add tests/test_user_id.py tests/test_v4_migration.py
git commit -m "test: update test imports from src/langfuse to hooks"
```

---

### Task 6: Update `settings.example.json`

**Files:**
- Modify: `settings.example.json`

- [ ] **Step 1: Update all hook command paths**

Replace every occurrence of `uv run src/langfuse/` with `uv run hooks/` in `settings.example.json`. The five commands to update:

| Old | New |
|---|---|
| `uv run src/langfuse/langfuse_session_start_hook.py` | `uv run hooks/langfuse_session_start_hook.py` |
| `uv run src/langfuse/langfuse_stop_hook.py` | `uv run hooks/langfuse_stop_hook.py` |
| `uv run src/langfuse/langfuse_subagent_start_hook.py` | `uv run hooks/langfuse_subagent_start_hook.py` |
| `uv run src/langfuse/langfuse_subagent_stop_hook.py` | `uv run hooks/langfuse_subagent_stop_hook.py` |
| `uv run src/langfuse/langfuse_session_end_hook.py` | `uv run hooks/langfuse_session_end_hook.py` |

- [ ] **Step 2: Commit**

```bash
git add settings.example.json
git commit -m "docs: update settings.example.json paths from src/langfuse to hooks"
```

---

### Task 7: Update `CLAUDE.md`

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update the Architecture section**

Replace `**Hook scripts** (\`src/langfuse/\`):` with `**Hook scripts** (\`hooks/\`):`.

- [ ] **Step 2: Update the shared modules description**

In the `common.py` bullet, replace `(no package, scripts run directly with \`uv run\`)` with `(scripts are standalone, run directly with \`uv run\`)`.

- [ ] **Step 3: Update the Tests section**

Replace:

```
Tests are in `tests/` and use `pytest` with `unittest.mock`. Test files add `src/langfuse/` to `sys.path` directly — there is no package install. Tests patch `langfuse.propagate_attributes` and `subprocess.run` to avoid real network/git calls.
```

With:

```
Tests are in `tests/` and use `pytest` with `unittest.mock`. Test files add `hooks/` to `sys.path` directly — there is no package install. Tests patch `langfuse.propagate_attributes` and `subprocess.run` to avoid real network/git calls.
```

- [ ] **Step 4: Update the Key Configuration section**

Replace:

```
Hook commands are registered in `.claude/settings.json` or `.claude/settings.local.json` (see `settings.example.json`).
```

With:

```
For plugin users, hooks are configured automatically via `hooks/hooks.json`. For manual setup, hook commands are registered in `.claude/settings.json` or `.claude/settings.local.json` (see `settings.example.json`).
```

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md paths from src/langfuse to hooks"
```

---

### Task 8: Update `README.md`

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update all file path references**

Replace all occurrences of `src/langfuse/` with `hooks/` throughout the README. This affects the hook descriptions (e.g., `**File**: \`src/langfuse/langfuse_session_start_hook.py\`` becomes `**File**: \`hooks/langfuse_session_start_hook.py\``).

- [ ] **Step 2: Replace the Setup and Configuration / Prerequisites section**

Replace the current Prerequisites section with:

```markdown
### Prerequisites

- [uv](https://github.com/astral-sh/uv) package manager (required)
  - Unix: `curl -LsSf https://astral.sh/uv/install.sh | sh`
  - Windows: `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`
- A [Langfuse](https://langfuse.com/) account (free tier available)
- Claude Code CLI

> **Note:** Hooks only run in **trusted workspaces**. If hooks appear to be silently ignored, check your workspace trust settings.
```

- [ ] **Step 3: Replace the Installation section**

Replace everything from `### Installation` through `Option 2: Global Installation` with:

```markdown
### Installation

#### Plugin Install (Recommended)

Install claude-fuse as a Claude Code plugin — no manual configuration needed:

1. Add the marketplace:
   ```
   /plugin marketplace add RockManJoe64/claude-fuse
   ```

2. Install the plugin:
   ```
   /plugin install claude-fuse@RockManJoe64/claude-fuse
   ```

3. Set your Langfuse environment variables. You can place these in your shell profile, `.claude/settings.local.json`, direnv, or wherever you manage env vars:
   ```
   LANGFUSE_PUBLIC_KEY=pk-lf-...
   LANGFUSE_SECRET_KEY=sk-lf-...
   LANGFUSE_HOST=https://cloud.langfuse.com
   ```

4. Start a new Claude Code session — hooks will activate automatically.

#### Advanced: Manual Setup

If you prefer to wire hooks manually (e.g., for customization or debugging):

1. Clone this repository:
   ```bash
   git clone https://github.com/RockManJoe64/claude-fuse.git
   cd claude-fuse
   ```

2. Install dev dependencies:
   ```bash
   uv sync
   ```

3. Copy the example settings file to your project or user config:
   ```bash
   cp settings.example.json /path/to/your/project/.claude/settings.local.json
   ```

4. Edit the copied file and replace the placeholder API keys with your actual Langfuse credentials.
```

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: restructure README with plugin install as primary path"
```

---

### Task 9: Update `.claude/settings.local.json` for local development

**Files:**
- Modify: `.claude/settings.local.json`

The local development settings file needs its hook command paths updated so hooks continue to work during development.

- [ ] **Step 1: Update all hook command paths**

Replace every occurrence of `uv run src/langfuse/` with `uv run hooks/` in `.claude/settings.local.json`. The five commands:

| Old | New |
|---|---|
| `uv run src/langfuse/langfuse_session_start_hook.py` | `uv run hooks/langfuse_session_start_hook.py` |
| `uv run src/langfuse/langfuse_stop_hook.py` | `uv run hooks/langfuse_stop_hook.py` |
| `uv run src/langfuse/langfuse_subagent_start_hook.py` | `uv run hooks/langfuse_subagent_start_hook.py` |
| `uv run src/langfuse/langfuse_subagent_stop_hook.py` | `uv run hooks/langfuse_subagent_stop_hook.py` |
| `uv run src/langfuse/langfuse_session_end_hook.py` | `uv run hooks/langfuse_session_end_hook.py` |

- [ ] **Step 2: Do NOT commit** — `settings.local.json` contains secrets and is gitignored. Just update it locally.

---

### Task 10: Final verification

- [ ] **Step 1: Run the full test suite**

```bash
uv run pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 2: Verify the directory structure matches the spec**

```bash
ls -la .claude-plugin/
ls -la hooks/
ls tests/
```

Expected:
- `.claude-plugin/` contains `plugin.json` and `marketplace.json`
- `hooks/` contains `hooks.json`, `check_uv.sh`, `common.py`, `transcript.py`, and all 5 hook scripts
- `src/` directory no longer exists
- `tests/` still contains `test_user_id.py` and `test_v4_migration.py`

- [ ] **Step 3: Verify no dangling references to `src/langfuse/`**

```bash
grep -r "src/langfuse" --include="*.py" --include="*.json" --include="*.md" .
```

Expected: no matches (or only matches in `docs/superpowers/` design/plan files, which are historical).

- [ ] **Step 4: Review the commit log**

```bash
git log --oneline feature/plugin-restructure --not develop
```

Expected: a clean sequence of commits matching the tasks above.
