### Task 5: Tool Observation Typing

**Files:**
- Modify: `hooks/transcript.py`

- [ ] **Step 1: Add `as_type="tool"` to tool spans**

In `create_trace()` inside `hooks/transcript.py`, find the tool span creation block:

```python
with langfuse.start_as_current_observation(
    name=tool_span_name,
    input=tool_call.get("input", {}),
    as_type="tool",
    metadata=build_metadata({...}),
) as tool_span:
```

- [ ] **Step 2: Run tests to verify it passes**

Run: `uv run pytest tests/ -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add hooks/transcript.py
git commit -m "feat: mark tool spans with as_type=\"tool\" for Langfuse classification"
```

### Task 6: Tags in propagate_attributes

**Files:**
- Modify: `hooks/common.py`

- [ ] **Step 1: Add `tags=["claude-code"]`**

In `hooks/common.py`, update `propagate_session_attributes`:

```python
@contextmanager
def propagate_session_attributes(session_id: str):
    from langfuse import propagate_attributes
    user_id = get_user_id()
    with propagate_attributes(session_id=session_id, user_id=user_id, tags=["claude-code"]):
        yield
```

- [ ] **Step 2: Run tests to verify it passes**

Run: `uv run pytest tests/ -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add hooks/common.py
git commit -m "feat: tag traces with claude-code for Langfuse filtering"
```

### Task 7: Environment Variable Alias for Host

**Files:**
- Modify: `hooks/common.py`

- [ ] **Step 1: Add BASE_URL fallback**

In `hooks/common.py`, inside `create_langfuse_client()`, update the `host` line:

```python
host = (
    os.environ.get("CC_LANGFUSE_HOST")
    or os.environ.get("LANGFUSE_HOST")
    or os.environ.get("CC_LANGFUSE_BASE_URL")
    or os.environ.get("LANGFUSE_BASE_URL")
    or "https://cloud.langfuse.com"
)
```

- [ ] **Step 2: Run tests to verify it passes**

Run: `uv run pytest tests/ -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add hooks/common.py
git commit -m "feat: support CC_LANGFUSE_BASE_URL and LANGFUSE_BASE_URL aliases"
```

### Task 8: Full Regression Test

**Files:**
- Run: `uv run pytest`

- [ ] **Step 1: Run the full test suite**

Run: `uv run pytest`
Expected: All existing tests (21+) pass without regression.

- [ ] **Step 2: Commit**

```bash
git commit --allow-empty -m "chore: verify regression suite passes after hook improvements"
```

---

## Self-Review

**1. Spec coverage:**
- State Key Hashing (Task 1) ✅
- Content Truncation (Task 2) ✅
- Incremental Transcript Reading (Task 3) ✅
- Assistant Message Deduplication (Task 4) ✅
- Tool Observation Typing (Task 5) ✅
- Tags in propagate_attributes (Task 6) ✅
- Environment Variable Alias for Host (Task 7) ✅

**2. Placeholder scan:**
- No "TBD", "TODO", or incomplete sections found. All steps show exact code and commands.

**3. Type consistency:**
- `state_key` signature used consistently across all hooks.
- `truncate_text` return type `(str, dict)` stable.
- `read_new_jsonl` state dict keys consistent.

**Ready for execution.**