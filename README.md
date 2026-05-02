<img src="docs/claude-fuse-logo.jpeg" width="120" height="120" alt="claude-fuse logo" />

# claude-fuse

A comprehensive set of Claude Code hooks for capturing telemetry, usage metrics, and conversation traces using Langfuse. These hooks provide complete observability into your Claude Code sessions, including session lifecycle, conversation turns, tool usage, and subagent execution.

## Table of Contents

- [Overview](#overview)
- [Setup and Configuration](#setup-and-configuration)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Getting Langfuse API Keys](#getting-langfuse-api-keys)
  - [Configuration Options](#configuration-options)
- [Viewing Your Data in Langfuse](#viewing-your-data-in-langfuse)

- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)
- [Related Links](#related-links)

## Overview

This repository provides Python-based hooks that integrate with Langfuse to track and analyze Claude Code interactions. The hooks capture detailed information about:

- Session lifecycle (start/end events with duration and turn counts)
- Conversation turns (user prompts, assistant responses, and tool calls)
- Tool usage patterns (which tools are called, inputs, and outputs)
- Subagent execution (Task agent lifecycle and performance)
- Model usage and metadata

All captured data is sent to Langfuse where you can visualize, analyze, and monitor your Claude Code usage in real-time.

## Setup and Configuration

### Prerequisites

- [uv](https://github.com/astral-sh/uv) package manager (required)
  - Unix: `curl -LsSf https://astral.sh/uv/install.sh | sh`
  - MacOS: `brew install uv`
  - Windows: `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`
- A [Langfuse](https://langfuse.com/) account (free tier available)
- Claude Code CLI

> **Note:** Hooks only run in **trusted workspaces**. If hooks appear to be silently ignored, check your workspace trust settings.

### Installation

#### Plugin Install (Recommended)

Install claude-fuse as a Claude Code plugin in three steps:

**Step 1 — Add the marketplace and install:**

```
/plugin marketplace add RockManJoe64/claude-fuse
/plugin install claude-fuse
/reload-plugins
```

**Step 2 — Set environment variables in `~/.claude/settings.json`:**

> **Important:** Environment variables must be placed in `~/.claude/settings.json` (not `settings.local.json`). Plugin hooks only inherit env vars from the user-level `settings.json`.

Add an `env` block to your `~/.claude/settings.json`:

```json
{
  "env": {
    "TRACE_TO_LANGFUSE": "true",
    "LANGFUSE_PUBLIC_KEY": "pk-lf-your-public-key",
    "LANGFUSE_SECRET_KEY": "sk-lf-your-secret-key",
    "LANGFUSE_HOST": "https://us.cloud.langfuse.com"
  }
}
```

Replace the key values with your actual Langfuse credentials (see [Getting Langfuse API Keys](#getting-langfuse-api-keys) below).

**Step 3 — Start a new Claude Code session.** Hooks activate automatically. Check `~/.claude/state/langfuse_hook.log` to confirm they're running.

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

### Getting Langfuse API Keys

1. Sign up for a free account at [langfuse.com](https://langfuse.com/)
2. Create a new project in the Langfuse dashboard
3. Navigate to Settings > API Keys
4. Copy your Public Key (starts with `pk-lf-`)
5. Copy your Secret Key (starts with `sk-lf-`)
6. Note your Langfuse host URL:
   - US Cloud: `https://us.cloud.langfuse.com`
   - EU Cloud: `https://cloud.langfuse.com`
   - Self-hosted: Your custom URL

### Configuration Options

#### Environment Variables

Set these in `~/.claude/settings.json` (the user-level settings file). Plugin hooks do **not** inherit from `settings.local.json`.

| Variable | Required | Description |
|---|---|---|
| `TRACE_TO_LANGFUSE` | Yes | Set to `"true"` to enable tracing |
| `LANGFUSE_PUBLIC_KEY` | Yes | Your Langfuse public API key (`pk-lf-...`) |
| `LANGFUSE_SECRET_KEY` | Yes | Your Langfuse secret API key (`sk-lf-...`) |
| `LANGFUSE_HOST` | No | Langfuse server URL (defaults to `https://cloud.langfuse.com`) |
| `CC_LANGFUSE_DEBUG` | No | Set to `"true"` to enable verbose debug logging |
| `CC_LANGFUSE_USER_ID` | No | Explicit user identity for Langfuse. Auto-detected if not set: `LANGFUSE_USER_ID` env → git email → git name → OS username → `"unknown"` |

You can also use `CC_LANGFUSE_*` prefixed variants: `CC_LANGFUSE_PUBLIC_KEY`, `CC_LANGFUSE_SECRET_KEY`, `CC_LANGFUSE_HOST`.

#### Hook Configuration

Each hook can be enabled/disabled independently in your settings file. Remove a hook from the configuration to disable it.

#### Debugging

Enable debug logging to troubleshoot issues:

```json
{
  "env": {
    "CC_LANGFUSE_DEBUG": "true"
  }
}
```

Debug logs are written to `~/.claude/state/langfuse_hook.log`

## Viewing Your Data in Langfuse

Once configured, your Claude Code sessions will automatically appear in your Langfuse dashboard:

1. **Traces**: View individual conversation turns with complete tool call details
2. **Sessions**: Group traces by Claude Code session using the session_id
3. **Analytics**: Track usage patterns, model performance, and tool usage
4. **Debugging**: Inspect full input/output for each turn to debug issues

### Example Langfuse Views

- Filter by `source: "claude-code"` to see all Claude Code traces
- Use session_id to group related traces
- Filter by `event: "subagent_start"` to find Task agent usage
- Search by tool names to analyze specific tool patterns

## Troubleshooting

### Hooks Not Running

1. Verify `TRACE_TO_LANGFUSE=true` is in `~/.claude/settings.json` (not `settings.local.json` — plugin hooks don't inherit from it)
2. Run `/hooks` in Claude Code to confirm the claude-fuse hooks appear in the list
3. Check `~/.claude/state/langfuse_hook.log` for error messages
4. Ensure `uv` is installed and in your PATH

### Plugin Install Fails or Hooks Don't Appear After Install

Stale temporary directories from a failed install can block future installs. Clean them up and reinstall:

```bash
rm -rf ~/.claude/plugins/cache/temp_github_*
```

Then in Claude Code:

```
/plugin uninstall claude-fuse
/plugin install claude-fuse
/reload-plugins
```

### Missing Traces in Langfuse

1. Verify your API keys are correct
2. Check network connectivity to Langfuse host
3. Look for timeout errors in the log file
4. Enable debug logging with `CC_LANGFUSE_DEBUG=true`

### Performance Issues

1. The Stop hook may take longer on large transcripts (handled gracefully)
2. Hooks have built-in timeout handling to avoid blocking Claude Code
3. Check logs for warnings about processing time >3 minutes

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

## License

See LICENSE file for details.

## Related Links

- [Claude Code Documentation](https://docs.anthropic.com/claude-code)
- [Langfuse Documentation](https://langfuse.com/docs)
- [Claude Code Hooks Guide](https://docs.anthropic.com/claude-code/docs/hooks)
