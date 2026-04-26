# Suggested Commands

## Development (Windows, bash shell)

```bash
# Install dependencies
uv sync

# Run all tests
uv run pytest

# Run a single test file
uv run pytest tests/test_user_id.py

# Run a single test by name
uv run pytest tests/test_user_id.py::test_cc_langfuse_user_id_takes_precedence

# Run tests verbose
uv run pytest tests/ -v
```

There is no build, lint, or format step — this is a pure Python hooks project.

## Git
Standard git commands work (bash shell on Windows). Branch: `feature/plugin-restructure`, main integration branch: `develop`.

## System Utilities (Windows/bash)
- `ls`, `find`, `grep` work via Git Bash
- `chmod +x` works for marking scripts executable in git
