# Hooks Reference

Documentation for the individual hook scripts and shared infrastructure in this directory.

## Architecture

```
Claude Code Session
├── SessionStart Hook → Langfuse "Session Start" span
├── Stop Hook (after each turn)
│   ├── Parse transcript
│   └── Create traces with:
│       ├── User input
│       ├── Assistant response
│       └── Tool calls (with inputs/outputs)
├── SubagentStart Hook → Langfuse "Subagent Start" span
├── SubagentStop Hook
│   ├── Parse subagent transcript
│   └── Create prefixed traces: [AgentType] Turn N
└── SessionEnd Hook → Langfuse "Session End" span
```

## Claude Code Hooks

### 1. SessionStart Hook

**File**: `langfuse_session_start_hook.py`

**Trigger**: Runs when a new Claude Code session starts.

**What it does**:
- Creates a "Session Start" span in Langfuse with session metadata
- Records the session source (startup, resume, etc.)
- Captures the working directory and model information
- Initializes session state tracking for later hooks

**Langfuse metadata**:
- `event`: "session_start"
- `start_source`: How the session was initiated
- `model`: The Claude model being used
- `cwd`: Current working directory

### 2. SessionEnd Hook

**File**: `langfuse_session_end_hook.py`

**Trigger**: Runs when a Claude Code session ends.

**What it does**:
- Creates a "Session End" span in Langfuse
- Calculates total session duration
- Records total number of turns in the session
- Captures the reason for session termination
- Cleans up session state

**Langfuse output**:
- `status`: "session_ended"
- `reason`: Why the session ended
- `total_turns`: Number of conversation turns
- `duration_seconds`: Total session duration

### 3. Stop Hook

**File**: `langfuse_stop_hook.py`

**Trigger**: Runs after each Claude response (after every turn).

**What it does**:
- Parses the conversation transcript to extract new turns since last run
- Creates detailed Langfuse traces for each turn containing:
  - User prompt
  - Assistant response
  - All tool calls made during the turn
  - Tool inputs and outputs
- Maintains state to track which lines have been processed
- Implements streaming to handle large transcript files efficiently

**Langfuse trace structure**:
- Turn-level span with user input and assistant output
- Generation observation with model information
- Individual tool spans for each tool call
- Complete input/output capture for debugging

**Performance**:
- Streams transcript files to avoid memory issues
- Implements timeout handling for network operations
- Logs warnings if processing takes longer than 3 minutes

### 4. SubagentStart Hook

**File**: `langfuse_subagent_start_hook.py`

**Trigger**: Runs when a Task agent (subagent) is launched.

**What it does**:
- Creates a "Subagent Start" span in Langfuse
- Records the agent type (Bash, Explore, Plan, etc.)
- Tracks the agent ID for later correlation
- Updates session state with subagent information

**Langfuse metadata**:
- `event`: "subagent_start"
- `agent_type`: Type of agent being launched
- `agent_id`: Unique identifier for this agent instance

### 5. SubagentStop Hook

**File**: `langfuse_subagent_stop_hook.py`

**Trigger**: Runs when a Task agent completes.

**What it does**:
- Parses the subagent's complete transcript
- Creates traces for all turns within the subagent execution
- Prefixes subagent traces with `[agent_type]` for easy identification
- Calculates subagent execution duration
- Records total turns processed by the subagent
- Cleans up subagent state

**Langfuse output**:
- `status`: "subagent_stopped"
- `agent_type`: Type of agent that stopped
- `total_turns`: Number of turns processed by subagent
- `duration_seconds`: How long the subagent ran

**Trace prefixes**: Subagent traces are labeled with `[Bash]`, `[Explore]`, `[Plan]`, etc. to distinguish them from main session traces.

## Common Infrastructure

### common.py

Provides shared utilities used by all hooks:

- **State management**: Load/save session state with file locking
- **Logging**: Centralized logging to `~/.claude/state/langfuse_hook.log`
- **Input parsing**: Read and validate JSON hook input from stdin
- **Langfuse client**: Initialize authenticated Langfuse client
- **Message parsing**: Extract content, tool calls, and text from transcript messages
- **Error handling**: Comprehensive timeout and fault tolerance

### transcript.py

Handles transcript parsing and trace creation:

- **Turn parsing**: Groups transcript messages into user/assistant turns
- **Message merging**: Combines streaming assistant response chunks
- **Trace creation**: Builds structured Langfuse traces with generations and tool spans
- **Error recovery**: Robust error handling for malformed transcript data
