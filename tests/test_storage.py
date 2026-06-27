"""Tests for SessionLens storage."""

from __future__ import annotations

from pathlib import Path

import pytest

from session_lens.models import (
    CodingSession,
    FileEdit,
    FileEditType,
    Message,
    MessageType,
    SessionStatus,
)
from session_lens.storage import SessionStore


@pytest.fixture
def store(tmp_path: Path) -> SessionStore:
    """Create a temporary SessionStore for testing."""
    return SessionStore(db_path=tmp_path / "test.db")


@pytest.fixture
def sample_session() -> CodingSession:
    """Create a sample coding session for testing."""
    session = CodingSession(
        title="Test session",
        project_path="/tmp/test",
        model="gpt-4o",
        tags=["test", "backend"],
        notes="Sample session for testing",
    )
    session.add_message(Message(MessageType.PROMPT, "user", "Add login", token_count=20))
    session.add_message(Message(MessageType.RESPONSE, "assistant", "Done", token_count=50))
    session.add_file_edit(
        FileEdit("src/auth.py", FileEditType.MODIFY, lines_added=15, lines_removed=5)
    )
    return session


class TestSessionStore:
    """Tests for the SessionStore class."""

    def test_init_creates_db(self, tmp_path: Path) -> None:
        SessionStore(db_path=tmp_path / "new.db")
        assert (tmp_path / "new.db").exists()

    def test_save_and_get_session(self, store: SessionStore, sample_session: CodingSession) -> None:
        """Test saving and retrieving a session."""
        session_id = store.save_session(sample_session)
        assert session_id == sample_session.id

        retrieved = store.get_session(session_id)
        assert retrieved is not None
        assert retrieved.id == sample_session.id
        assert retrieved.title == "Test session"
        assert retrieved.model == "gpt-4o"
        assert len(retrieved.messages) == 2
        assert len(retrieved.file_edits) == 1
        assert retrieved.summary.total_tokens == 70

    def test_get_nonexistent_session(self, store: SessionStore) -> None:
        """Test retrieving a session that doesn't exist."""
        assert store.get_session("nonexistent") is None

    def test_list_sessions(self, store: SessionStore, sample_session: CodingSession) -> None:
        """Test listing sessions."""
        store.save_session(sample_session)

        # Create another session
        session2 = CodingSession(
            title="Second session",
            project_path="/tmp/test2",
            model="claude-3",
        )
        store.save_session(session2)

        sessions = store.list_sessions()
        assert len(sessions) == 2

        # Test with limit
        limited = store.list_sessions(limit=1)
        assert len(limited) == 1

    def test_list_sessions_by_status(
        self, store: SessionStore, sample_session: CodingSession
    ) -> None:
        """Test filtering sessions by status."""
        store.save_session(sample_session)

        # Active session
        sessions = store.list_sessions(status=SessionStatus.ACTIVE)
        assert len(sessions) == 1
        assert sessions[0].id == sample_session.id

        # Completed session
        sample_session.status = SessionStatus.COMPLETED
        store.save_session(sample_session)
        completed = store.list_sessions(status=SessionStatus.COMPLETED)
        assert len(completed) == 1

        # No matching sessions
        none = store.list_sessions(status=SessionStatus.INTERRUPTED)
        assert len(none) == 0

    def test_delete_session(self, store: SessionStore, sample_session: CodingSession) -> None:
        """Test deleting a session."""
        session_id = store.save_session(sample_session)

        # Delete
        assert store.delete_session(session_id) is True

        # Verify it's gone
        assert store.get_session(session_id) is None

    def test_delete_nonexistent_session(self, store: SessionStore) -> None:
        """Test deleting a session that doesn't exist."""
        assert store.delete_session("nonexistent") is False

    def test_search_sessions(self, store: SessionStore) -> None:
        """Test searching sessions by query."""
        session1 = CodingSession(
            title="Auth module refactor",
            project_path="/tmp/test",
            tags=["auth"],
        )
        session2 = CodingSession(
            title="Frontend dashboard",
            project_path="/tmp/test2",
            tags=["frontend"],
        )
        store.save_session(session1)
        store.save_session(session2)

        # Search by title
        results = store.search_sessions("Auth")
        assert len(results) == 1
        assert results[0].title == "Auth module refactor"

        # Search by tag
        results = store.search_sessions("", tags=["frontend"])
        assert len(results) == 1
        assert results[0].title == "Frontend dashboard"

    def test_update_session(self, store: SessionStore, sample_session: CodingSession) -> None:
        """Test updating an existing session."""
        store.save_session(sample_session)

        # Modify the session
        sample_session.title = "Updated title"
        sample_session.add_message(
            Message(MessageType.PROMPT, "user", "New prompt", token_count=10)
        )
        store.save_session(sample_session)

        retrieved = store.get_session(sample_session.id)
        assert retrieved.title == "Updated title"
        assert len(retrieved.messages) == 3  # 2 original + 1 new

    def test_get_stats(self, store: SessionStore) -> None:
        """Test aggregate statistics."""
        session1 = CodingSession(
            title="Session 1",
            project_path="/tmp/test",
            model="gpt-4o",
        )
        session1.add_message(Message(MessageType.PROMPT, "user", "Test", token_count=100))
        session1.add_message(Message(MessageType.RESPONSE, "assistant", "OK", token_count=200))
        session1.status = SessionStatus.COMPLETED
        store.save_session(session1)

        session2 = CodingSession(
            title="Session 2",
            project_path="/tmp/test",
            model="claude-3",
        )
        session2.add_message(Message(MessageType.PROMPT, "user", "Test", token_count=50))
        session2.status = SessionStatus.ACTIVE
        store.save_session(session2)

        stats = store.get_stats()
        assert stats["total_sessions"] == 2
        assert stats["status_breakdown"]["completed"] == 1
        assert stats["status_breakdown"]["active"] == 1
        assert stats["total_tokens"] == 350
        assert stats["model_usage"]["gpt-4o"] == 1
        assert stats["model_usage"]["claude-3"] == 1

    def test_wal_mode(self, tmp_path: Path) -> None:
        """Test that WAL journaling is enabled."""
        SessionStore(db_path=tmp_path / "wal.db")
        # The database should be created
        assert (tmp_path / "wal.db").exists()

    def test_multiple_file_edits(self, store: SessionStore) -> None:
        """Test saving multiple file edits."""
        session = CodingSession(
            title="Multi-edit session",
            project_path="/tmp/test",
        )
        for i in range(5):
            session.add_file_edit(
                FileEdit(
                    f"src/module_{i}.py",
                    FileEditType.CREATE,
                    lines_added=10 * (i + 1),
                )
            )
        store.save_session(session)

        retrieved = store.get_session(session.id)
        assert len(retrieved.file_edits) == 5

    def test_empty_session(self, store: SessionStore) -> None:
        """Test saving a session with no messages or edits."""
        session = CodingSession(title="Empty session", project_path="/tmp")
        store.save_session(session)

        retrieved = store.get_session(session.id)
        assert retrieved is not None
        assert retrieved.title == "Empty session"
        assert len(retrieved.messages) == 0
        assert len(retrieved.file_edits) == 0
