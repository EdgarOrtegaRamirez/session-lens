"""CLI interface for SessionLens."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click
import yaml

from .analyzer import ReportGenerator, SessionAnalyzer
from .models import CodingSession, FileEdit, FileEditType, Message, MessageType, SessionStatus
from .storage import SessionStore


pass_store = click.make_pass_decorator(SessionStore, ensure=True)


def _output_format(ctx: click.Context, param: click.Parameter, value: str | None) -> str:
    """Callback to validate and normalize output format."""
    if value is None:
        return "text"
    if value not in ("text", "json"):
        raise click.BadParameter(f"Unsupported format: {value}. Use 'text' or 'json'.")
    return value


# CLI group
@click.group()
@click.option(
    "--db",
    "db_path",
    default=None,
    help="Path to the SQLite database. Defaults to ~/.session-lens/session-lens.db",
)
@click.pass_context
def main(ctx: click.Context, db_path: str | None) -> None:
    """SessionLens — AI coding session analyzer and optimizer.

    Track, analyze, and optimize your AI-assisted coding sessions.
    """
    ctx.ensure_object(dict)
    store = SessionStore(db_path)
    ctx.obj["store"] = store


# --- START command ---
@main.command()
@click.option("--title", "-t", required=True, help="Session title")
@click.option("--project", "-p", required=True, help="Project path")
@click.option("--model", "-m", default=None, help="AI model used for the session")
@click.option("--tag", "-g", "tags", multiple=True, help="Tags to assign (repeatable)")
@click.option("--notes", "-n", default=None, help="Session notes")
@click.pass_context
def start(ctx: click.Context, title: str, project: str, model: str | None, tags: tuple[str, ...], notes: str | None) -> None:
    """Start a new coding session."""
    store = ctx.obj["store"]
    session = CodingSession(
        title=title,
        project_path=project,
        model=model,
        tags=list(tags),
        notes=notes,
    )
    store.save_session(session)
    click.echo(f"✅ Session started: {session.id}")
    click.echo(f"   Title: {title}")
    click.echo(f"   Project: {project}")
    if model:
        click.echo(f"   Model: {model}")
    if tags:
        click.echo(f"   Tags: {', '.join(tags)}")


# --- STOP command ---
@main.command()
@click.option("--id", "session_id", required=True, help="Session ID to stop")
@click.pass_context
def stop(ctx: click.Context, session_id: str) -> None:
    """Stop an active coding session."""
    store = ctx.obj["store"]
    session = store.get_session(session_id)
    if not session:
        click.echo(f"❌ Session {session_id} not found.", err=True)
        sys.exit(1)

    session.status = SessionStatus.COMPLETED
    import datetime
    session.completed_at = datetime.datetime.now(datetime.timezone.utc)
    store.save_session(session)
    click.echo(f"✅ Session stopped: {session_id}")
    summary = session.compute_summary()
    click.echo(f"   Tokens: {summary.total_tokens:,}")
    click.echo(f"   Messages: {summary.message_count}")
    click.echo(f"   Edits: {summary.file_edits_count}")
    click.echo(f"   Duration: {session.duration_human}")


# --- ADD-MESSAGE command ---
@main.command("add-message")
@click.option("--id", "session_id", required=True, help="Session ID")
@click.option("--type", "msg_type", required=True, type=click.Choice(["prompt", "response", "file_edit", "tool_call", "error", "system"]), help="Message type")
@click.option("--role", "-r", required=True, help="Role (e.g., user, assistant)")
@click.option("--content", "-c", required=True, help="Message content")
@click.option("--tokens", "-n", default=None, type=int, help="Token count")
@click.option("--metadata", "-d", default=None, help="JSON metadata")
@click.pass_context
def add_message(
    ctx: click.Context,
    session_id: str,
    msg_type: str,
    role: str,
    content: str,
    tokens: int | None,
    metadata: str | None,
) -> None:
    """Add a message to an existing session."""
    store = ctx.obj["store"]
    session = store.get_session(session_id)
    if not session:
        click.echo(f"❌ Session {session_id} not found.", err=True)
        sys.exit(1)

    msg = Message(
        message_type=MessageType(msg_type),
        role=role,
        content=content,
        token_count=tokens,
        metadata=json.loads(metadata) if metadata else None,
    )
    session.add_message(msg)
    store.save_session(session)
    click.echo(f"✅ Message added to session {session_id}")


# --- LIST command ---
@main.command()
@click.option("--status", "-s", default=None, help="Filter by status (active, completed, interrupted, errored)")
@click.option("--limit", "-l", default=20, show_default=True, help="Max results")
@click.option("--offset", default=0, show_default=True, help="Offset for pagination")
@click.option("--format", "-f", "fmt", callback=_output_format, default=None, help="Output format (text or json)")
@pass_store
def list_sessions(store: SessionStore, status: str | None, limit: int, offset: int, fmt: str) -> None:
    """List coding sessions."""
    sessions = store.list_sessions(status=status, limit=limit, offset=offset)
    if fmt == "json":
        data = [{
            "id": s.id,
            "title": s.title,
            "status": s.status.value if isinstance(s.status, SessionStatus) else s.status,
            "project_path": s.project_path,
            "model": s.model,
            "tags": s.tags,
            "started_at": s.started_at.isoformat(),
            "duration_human": s.duration_human,
        } for s in sessions]
        click.echo(json.dumps(data, indent=2))
        return

    if not sessions:
        click.echo("No sessions found.")
        return

    click.echo(f"{'ID':<10} {'Title':<40} {'Status':<12} {'Duration':<10} {'Tokens':>10}")
    click.echo("─" * 90)
    for s in sessions:
        summary = s.compute_summary()
        click.echo(
            f"{s.id:<10} {s.title[:39]:<40} {s.status.value:<12} {s.duration_human:<10} {summary.total_tokens:>10,}"
        )


# --- SHOW command ---
@main.command()
@click.argument("session_id")
@click.option("--format", "-f", "fmt", callback=_output_format, default=None, help="Output format (text or json)")
@pass_store
def show(store: SessionStore, session_id: str, fmt: str) -> None:
    """Show a session's details."""
    session = store.get_session(session_id)
    if not session:
        click.echo(f"❌ Session {session_id} not found.", err=True)
        sys.exit(1)

    if fmt == "json":
        click.echo(json.dumps(session.to_dict(), indent=2))
        return

    click.echo(f"Session: {session.title}")
    click.echo(f"ID: {session.id}")
    click.echo(f"Project: {session.project_path}")
    click.echo(f"Status: {session.status.value if isinstance(session.status, SessionStatus) else session.status}")
    click.echo(f"Model: {session.model or 'unknown'}")
    click.echo(f"Started: {session.started_at.isoformat()}")
    if session.completed_at:
        click.echo(f"Completed: {session.completed_at.isoformat()}")
    click.echo(f"Duration: {session.duration_human}")
    if session.tags:
        click.echo(f"Tags: {', '.join(session.tags)}")
    if session.notes:
        click.echo(f"Notes: {session.notes}")

    summary = session.compute_summary()
    click.echo(f"")
    click.echo(f"Tokens: {summary.total_tokens:,} (prompts: {summary.prompt_tokens:,}, responses: {summary.response_tokens:,})")
    click.echo(f"Messages: {summary.message_count}")
    click.echo(f"File edits: {summary.file_edits_count}")

    if summary.files_touched:
        click.echo(f"Files: {', '.join(summary.files_touched[:10])}")
        if len(summary.files_touched) > 10:
            click.echo(f"  ... and {len(summary.files_touched) - 10} more")


