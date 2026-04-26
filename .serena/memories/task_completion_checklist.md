# Task Completion Checklist

When a coding task is complete:

1. **Run tests**: `uv run pytest tests/ -v`
   - All tests must pass before committing
2. **No lint/format step** — project has none configured
3. **Commit** with a conventional commit message (feat/fix/refactor/docs/test/chore)
   - Commits go on `feature/plugin-restructure`, not `develop`
   - Do NOT commit `.claude/settings.local.json` (contains secrets, is gitignored)
4. **Verify no dangling `src/langfuse/` references** (during restructure):
   ```bash
   grep -r "src/langfuse" --include="*.py" --include="*.json" --include="*.md" .
   ```
