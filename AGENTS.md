# AGENTS.md

## SessionLens — Notes for AI Agents

### Project Overview
SessionLens is a CLI tool and Python library for tracking, analyzing, and optimizing AI-assisted coding sessions. It stores session data in SQLite and provides deep analysis of prompts, productivity metrics, and code changes.

### Key Files
- `src/session_lens/models.py` — Core data models (CodingSession, Message, FileEdit, SessionSummary)
- `src/session_lens/analyzer.py` — Analysis engine (SessionAnalyzer) and report generation (ReportGenerator)
- `src/session_lens/storage.py` — SQLite-backed persistence (SessionStore)
- `src/session_lens/cli.py` — Click CLI interface with 8 commands
- `src/session_lens/mcp_server.py` — MCP server for AI agent integration
- `pyproject.toml` — Project config, dependencies, entry points

### Dependencies
- `click` — CLI framework
- `pydantic` — Data validation (via models)
- `pyyaml` — YAML support (sample-config command)
- `rich` — Rich text output (optional, used by click)
- `sqlite-utils` — SQLite utilities
- `tiktoken` — Token estimation for various LLMs

### Testing
Run tests: `pytest tests/ -v`
The test suite covers:
- Model serialization (to_dict/from_dict round-trip)
- SessionAnalyzer analysis accuracy
- Storage CRUD operations
- Edge cases (empty sessions, missing fields)

### Code Style
- Python 3.11+
- Type hints on all public functions
- Docstrings on all modules, classes, and public methods
- Line length: 100 chars
- Uses `__slots__` in hot-path models
- Uses `dataclass` for analysis result objects

### Security Notes
- SQLite database is local-only, no network calls
- No hardcoded secrets or API keys
- All user input is validated through Pydantic models and Click arguments
- File paths are validated for traversal attacks in analysis

### MCP Server
The MCP server exposes 3 tools:
1. `session_lens_list_sessions` — List/filter sessions
2. `session_lens_analyze_session` — Analyze session with optional text/json/markdown output
3. `session_lens_get_stats` — Aggregate statistics

Run with: `python -m session_lens.mcp_server`

### Common Operations
- Add a session: `store.save_session(session)`
- Query sessions: `store.list_sessions(status=..., limit=...)`
- Analyze: `analyzer.analyze_session(session)`
- Report: `ReportGenerator().generate_text_report(analysis)`
