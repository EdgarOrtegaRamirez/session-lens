# SessionLens

**AI coding session analyzer and optimizer** — Track, analyze, and optimize your AI-assisted coding sessions with deep insights into prompt quality, token usage, productivity, and code changes.

## Features

- **Session Tracking** — Record AI coding sessions with prompts, responses, file edits, and tool calls
- **Deep Analysis** — Analyze prompt complexity, intent detection, token usage patterns, and productivity metrics
- **Insights Engine** — Automatic detection of high token usage, low productivity, excessive scope, and error patterns
- **Rich Reports** — Generate text or markdown reports with detailed session breakdowns
- **SQLite Storage** — Fast, reliable, local-first storage with full-text search
- **CLI Interface** — 8 commands for managing sessions from the terminal
- **MCP Server** — Integrate with AI coding agents via Model Context Protocol
- **Cross-model** — Works with any LLM (OpenAI, Anthropic, local models)

## Install

```bash
# From source
pip install -e .

# With MCP support
pip install -e ".[mcp]"

# Development
pip install -e ".[dev]"
```

## Quick Start

```bash
# Initialize database
session-lens init

# Start a new session
session-lens start -t "Refactor auth module" -p ./myproject --model gpt-4o

# List sessions
session-lens list

# Analyze a session
session-lens analyze <session-id>

# Get aggregate stats
session-lens info
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `init` | Initialize the SessionLens database |
| `start` | Start a new coding session |
| `stop` | Stop an active session |
| `add-message` | Add a message to an existing session |
| `list` | List sessions with filtering |
| `show` | Show session details |
| `analyze` | Analyze a session for insights |
| `search` | Search sessions by title, notes, or tags |
| `info` | Show aggregate statistics |
| `delete` | Delete a session |
| `sample-config` | Print a sample configuration file |

## Analysis Features

SessionLens analyzes sessions across multiple dimensions:

### Prompt Analysis
- **Complexity detection** — Identifies simple, medium, and complex prompts
- **Intent classification** — Detects creation, debugging, refactoring, learning, testing, documentation, review, and migration intents
- **Token estimation** — Uses tiktoken to estimate token counts
- **Length categorization** — Classifies prompts as short, medium, long, or very_long

### Productivity Metrics
- Net lines added/removed
- Files changed count
- Edits per minute
- Tokens per line ratio
- Error rate

### Insight Categories
- **Token warnings** — Flags sessions exceeding 50k tokens
- **Productivity alerts** — Detects low edit rates
- **Scope warnings** — Flags excessive file touching
- **Quality indicators** — Highlights error patterns

## MCP Integration

SessionLens provides an MCP server for AI agent integration:

```python
from session_lens.mcp_server import create_mcp_server

server = create_mcp_server()
```

Available MCP tools:
- `session_lens_list_sessions` — List sessions with filtering
- `session_lens_analyze_session` — Analyze a session for insights
- `session_lens_get_stats` — Get aggregate statistics

## Architecture

```
session-lens/
├── src/session_lens/
│   ├── __init__.py       # Package init
│   ├── models.py         # Data models (Message, FileEdit, CodingSession)
│   ├── analyzer.py       # Analysis engine & report generator
│   ├── storage.py        # SQLite-backed session storage
│   ├── cli.py            # Click-based CLI interface
│   └── mcp_server.py     # MCP server for AI agent integration
├── tests/                # Test suite
├── pyproject.toml        # Project configuration
├── README.md
├── LICENSE
├── AGENTS.md
└── SECURITY.md
```

## Data Model

- **CodingSession** — Top-level entity with title, project path, model, tags, status
- **Message** — Individual messages (prompts, responses, tool calls, errors)
- **FileEdit** — Tracked file changes with line counts and descriptions
- **SessionSummary** — Computed statistics (tokens, counts, metrics)

## Configuration

Environment variables:
- `SESSIONS_DIR` — Session data directory (default: `~/.session-lens/sessions`)
- `DB_PATH` — Database path (default: `~/.session-lens/session-lens.db`)
- `OPENAI_API_KEY` — For OpenAI token estimation
- `ANTHROPIC_API_KEY` — For Anthropic token estimation

## License

MIT — See [LICENSE](LICENSE) for details.
