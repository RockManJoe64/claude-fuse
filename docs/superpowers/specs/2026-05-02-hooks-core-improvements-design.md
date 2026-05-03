# Hooks Core Improvements Design Document

> **Date:** 2026-05-02
> **Scope:** 7 improvements identified by comparing our hooks to the Langfuse-provided reference implementation.
> **Approach:** Layered (Approach A)

---

## Design Section 1: State Key Hashing & Content Truncation

### 1.1 State Key Hashing

**Problem:** Our current state uses `session_id` directly as the top-level key in `langfuse_state.json`. If the same `session_id` is reused with a different transcript path (e.g., workspace migration), state corruption can occur.

**Solution:** Replace the key generation function with a deterministic SHA-256 hash of `session_id + "::" + transcript_path`. The hashed string remains safe to use as a JSON key.

```python
def state_key(session_id: str, transcript_path: str) -> str:
    raw = f"{session_id}::{transcript_path}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
```

All call sites (`save_state`, `load_state`, `process_transcript`, `hooks`) will use this function instead of `session_id` directly.

### 1.2 Content Truncation

**Problem:** Our hooks send raw transcript content to Langfuse, which can exceed Langfuse limits or create bloated traces.

**Solution:** Add a `truncate_text()` utility function in `common.py`, controlled by an optional `CC_LANGFUSE_MAX_CHARS` environment variable (default: 20,000). It truncates text, attaches metadata about truncation, and computes a SHA-256 of the original for later verification.

```python
def truncate_text(s: str, max_chars: int = 20000) -> str: ...
# Returns: (truncated_str, metadata_dict)
```

`create_trace()` in `transcript.py` will use this for `user_text`, `assistant_text`, and `tool_output`.

---

## Design Section 2: Incremental Transcript Reading

### 2.1 Problem
Our current `process_transcript()` reads the entire transcript file on every `Stop` event, skipping already-processed lines by line-number index. For long sessions (thousands of lines), this is wasteful.

### 2.2 Solution
Adopt byte-offset incremental reading, similar to the Langfuse reference hook.

**Key Changes:**
- Replace `last_line` (line index) with `offset` (byte position) and `buffer` (partial line buffer) in session state.
- On each `Stop` event, `seek()` to the stored offset, read only new bytes, and append to a buffer for incomplete last lines.
- Use `rb` mode for robust encoding handling.

**State structure update:**
```json
{
  "<state_key>": {
    "offset": 2048,
    "buffer": "",
    "turn_count": 5,
    "updated": "2026-05-02T13:00:00Z"
  }
}
```

**Implementation:** A new `read_new_jsonl()` function in `transcript.py` (or `common.py`) will handle this.

### 2.3 Migration Path
Old states using `last_line` will gracefully reset to `offset: 0` on first run. We will add a version marker to the state file or simply handle missing `offset` by defaulting to 0.

---

## Design Section 3: Assistant Message Deduplication

### 3.1 Problem
Claude Code can emit the same assistant `message.id` multiple times during streaming (partial updates). Our current `parse_transcript_into_turns()` merges consecutive parts but doesn't deduplicate by ID across non-consecutive rows, potentially creating duplicate assistant messages.

### 3.2 Solution
Modify `parse_transcript_into_turns()` to track assistant messages by `message.id` within each turn. The latest row per ID wins while preserving order of first appearance.

```python
assistant_order: List[str] = []  # message ids in order of first appearance
assistant_latest: Dict[str, Dict] = {}  # id -> latest msg
```

This ensures that if the same assistant message is updated mid-turn, we keep the final version.

---

## Design Section 4: Langfuse UX Enhancements

### 4.1 Tool Observation Typing (`as_type="tool"`)
In `transcript.py` `create_trace()`, add `as_type="tool"` when creating tool spans. This helps Langfuse classify and display them correctly.

### 4.2 Tags in `propagate_attributes`
In `common.py`, update `propagate_session_attributes()` to include `tags=["claude-code"]`.

### 4.3 Environment Variable Alias for Host
In `create_langfuse_client()`, add fallback checks for `CC_LANGFUSE_BASE_URL` and `LANGFUSE_BASE_URL` in addition to the existing `HOST` variants.

---

## Testing Strategy
- All changes must pass existing tests (`uv run pytest`).
- New tests should be added for `state_key()`, `truncate_text()`, and `read_new_jsonl()`.
- Regression test: verify that a large transcript file is processed correctly with the incremental reader.

---

## Files to Modify
- `hooks/common.py` — `state_key()`, `truncate_text()`, `propagate_session_attributes()`, `create_langfuse_client()`
- `hooks/transcript.py` — `parse_transcript_into_turns()`, `create_trace()`, `read_new_jsonl()`
- `hooks/langfuse_stop_hook.py` — `process_transcript()` to use offset-based reading
- `tests/` — new test files for utilities

---

## Rollback Plan
If issues arise with the incremental reader, reverting `langfuse_stop_hook.py` to line-based reading is straightforward. The state file format is additive (new keys), so old code ignores `offset` and `buffer` gracefully.

---
