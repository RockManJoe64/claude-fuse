#!/usr/bin/env bash
# Verify that uv is installed before running Langfuse hooks.

# --- Diagnostic logging (remove after troubleshooting) ---
DIAG_LOG="$HOME/.claude/state/langfuse_hook.log"
mkdir -p "$(dirname "$DIAG_LOG")"
echo "$(date '+%Y-%m-%d %H:%M:%S') [DIAG] check_uv.sh invoked" >> "$DIAG_LOG"
echo "$(date '+%Y-%m-%d %H:%M:%S') [DIAG] CLAUDE_PLUGIN_ROOT=${CLAUDE_PLUGIN_ROOT:-<unset>}" >> "$DIAG_LOG"
echo "$(date '+%Y-%m-%d %H:%M:%S') [DIAG] script location: $(cd "$(dirname "$0")" && pwd)" >> "$DIAG_LOG"
echo "$(date '+%Y-%m-%d %H:%M:%S') [DIAG] pwd: $(pwd)" >> "$DIAG_LOG"
# --- End diagnostic logging ---

if ! command -v uv &>/dev/null; then
  echo "claude-fuse: 'uv' is required but not found." >&2
  echo "Install it: curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
  echo "Windows:    powershell -c \"irm https://astral.sh/uv/install.ps1 | iex\"" >&2
  exit 1
fi

exit 0
