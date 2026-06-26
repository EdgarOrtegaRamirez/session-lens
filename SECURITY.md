# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | ✅ Yes     |

## Security Architecture

SessionLens is designed with security in mind:

- **Local-first** — All data is stored locally in SQLite. No data is sent to external services.
- **No network calls** — The core library makes no network requests.
- **No secrets stored** — No API keys or tokens are stored in the database or config files.
- **Input validation** — All CLI arguments and file paths are validated.

## Dependencies

SessionLens uses a minimal set of dependencies:
- `click` — CLI framework (widely audited)
- `pydantic` — Data validation (widely used)
- `pyyaml` — YAML parsing (standard library for this use case)
- `tiktoken` — Token counting (OpenAI's official library)
- `sqlite-utils` — SQLite management (lightweight wrapper)

All dependencies are pinned to specific versions to avoid supply-chain attacks via version drift.

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly:
1. Email: [security contact]
2. Do not open a public issue until we've had a chance to address it
3. We aim to respond within 48 hours and release a fix within 2 weeks
