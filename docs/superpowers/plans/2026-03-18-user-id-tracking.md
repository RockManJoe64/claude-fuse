# User ID Tracking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `user_id` to all Langfuse traces by resolving it from env vars, git config, or OS username.

**Architecture:** Add `get_user_id()` (resolution chain) and `propagate_session_attributes()` (context manager wrapper) to `common.py`. Replace all direct `propagate_attributes(session_id=...)` calls across 5 hook files and `transcript.py` with the new wrapper.

**Tech Stack:** Python 3.13, `uv` package manager, `langfuse` SDK, `pytest` for tests, `unittest.mock` for mocking.

**Spec:** `docs/superpowers/specs/2026-03-18-user-id-tracking-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `src/langfuse/common.py` | Modify | Add `get_user_id()` and `propagate_session_attributes()` |
| `tests/test_user_id.py` | Create | Tests for `get_user_id()` and `propagate_session_attributes()` |
| `src/langfuse/langfuse_session_start_hook.py` | Modify | Use `propagate_session_attributes` (1 call site, line 75) |
| `src/langfuse/langfuse_session_end_hook.py` | Modify | Use `propagate_session_attributes` (1 call site, line 75) |
| `src/langfuse/langfuse_subagent_start_hook.py` | Modify | Use `propagate_session_attributes` (1 call site, line 53) |
| `src/langfuse/langfuse_subagent_stop_hook.py` | Modify | Use `propagate_session_attributes` (1 call site, line 154) |
| `src/langfuse/transcript.py` | Modify | Use `propagate_session_attributes` (1 call site, line 282) |
| `settings.example.json` | Modify | Add optional `CC_LANGFUSE_USER_ID` env var |
| `README.md` | Modify | Document `CC_LANGFUSE_USER_ID` and fallback chain |

---

## Task 1: Implement `get_user_id()` with TDD

**Files:**
- Create: `tests/test_user_id.py`
- Modify: `src/langfuse/common.py`

- [ ] **Step 1: Create the test file with failing tests for `get_user_id()`**

Create `tests/test_user_id.py`:

```python
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src" / "langfuse"))
from common import get_user_id


def test_cc_langfuse_user_id_takes_precedence():
    """CC_LANGFUSE_USER_ID env var is highest priority."""
    with patch.dict(os.environ, {
        "CC_LANGFUSE_USER_ID": "explicit-user",
        "LANGFUSE_USER_ID": "other-user",
    }):
        assert get_user_id() == "explicit-user"


def test_langfuse_user_id_fallback():
    """LANGFUSE_USER_ID is used when CC_LANGFUSE_USER_ID is not set."""
    env = {"LANGFUSE_USER_ID": "langfuse-user"}
    with patch.dict(os.environ, env, clear=True):
        assert get_user_id() == "langfuse-user"


