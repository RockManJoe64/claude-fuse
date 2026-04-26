# Code Style and Conventions

## Python
- Type hints used throughout (e.g., `Optional`, `dict`, `list`)
- Short module-level docstrings on hook scripts
- No multi-line docstrings on functions — single-line or none
- No comments unless WHY is non-obvious
- Snake_case for functions and variables; UPPER_CASE for module-level constants
- Relative imports between `common.py` and `transcript.py` (both in same directory, run as standalone scripts with `uv run`)

## Hook Scripts
- Shebang: `#!/usr/bin/env python3`
- PEP 723 inline script metadata block immediately after shebang (added during restructure)
- Each script is standalone — no package install required, dependencies resolved by `uv run`
- Read hook input from stdin (JSON); exit 0 on success, non-zero on fatal error

## Tests
- pytest with `unittest.mock`
- `sys.path.insert` at top of test files to add hooks directory
- No mocking of the database — patches target `langfuse.propagate_attributes` and `subprocess.run`
- No fixtures file — each test file is self-contained

## No lint/format tooling configured in the project.