# --- ANALYZE command ---
@main.command()
@click.argument("session_id")
@click.option("--format", "-f", "fmt", callback=_output_format, default=None, help="Output format (text or json or markdown)")
@click.pass_context
def analyze(ctx: click.Context, session_id: str, fmt: str) -> None:
    """Analyze a coding session."""
    store = ctx.obj["store"]
    session = store.get_session(session_id)
    if not session:
        click.echo(f"❌ Session {session_id} not found.", err=True)
        sys.exit(1)

    analyzer = SessionAnalyzer()
    analysis = analyzer.analyze_session(session)

    if fmt == "json":
        click.echo(json.dumps(analysis, indent=2))
        return

    generator = ReportGenerator(analyzer)
    if fmt == "markdown":
        click.echo(generator.generate_markdown_report(analysis))
    else:
        click.echo(generator.generate_text_report(analysis))


# --- SEARCH command ---
@main.command()
@click.argument("query")
@click.option("--tag", "-g", "tags", multiple=True, help="Filter by tags (repeatable)")
@click.option("--limit", "-l", default=20, show_default=True, help="Max results")
@click.option("--format", "-f", "fmt", callback=_output_format, default=None, help="Output format (text or json)")
@pass_store
def search(store: SessionStore, query: str, tags: tuple[str, ...], limit: int, fmt: str) -> None:
    """Search sessions by title, notes, or tags."""
    sessions = store.search_sessions(query, tags=list(tags) if tags else None, limit=limit)
    if fmt == "json":
        data = [{
            "id": s.id,
            "title": s.title,
            "status": s.status.value if isinstance(s.status, SessionStatus) else s.status,
            "started_at": s.started_at.isoformat(),
        } for s in sessions]
        click.echo(json.dumps(data, indent=2))
        return

    if not sessions:
        click.echo(f"No sessions found matching '{query}'.")
        return

    click.echo(f"Found {len(sessions)} session(s) matching '{query}':")
    click.echo(f"{'ID':<10} {'Title':<40} {'Started':<22} {'Tags':<30}")
    click.echo("─" * 100)
    for s in sessions:
        tag_str = ", ".join(s.tags[:3])
        click.echo(f"{s.id:<10} {s.title[:39]:<40} {s.started_at.isoformat()[:19]:<22} {tag_str:<30}")