def test_git_email_fallback():
    """Falls back to git config user.email when no env vars are set."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "dev@example.com\n"

    with patch.dict(os.environ, {}, clear=True):
        with patch("subprocess.run", return_value=mock_result) as mock_sub:
            result = get_user_id()
    assert result == "dev@example.com"
    mock_sub.assert_called_once_with(
        ["git", "config", "user.email"],
        capture_output=True, text=True, timeout=2
    )


def test_git_name_fallback_when_email_empty():
    """Falls back to git config user.name when email is empty."""
    def side_effect(args, **kwargs):
        result = MagicMock()
        if args == ["git", "config", "user.email"]:
            result.returncode = 0
            result.stdout = "\n"
        elif args == ["git", "config", "user.name"]:
            result.returncode = 0
            result.stdout = "Dev Name\n"
        return result

    with patch.dict(os.environ, {}, clear=True):
        with patch("subprocess.run", side_effect=side_effect):
            result = get_user_id()
    assert result == "Dev Name"


def test_os_getlogin_fallback():
    """Falls back to os.getlogin() when git fails."""
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = ""

    with patch.dict(os.environ, {}, clear=True):
        with patch("subprocess.run", return_value=mock_result):
            with patch("os.getlogin", return_value="osuser"):
                result = get_user_id()
    assert result == "osuser"


def test_username_env_fallback_when_getlogin_raises():
    """Falls back to USERNAME env var when os.getlogin() raises OSError."""
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = ""

    with patch.dict(os.environ, {"USERNAME": "winuser"}, clear=True):
        with patch("subprocess.run", return_value=mock_result):
            with patch("os.getlogin", side_effect=OSError("no tty")):
                result = get_user_id()
    assert result == "winuser"


def test_user_env_fallback():
    """Falls back to USER env var when USERNAME is not set."""
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = ""

    with patch.dict(os.environ, {"USER": "linuxuser"}, clear=True):
        with patch("subprocess.run", return_value=mock_result):
            with patch("os.getlogin", side_effect=OSError("no tty")):
                result = get_user_id()
    assert result == "linuxuser"


def test_unknown_final_fallback():
    """Returns 'unknown' when all other methods fail."""
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = ""

    with patch.dict(os.environ, {}, clear=True):
        with patch("subprocess.run", return_value=mock_result):
            with patch("os.getlogin", side_effect=OSError("no tty")):
                result = get_user_id()
    assert result == "unknown"


def test_subprocess_exception_falls_through():
    """subprocess.run raising an exception falls through to os.getlogin."""
    with patch.dict(os.environ, {}, clear=True):
        with patch("subprocess.run", side_effect=Exception("git not found")):
            with patch("os.getlogin", return_value="fallbackuser"):
                result = get_user_id()
    assert result == "fallbackuser"


def test_returns_non_empty_string_always():
    """get_user_id always returns a non-empty string."""
    with patch.dict(os.environ, {}, clear=True):
        with patch("subprocess.run", side_effect=Exception("fail")):
            with patch("os.getlogin", side_effect=OSError("fail")):
                result = get_user_id()
    assert isinstance(result, str)
    assert len(result) > 0
```

- [ ] **Step 2: Run tests to verify they fail (function not yet defined)**

```bash
cd C:/Users/Jose/Workspaces/rockmanjoe64/claude-fuse
uv run pytest tests/test_user_id.py -v 2>&1 | head -30
```

Expected: `ImportError` or `AttributeError: module 'common' has no attribute 'get_user_id'`

- [ ] **Step 3: Implement `get_user_id()` in `common.py`**

Add after the existing imports in `src/langfuse/common.py` (after line 13, after `from typing import Any`):

```python
import subprocess
```

Add the following function at the end of `common.py` (before any existing final functions, or at the bottom):

```python
def get_user_id() -> str:
    """Resolve user identity for Langfuse tracking.

    Priority order:
    1. CC_LANGFUSE_USER_ID env var
    2. LANGFUSE_USER_ID env var
    3. git config user.email
    4. git config user.name
    5. os.getlogin()
    6. USERNAME or USER env var
    7. "unknown"
    """
    # 1. Explicit env vars
    user_id = os.environ.get("CC_LANGFUSE_USER_ID", "").strip()
    if user_id:
        return user_id

    user_id = os.environ.get("LANGFUSE_USER_ID", "").strip()
    if user_id:
        return user_id

    # 2. Git config
    try:
        result = subprocess.run(
            ["git", "config", "user.email"],
            capture_output=True, text=True, timeout=2
        )
        if result.returncode == 0:
            user_id = result.stdout.strip()
            if user_id:
                return user_id

        result = subprocess.run(
            ["git", "config", "user.name"],
            capture_output=True, text=True, timeout=2
        )
        if result.returncode == 0:
            user_id = result.stdout.strip()
            if user_id:
                return user_id
    except Exception:
        pass

    # 3. OS username
    try:
        user_id = os.getlogin()
        if user_id:
            return user_id
    except OSError:
        pass

    user_id = os.environ.get("USERNAME") or os.environ.get("USER") or ""
    if user_id:
        return user_id

    return "unknown"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd C:/Users/Jose/Workspaces/rockmanjoe64/claude-fuse
uv run pytest tests/test_user_id.py -v
```

Expected: All 10 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd C:/Users/Jose/Workspaces/rockmanjoe64/claude-fuse
git add tests/test_user_id.py src/langfuse/common.py
git commit -m "feat: add get_user_id() with env var, git config, and OS username fallback"
```

---

## Task 2: Implement `propagate_session_attributes()` with TDD

**Files:**
- Modify: `tests/test_user_id.py`
- Modify: `src/langfuse/common.py`

- [ ] **Step 1: Add failing tests for `propagate_session_attributes()`**

Append to `tests/test_user_id.py`:

```python
from unittest.mock import call, patch as mock_patch
from contextlib import contextmanager


def test_propagate_session_attributes_passes_session_and_user_id():
    """propagate_session_attributes calls propagate_attributes with session_id and user_id."""
    from common import propagate_session_attributes

    captured = {}

    @contextmanager
    def mock_propagate(**kwargs):
        captured.update(kwargs)
        yield

    with patch.dict(os.environ, {"CC_LANGFUSE_USER_ID": "testuser"}):
        with patch("langfuse.propagate_attributes", mock_propagate):
            with propagate_session_attributes("sess-123"):
                pass

    assert captured == {"session_id": "sess-123", "user_id": "testuser"}


def test_propagate_session_attributes_yields():
    """propagate_session_attributes yields so body executes."""
    from common import propagate_session_attributes

    executed = []

    @contextmanager
    def mock_propagate(**kwargs):
        yield

    with patch("langfuse.propagate_attributes", mock_propagate):
        with patch.dict(os.environ, {"CC_LANGFUSE_USER_ID": "u"}):
            with propagate_session_attributes("sess-456"):
                executed.append(True)

    assert executed == [True]
```

- [ ] **Step 2: Run tests to verify new tests fail**

```bash
cd C:/Users/Jose/Workspaces/rockmanjoe64/claude-fuse
uv run pytest tests/test_user_id.py::test_propagate_session_attributes_passes_session_and_user_id tests/test_user_id.py::test_propagate_session_attributes_yields -v
```

Expected: `ImportError` or `AttributeError: module 'common' has no attribute 'propagate_session_attributes'`

- [ ] **Step 3: Implement `propagate_session_attributes()` in `common.py`**

Two changes to `src/langfuse/common.py`:

**3a.** Add `from contextlib import contextmanager` to the top-level imports block (alongside the other `from X import Y` lines, e.g. after `from typing import Any` at line 13):

```python
from contextlib import contextmanager
```

**3b.** Add the following function at the end of `common.py`, after `get_user_id()`:

```python
@contextmanager
def propagate_session_attributes(session_id: str):
    """Context manager that propagates session_id and user_id to Langfuse.

    Wraps langfuse.propagate_attributes, resolving user_id via get_user_id().
    Use this instead of calling propagate_attributes directly.
    """
    from langfuse import propagate_attributes
    user_id = get_user_id()
    with propagate_attributes(session_id=session_id, user_id=user_id):
        yield
```

Note: `propagate_attributes` is imported inside the function body (lazy import) to avoid a circular/top-level dependency on langfuse. This is intentional.

- [ ] **Step 4: Run all tests to verify they pass**

```bash
cd C:/Users/Jose/Workspaces/rockmanjoe64/claude-fuse
uv run pytest tests/test_user_id.py -v
```

Expected: All 12 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd C:/Users/Jose/Workspaces/rockmanjoe64/claude-fuse
git add tests/test_user_id.py src/langfuse/common.py
git commit -m "feat: add propagate_session_attributes() context manager wrapper"
```

---

## Task 3: Update hook files to use `propagate_session_attributes`

**Files:**
- Modify: `src/langfuse/langfuse_session_start_hook.py`
- Modify: `src/langfuse/langfuse_session_end_hook.py`
- Modify: `src/langfuse/langfuse_subagent_start_hook.py`
- Modify: `src/langfuse/langfuse_subagent_stop_hook.py`

In each of these 4 files, make the same two changes:

**Change 1** — Replace the import (near the top of each file):
```python
# Remove this line:
from langfuse import propagate_attributes

# Add propagate_session_attributes to the existing common import block:
from common import (
    ...,
    propagate_session_attributes,
)
```

**Change 2** — Replace the call site (one per file):
```python
# Before:
with propagate_attributes(session_id=session_id):

# After:
with propagate_session_attributes(session_id):
```

Exact locations:
- `langfuse_session_start_hook.py`: import at line 23, call at line 75
- `langfuse_session_end_hook.py`: import at line 20, call at line 75
- `langfuse_subagent_start_hook.py`: import at line 19, call at line 53
- `langfuse_subagent_stop_hook.py`: import at line 23, call at line 154

- [ ] **Step 1: Update `langfuse_session_start_hook.py`**

Remove `from langfuse import propagate_attributes` (line 23).

Add `propagate_session_attributes` to the `from common import (...)` block (lines 14-22).

Replace `with propagate_attributes(session_id=session_id):` (line 75) with `with propagate_session_attributes(session_id):`.

- [ ] **Step 2: Update `langfuse_session_end_hook.py`**

Remove `from langfuse import propagate_attributes` (line 20).

Add `propagate_session_attributes` to the `from common import (...)` block (lines 11-19).

Replace `with propagate_attributes(session_id=session_id):` (line 75) with `with propagate_session_attributes(session_id):`.

- [ ] **Step 3: Update `langfuse_subagent_start_hook.py`**

Remove `from langfuse import propagate_attributes` (line 19).

Add `propagate_session_attributes` to the `from common import (...)` block (lines 10-18).

Replace `with propagate_attributes(session_id=session_id):` (line 53) with `with propagate_session_attributes(session_id):`.

- [ ] **Step 4: Update `langfuse_subagent_stop_hook.py`**

Remove `from langfuse import propagate_attributes` (line 23).

Add `propagate_session_attributes` to the `from common import (...)` block (lines 12-20).

Replace `with propagate_attributes(session_id=session_id):` (line 154) with `with propagate_session_attributes(session_id):`.

- [ ] **Step 5: Run the full test suite**

```bash
cd C:/Users/Jose/Workspaces/rockmanjoe64/claude-fuse
uv run pytest tests/ -v
```

Expected: All tests PASS. No import errors.

- [ ] **Step 6: Commit**

```bash
cd C:/Users/Jose/Workspaces/rockmanjoe64/claude-fuse
git add src/langfuse/langfuse_session_start_hook.py src/langfuse/langfuse_session_end_hook.py src/langfuse/langfuse_subagent_start_hook.py src/langfuse/langfuse_subagent_stop_hook.py
git commit -m "feat: use propagate_session_attributes in session and subagent hooks"
```

---

## Task 4: Update `transcript.py`

**Files:**
- Modify: `src/langfuse/transcript.py`

- [ ] **Step 1: Update `transcript.py`**

Remove `from langfuse import propagate_attributes` (line 12).

Add `propagate_session_attributes` to the `from common import (...)` block (lines 3-11):

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
)
```

Replace `with propagate_attributes(session_id=session_id):` (line 282 in `create_trace`) with `with propagate_session_attributes(session_id):`.

- [ ] **Step 2: Run the full test suite**

```bash
cd C:/Users/Jose/Workspaces/rockmanjoe64/claude-fuse
uv run pytest tests/ -v
```

Expected: All tests PASS.

- [ ] **Step 3: Commit**

```bash
cd C:/Users/Jose/Workspaces/rockmanjoe64/claude-fuse
git add src/langfuse/transcript.py
git commit -m "feat: use propagate_session_attributes in transcript create_trace"
```

---

## Task 5: Update configuration and documentation

**Files:**
- Modify: `settings.example.json`
- Modify: `README.md`

- [ ] **Step 1: Update `settings.example.json`**

Add `CC_LANGFUSE_USER_ID` as an optional env var in the `env` block. Current `env` block (lines 2-7):

```json
"env": {
  "TRACE_TO_LANGFUSE": "true",
  "LANGFUSE_PUBLIC_KEY": "pk-lf-your-public-key-here",
  "LANGFUSE_SECRET_KEY": "sk-lf-your-secret-key-here",
  "LANGFUSE_HOST": "https://cloud.langfuse.com"
},
```

Add after `LANGFUSE_HOST`:

```json
"env": {
  "TRACE_TO_LANGFUSE": "true",
  "LANGFUSE_PUBLIC_KEY": "pk-lf-your-public-key-here",
  "LANGFUSE_SECRET_KEY": "sk-lf-your-secret-key-here",
  "LANGFUSE_HOST": "https://cloud.langfuse.com",
  "CC_LANGFUSE_USER_ID": ""
},
```

(Empty string means it is disabled by default — the fallback chain runs when unset or empty.)

- [ ] **Step 2: Update `README.md` environment variables section**

Locate the "Environment Variables" section (around line 244). After the existing `CC_LANGFUSE_DEBUG` entry, add:

```markdown
- **CC_LANGFUSE_USER_ID** (optional): Explicit user identifier sent to Langfuse for per-user analytics. If not set, auto-detected via: `LANGFUSE_USER_ID` env var → git config email → git config name → OS username → `"unknown"`.
```

- [ ] **Step 3: Commit**

```bash
cd C:/Users/Jose/Workspaces/rockmanjoe64/claude-fuse
git add settings.example.json README.md
git commit -m "docs: add CC_LANGFUSE_USER_ID config option and user tracking documentation"
```

---

## Final Verification

- [ ] **Run the full test suite one last time**

```bash
cd C:/Users/Jose/Workspaces/rockmanjoe64/claude-fuse
uv run pytest tests/ -v
```

Expected: All tests PASS.

- [ ] **Verify no remaining direct `propagate_attributes` imports in hook files**

```bash
cd C:/Users/Jose/Workspaces/rockmanjoe64/claude-fuse
grep -rn "from langfuse import propagate_attributes" src/langfuse/
```

Expected: No output (all replaced with `propagate_session_attributes` from `common`).

- [ ] **Verify `propagate_session_attributes` is used everywhere**

```bash
cd C:/Users/Jose/Workspaces/rockmanjoe64/claude-fuse
grep -rn "propagate_session_attributes" src/langfuse/
```

Expected: 6 lines — one in each of: `common.py` (definition), `langfuse_session_start_hook.py`, `langfuse_session_end_hook.py`, `langfuse_subagent_start_hook.py`, `langfuse_subagent_stop_hook.py`, `transcript.py`.
