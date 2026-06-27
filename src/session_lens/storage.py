"""SQLite-based session storage for SessionLens."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from .models import CodingSession, SessionStatus


class SessionStore:
    """SQLite-backed storage for coding sessions."""

    TABLES = """
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            project_path TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            model TEXT,
            tags TEXT DEFAULT '[]',
            notes TEXT,
            started_at TEXT NOT NULL,
            completed_at TEXT,
            summary_json TEXT,
            session_metadata TEXT DEFAULT '{}'
        );
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            type TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            metadata TEXT DEFAULT '{}',
            token_count INTEGER,
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS file_edits (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            path TEXT NOT NULL,
            edit_type TEXT NOT NULL,
            lines_added INTEGER DEFAULT 0,
            lines_removed INTEGER DEFAULT 0,
            description TEXT,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
        CREATE INDEX IF NOT EXISTS idx_file_edits_session ON file_edits(session_id);
        CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
        CREATE INDEX IF NOT EXISTS idx_sessions_started ON sessions(started_at);
    """

    def __init__(self, db_path: str | Path | None = None):
        if db_path is None:
            import os
            home = os.path.expanduser("~/.session-lens")
            Path(home).mkdir(parents=True, exist_ok=True)
            self.db_path = Path(home) / "session-lens.db"
        else:
            self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(self.TABLES)
            conn.commit()

    def save_session(self, session: CodingSession) -> str:
        """Save or update a coding session. Returns session ID."""
        session.compute_summary()
        with self._connect() as conn:
            # Save session metadata
            conn.execute(
                """INSERT OR REPLACE INTO sessions
                   (id, title, project_path, status, model, tags, notes,
                    started_at, completed_at, summary_json, session_metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    session.id,
                    session.title,
                    session.project_path,
                    session.status.value if isinstance(session.status, SessionStatus) else session.status,
                    session.model,
                    json.dumps(session.tags),
                    session.notes,
                    session.started_at.isoformat(),
                    session.completed_at.isoformat() if session.completed_at else None,
                    json.dumps(session.summary.to_dict()),
                    json.dumps(session.session_metadata),
                ),
            )

            # Delete existing messages and edits (we re-save everything)
            conn.execute("DELETE FROM messages WHERE session_id = ?", (session.id,))
            conn.execute("DELETE FROM file_edits WHERE session_id = ?", (session.id,))

            # Save messages
            for msg in session.messages:
                conn.execute(
                    """INSERT INTO messages
                       (id, session_id, type, role, content, timestamp, metadata, token_count)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        msg.id,
                        session.id,
                        msg.type.value if isinstance(msg.type, str) else msg.type,
                        msg.role,
                        msg.content,
                        msg.timestamp.isoformat(),
                        json.dumps(msg.metadata),
                        msg.token_count,
                    ),
                )

            # Save file edits
            for edit in session.file_edits:
                conn.execute(
                    """INSERT INTO file_edits
                       (id, session_id, path, edit_type, lines_added, lines_removed, description, timestamp)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        edit.id,
                        session.id,
                        edit.path,
                        edit.edit_type.value if isinstance(edit.edit_type, str) else edit.edit_type,
                        edit.lines_added,
                        edit.lines_removed,
                        edit.description,
                        edit.timestamp.isoformat(),
                    ),
                )

            conn.commit()
        return session.id

    def get_session(self, session_id: str) -> CodingSession | None:
        """Retrieve a session by ID."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
            if not row:
                return None

            messages = []
            for msg_row in conn.execute(
                "SELECT * FROM messages WHERE session_id = ?", (session_id,)
            ):
                messages.append({
                    "id": msg_row["id"],
                    "type": msg_row["type"],
                    "role": msg_row["role"],
                    "content": msg_row["content"],
                    "timestamp": msg_row["timestamp"],
                    "metadata": json.loads(msg_row["metadata"]) if msg_row["metadata"] else {},
                    "token_count": msg_row["token_count"],
                })

            edits = []
            for edit_row in conn.execute(
                "SELECT * FROM file_edits WHERE session_id = ?", (session_id,)
            ):
                edits.append({
                    "id": edit_row["id"],
                    "path": edit_row["path"],
                    "edit_type": edit_row["edit_type"],
                    "lines_added": edit_row["lines_added"],
                    "lines_removed": edit_row["lines_removed"],
                    "description": edit_row["description"],
                    "timestamp": edit_row["timestamp"],
                })

            data = dict(row)
            # Rename DB column to match model field name
            if "summary_json" in data:
                data["summary"] = json.loads(data.pop("summary_json"))
            if "session_metadata" in data:
                data["session_metadata"] = json.loads(data["session_metadata"])
            data["messages"] = messages
            data["file_edits"] = edits
            return CodingSession.from_dict(data)

    def list_sessions(
        self,
        status: SessionStatus | str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[CodingSession]:
        """List sessions with optional filtering."""
        query = "SELECT * FROM sessions"
        params: list[Any] = []
        if status:
            query += " WHERE status = ?"
            params.append(status.value if isinstance(status, SessionStatus) else status)
        query += " ORDER BY started_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
            sessions = []
            for row in rows:
                data = dict(row)
                # Fetch related messages and edits
                messages = []
                for msg_row in conn.execute(
                    "SELECT * FROM messages WHERE session_id = ?", (data["id"],)
                ):
                    messages.append({
                        "id": msg_row["id"],
                        "type": msg_row["type"],
                        "role": msg_row["role"],
                        "content": msg_row["content"],
                        "timestamp": msg_row["timestamp"],
                        "metadata": json.loads(msg_row["metadata"]) if msg_row["metadata"] else {},
                        "token_count": msg_row["token_count"],
                    })
                edits = []
                for edit_row in conn.execute(
                    "SELECT * FROM file_edits WHERE session_id = ?", (data["id"],)
                ):
                    edits.append({
                        "id": edit_row["id"],
                        "path": edit_row["path"],
                        "edit_type": edit_row["edit_type"],
                        "lines_added": edit_row["lines_added"],
                        "lines_removed": edit_row["lines_removed"],
                        "description": edit_row["description"],
                        "timestamp": edit_row["timestamp"],
                    })
                data["messages"] = messages
                data["file_edits"] = edits
                # Rename DB columns to match model field names
                if "summary_json" in data:
                    data["summary"] = json.loads(data.pop("summary_json"))
                if "session_metadata" in data:
                    data["session_metadata"] = json.loads(data["session_metadata"])
                sessions.append(CodingSession.from_dict(data))
            return sessions

    def search_sessions(
        self,
        query: str,
        tags: list[str] | None = None,
        limit: int = 50,
    ) -> list[CodingSession]:
        """Search sessions by title, notes, or tags."""
        conditions = []
        params: list[Any] = []

        # Search title and notes
        search_term = f"%{query}%"
        conditions.append("(title LIKE ? OR notes LIKE ?)")
        params.extend([search_term, search_term])

        # Search tags
        if tags:
            tag_conditions = []
            for tag in tags:
                tag_conditions.append("tags LIKE ?")
                params.append(f"%{tag}%")
            conditions.append(f"({' OR '.join(tag_conditions)})")

        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        sql = f"SELECT * FROM sessions{where} ORDER BY started_at DESC LIMIT ?"
        params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
            sessions = []
            for row in rows:
                data = dict(row)
                messages = []
                for msg_row in conn.execute(
                    "SELECT * FROM messages WHERE session_id = ?", (data["id"],)
                ):
                    messages.append({
                        "id": msg_row["id"],
                        "type": msg_row["type"],
                        "role": msg_row["role"],
                        "content": msg_row["content"],
                        "timestamp": msg_row["timestamp"],
                        "metadata": json.loads(msg_row["metadata"]) if msg_row["metadata"] else {},
                        "token_count": msg_row["token_count"],
                    })
                edits = []
                for edit_row in conn.execute(
                    "SELECT * FROM file_edits WHERE session_id = ?", (data["id"],)
                ):
                    edits.append({
                        "id": edit_row["id"],
                        "path": edit_row["path"],
                        "edit_type": edit_row["edit_type"],
                        "lines_added": edit_row["lines_added"],
                        "lines_removed": edit_row["lines_removed"],
                        "description": edit_row["description"],
                        "timestamp": edit_row["timestamp"],
                    })
                data["messages"] = messages
                data["file_edits"] = edits
                # Rename DB columns to match model field names
                if "summary_json" in data:
                    data["summary"] = json.loads(data.pop("summary_json"))
                if "session_metadata" in data:
                    data["session_metadata"] = json.loads(data["session_metadata"])
                sessions.append(CodingSession.from_dict(data))
            return sessions

    def delete_session(self, session_id: str) -> bool:
        """Delete a session and all its data."""
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            conn.commit()
            return cursor.rowcount > 0

    def get_stats(self) -> dict[str, Any]:
        """Get aggregate statistics across all sessions."""
        with self._connect() as conn:
            # Total sessions
            total = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]

            # By status
            status_rows = conn.execute(
                "SELECT status, COUNT(*) as count FROM sessions GROUP BY status"
            ).fetchall()
            status_counts = {row["status"]: row["count"] for row in status_rows}

            # Total tokens
            conn.execute(
                "SELECT COALESCE(SUM(summary_json), '0') as total FROM sessions"
            ).fetchone()
            # Parse from summary_json
            total_tokens = 0
            for row in conn.execute("SELECT summary_json FROM sessions"):
                if row["summary_json"]:
                    try:
                        s = json.loads(row["summary_json"])
                        total_tokens += s.get("total_tokens", 0)
                    except (json.JSONDecodeError, TypeError):
                        pass

            # Average session duration
            avg_duration = conn.execute(
                """SELECT AVG(julianday(completed_at) - julianday(started_at)) * 86400
                   FROM sessions
                   WHERE completed_at IS NOT NULL
                     AND status = 'completed'"""
            ).fetchone()[0] or 0

            # Files touched
            files_rows = conn.execute(
                "SELECT path, COUNT(*) as count FROM file_edits GROUP BY path ORDER BY count DESC LIMIT 10"
            ).fetchall()
            top_files = [{"path": r["path"], "edits": r["count"]} for r in files_rows]

            # Model usage
            model_rows = conn.execute(
                "SELECT model, COUNT(*) as count FROM sessions WHERE model IS NOT NULL GROUP BY model ORDER BY count DESC"
            ).fetchall()
            model_usage = {r["model"]: r["count"] for r in model_rows}

            return {
                "total_sessions": total,
                "status_breakdown": status_counts,
                "total_tokens": total_tokens,
                "avg_session_duration_seconds": avg_duration,
                "top_files": top_files,
                "model_usage": model_usage,
            }
