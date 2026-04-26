# Plugin Restructure — Session Primer

Paste this into a new Claude Code session to execute the implementation plan.

---

## Context

We're restructuring the claude-fuse repo to be a distributable Claude Code plugin. Currently hooks live in `src/langfuse/`; they need to move to `hooks/` with plugin metadata added.

## Key files

- **Design spec:** `docs/superpowers/specs/2026-04-12-plugin-restructure-design.md`
- **Implementation plan:** `docs/superpowers/plans/2026-04-12-plugin-restructure.md`

## Instructions

1. Check out the `feature/plugin-restructure` branch (it already exists with the spec and plan committed).
2. Read the implementation plan at the path above.
3. Execute Tasks 1–10 in order, committing after each task as specified.
4. All commits go on `feature/plugin-restructure`, not `develop`.
5. Run `uv run pytest tests/ -v` after Task 5 and again in Task 10 to verify nothing broke.

## Quick summary of tasks

| Task | What |
|------|------|
| 1 | Create `.claude-plugin/plugin.json` and `marketplace.json` |
| 2 | Create `hooks/hooks.json` and `hooks/check_uv.sh` |
| 3 | `git mv` all 7 Python files from `src/langfuse/` to `hooks/`, delete `src/` |
| 4 | Add PEP 723 headers, remove `sys.path.insert` hacks |
| 5 | Update test imports from `src/langfuse` to `hooks`, run tests |
| 6 | Update `settings.example.json` paths |
| 7 | Update `CLAUDE.md` paths |
| 8 | Rewrite `README.md` install section (plugin primary, manual as Advanced) |
| 9 | Update `.claude/settings.local.json` locally (don't commit — has secrets) |
| 10 | Final verification: tests, directory structure, no dangling refs |