# --- INFO command ---
@main.command()
@click.option("--format", "-f", "fmt", callback=_output_format, default=None, help="Output format (text or json)")
@pass_store
def info(store: SessionStore, fmt: str) -> None:
    """Show aggregate statistics."""
    stats = store.get_stats()

    if fmt == "json":
        click.echo(json.dumps(stats, indent=2))
        return

    click.echo(f"{'='*50}")
    click.echo(f"  SessionLens — Aggregate Statistics")
    click.echo(f"{'='*50}")
    click.echo(f"")
    click.echo(f"Total sessions: {stats['total_sessions']}")
    click.echo(f"Total tokens used: {stats['total_tokens']:,}")

    if stats["status_breakdown"]:
        click.echo(f"")
        click.echo(f"By status:")
        for status, count in stats["status_breakdown"].items():
            click.echo(f"  {status}: {count}")

    if stats["avg_session_duration_seconds"] > 0:
        avg = stats["avg_session_duration_seconds"]
        if avg < 60:
            click.echo(f"Average session duration: {avg:.0f}s")
        else:
            mins = avg / 60
            click.echo(f"Average session duration: {mins:.1f}m")

    if stats["model_usage"]:
        click.echo(f"")
        click.echo(f"Model usage:")
        for model, count in sorted(stats["model_usage"].items(), key=lambda x: -x[1]):
            click.echo(f"  {model}: {count}")

    if stats["top_files"]:
        click.echo(f"")
        click.echo(f"Top files edited:")
        for file in stats["top_files"][:5]:
            click.echo(f"  {file['path']}: {file['edits']} edits")


# --- DELETE command ---
@main.command()
@click.argument("session_id")
@pass_store
def delete(store: SessionStore, session_id: str) -> None:
    """Delete a session."""
    if store.delete_session(session_id):
        click.echo(f"✅ Session {session_id} deleted.")
    else:
        click.echo(f"❌ Session {session_id} not found.", err=True)
        sys.exit(1)


# --- SAMPLE-CONFIG command ---
@main.command()
def sample_config() -> None:
    """Print a sample configuration file."""
    config = {
        "default_db": "~/.session-lens/session-lens.db",
        "default_model": "gpt-4o-mini",
        "max_sessions": 1000,
        "auto_save_interval_seconds": 30,
        "analysis": {
            "token_estimator": "cl100k_base",
            "enable_insights": True,
            "high_token_threshold": 50000,
            "long_session_threshold_seconds": 3600,
        },
        "reporting": {
            "default_format": "text",
            "include_insights": True,
            "max_file_edits_displayed": 50,
        },
    }
    click.echo(yaml.dump(config, default_flow_style=False, sort_keys=False))


# --- INIT command ---
@main.command()
@click.option("--db", "db_path", default=None, help="Custom database path")
def init(db_path: str | None) -> None:
    """Initialize SessionLens database."""
    store = SessionStore(db_path)
    import os
    db_dir = str(store.db_path.parent)
    click.echo(f"✅ SessionLens initialized.")
    click.echo(f"   Database: {store.db_path}")

    # Create sessions directory for JSON backups
    sessions_dir = Path(os.path.expanduser("~/.session-lens/sessions"))
    sessions_dir.mkdir(parents=True, exist_ok=True)
    click.echo(f"   Sessions dir: {sessions_dir}")
