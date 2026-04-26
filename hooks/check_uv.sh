#!/usr/bin/env bash
# Verify that uv is installed before running Langfuse hooks.

if ! command -v uv &>/dev/null; then
  echo "claude-fuse: 'uv' is required but not found." >&2
  echo "Install it: curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
  echo "Windows:    powershell -c \"irm https://astral.sh/uv/install.ps1 | iex\"" >&2
  exit 1
fi

exit 0
