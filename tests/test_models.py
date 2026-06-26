"""Tests for SessionLens models."""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from session_lens.models import (
    CodingSession,
    FileEdit,
    FileEditType,
    Message,
    MessageType,
    SessionStatus,
    SessionSummary,
)


class TestMessage:
    """Tests for the Message model."""

    def test_create_prompt_message(self) -> None:
        msg = Message(
            message_type=MessageType.PROMPT,
            role="user",
            content="Refactor the auth module",
            token_count=50,
        )
        assert msg.id
        assert msg.type == MessageType.PROMPT
        assert msg.role == "user"
        assert msg.content == "Refactor the auth module"
        assert msg.token_count == 50
        assert msg.timestamp.tzinfo is not None
        assert msg.is_prompt
        assert not msg.is_response

    def test_create_response_message(self) -> None:
        msg = Message(
            message_type=MessageType.RESPONSE,
            role="assistant",
            content="Here's the refactored code...",
            token_count=200,
        )
        assert msg.type == MessageType.RESPONSE
        assert msg.is_response
        assert not msg.is_prompt

    def test_to_dict_and_from_dict(self) -> None:
        msg = Message(
            message_type=MessageType.TOOL_CALL,
            role="system",
            content="Running test",
            metadata={"tool": "pytest", "args": ["-v"]},
            token_count=30,
        )
        data = msg.to_dict()
        assert data["id"] == msg.id
        assert data["type"] == "tool_call"
        assert data["role"] == "system"
        assert data["content"] == "Running test"
        assert data["metadata"] == {"tool": "pytest", "args": ["-v"]}
        assert data["token_count"] == 30

        restored = Message.from_dict(data)
        assert restored.id == msg.id
        assert restored.type == "tool_call"
        assert restored.role == "system"
        assert restored.content == "Running test"
        assert restored.metadata == {"tool": "pytest", "args": ["-v"]}
        assert restored.token_count == 30

    def test_empty_content(self) -> None:
        msg = Message(
            message_type=MessageType.SYSTEM,
            role="system",
            content="",
        )
        assert msg.content == ""

    def test_no_metadata(self) -> None:
        msg = Message(
            message_type=MessageType.PROMPT,
            role="user",
            content="Test",
        )
        assert msg.metadata == {}


class TestFileEdit:
    """Tests for the FileEdit model."""

    def test_create_create_edit(self) -> None:
        edit = FileEdit(
            path="src/auth.py",
            edit_type=FileEditType.CREATE,
            lines_added=50,
            description="Create auth module",
        )
        assert edit.id
        assert edit.path == "src/auth.py"
        assert edit.edit_type == FileEditType.CREATE
        assert edit.lines_added == 50
        assert edit.lines_removed == 0

    def test_to_dict_and_from_dict(self) -> None:
        edit = FileEdit(
            path="src/main.py",
            edit_type=FileEditType.MODIFY,
            lines_added=20,
            lines_removed=10,
            description="Add new feature",
        )
        data = edit.to_dict()
        restored = FileEdit.from_dict(data)
        assert restored.path == edit.path
        assert restored.edit_type == "modify"
        assert restored.lines_added == 20
        assert restored.lines_removed == 10
        assert restored.description == "Add new feature"

    def test_delete_edit(self) -> None:
        edit = FileEdit(
            path="src/old_module.py",
            edit_type=FileEditType.DELETE,
            lines_added=0,
            lines_removed=100,
        )
        assert edit.edit_type == FileEditType.DELETE
        assert edit.lines_removed == 100


class TestSessionSummary:
    """Tests for the SessionSummary model."""

    def test_empty_summary(self) -> None:
        summary = SessionSummary()
        assert summary.total_tokens == 0
        assert summary.message_count == 0
        assert summary.files_touched == []
        assert summary.to_dict() == {
            "total_tokens": 0,
            "prompt_tokens": 0,
            "response_tokens": 0,
            "message_count": 0,
            "file_edits_count": 0,
            "files_touched": [],
            "avg_response_time_ms": 0.0,
            "tool_calls_count": 0,
            "error_count": 0,
        }

    def test_full_summary(self) -> None:
        summary = SessionSummary(
            total_tokens=10000,
            prompt_tokens=5000,
            response_tokens=5000,
            message_count=25,
            file_edits_count=8,
            files_touched=["src/main.py", "src/auth.py"],
            avg_response_time_ms=1200.5,
            tool_calls_count=3,
            error_count=1,
        )
        data = summary.to_dict()
        assert data["total_tokens"] == 10000
        assert data["prompt_tokens"] == 5000
        assert data["files_touched"] == ["src/main.py", "src/auth.py"]


class TestCodingSession:
    """Tests for the CodingSession model."""

    def test_create_session(self) -> None:
        session = CodingSession(
            title="Refactor auth module",
            project_path="/home/user/project",
            model="gpt-4o",
        )
        assert session.id
        assert session.title == "Refactor auth module"
        assert session.project_path == "/home/user/project"
        assert session.model == "gpt-4o"
        assert session.status == SessionStatus.ACTIVE
        assert session.messages == []
        assert session.file_edits == []
        assert session.duration_seconds >= 0

    def test_add_message(self) -> None:
        session = CodingSession(
            title="Test session",
            project_path="/tmp/test",
        )
        msg = Message(
            message_type=MessageType.PROMPT,
            role="user",
            content="Add login endpoint",
            token_count=30,
        )
        added = session.add_message(msg)
        assert added is msg
        assert len(session.messages) == 1
        assert session.messages[0].content == "Add login endpoint"

    def test_add_file_edit(self) -> None:
        session = CodingSession(
            title="Test session",
            project_path="/tmp/test",
        )
        edit = FileEdit(
            path="src/auth.py",
            edit_type=FileEditType.MODIFY,
            lines_added=15,
            lines_removed=5,
        )
        added = session.add_file_edit(edit)
        assert added is edit
        assert len(session.file_edits) == 1

    def test_compute_summary(self) -> None:
        session = CodingSession(
            title="Test session",
            project_path="/tmp/test",
        )
        session.add_message(
            Message(MessageType.PROMPT, "user", "Hello", token_count=10)
        )
        session.add_message(
            Message(MessageType.RESPONSE, "assistant", "Hi there", token_count=20)
        )
        session.add_file_edit(
            FileEdit("src/main.py", FileEditType.MODIFY, lines_added=5, lines_removed=2)
        )
        summary = session.compute_summary()
        assert summary.total_tokens == 30
        assert summary.prompt_tokens == 10
        assert summary.response_tokens == 20
        assert summary.message_count == 2
        assert summary.file_edits_count == 1
        assert "src/main.py" in summary.files_touched

    def test_compute_summary_with_tools_and_errors(self) -> None:
        session = CodingSession(
            title="Test session",
            project_path="/tmp/test",
        )
        session.add_message(Message(MessageType.TOOL_CALL, "system", "run test", token_count=5))
        session.add_message(Message(MessageType.ERROR, "system", "Build failed", token_count=3))
        session.add_message(Message(MessageType.RESPONSE, "assistant", "Fixed it", token_count=15))
        summary = session.compute_summary()
        assert summary.tool_calls_count == 1
        assert summary.error_count == 1
        assert summary.prompt_tokens == 0
        assert summary.response_tokens == 15

    def test_duration_human(self) -> None:
        session = CodingSession(
            title="Short session",
            project_path="/tmp/test",
        )
        session.completed_at = session.started_at  # 0 seconds
        assert session.duration_human == "0s"

        # Simulate 30 seconds
        from datetime import timedelta
        session.completed_at = session.started_at + timedelta(seconds=30)
        assert "30s" in session.duration_human

        # Simulate 90 minutes
        session.completed_at = session.started_at + timedelta(minutes=90)
        assert "1.5h" in session.duration_human

    def test_to_dict_and_from_dict_round_trip(self) -> None:
        now = datetime.now(timezone.utc)
        session = CodingSession(
            title="Round-trip test",
            project_path="/tmp/test",
            model="claude-3",
            tags=["auth", "backend"],
            notes="Test notes",
            started_at=now,
            status=SessionStatus.COMPLETED,
            completed_at=now,
        )
        session.add_message(Message(MessageType.PROMPT, "user", "Test prompt", token_count=10))
        session.add_file_edit(
            FileEdit("src/test.py", FileEditType.CREATE, lines_added=50)
        )
        session.compute_summary()

        data = session.to_dict()
        restored = CodingSession.from_dict(data)

        assert restored.id == session.id
        assert restored.title == "Round-trip test"
        assert restored.project_path == "/tmp/test"
        assert restored.model == "claude-3"
        assert restored.tags == ["auth", "backend"]
        assert restored.notes == "Test notes"
        assert restored.status == "completed"
        assert len(restored.messages) == 1
        assert len(restored.file_edits) == 1
        assert restored.summary.total_tokens == 10

    def test_save_and_load(self, tmp_path: Path) -> None:
        session = CodingSession(
            title="Persistence test",
            project_path="/tmp/test",
            model="gpt-4o-mini",
            tags=["test"],
        )
        session.add_message(Message(MessageType.PROMPT, "user", "Save test", token_count=15))
        session.add_file_edit(
            FileEdit("data/test.txt", FileEditType.CREATE, lines_added=100)
        )
        session.completed_at = datetime.now(timezone.utc)
        session.compute_summary()

        path = tmp_path / "session.json"
        session.save(Path(path))

        loaded = CodingSession.load(Path(path))
        assert loaded.id == session.id
        assert loaded.title == "Persistence test"
        assert loaded.model == "gpt-4o-mini"
        assert len(loaded.messages) == 1
        assert len(loaded.file_edits) == 1
        assert loaded.summary.total_tokens == 15

    def test_tags_and_metadata(self) -> None:
        session = CodingSession(
            title="Metadata test",
            project_path="/tmp/test",
            tags=["frontend", "ui"],
            notes="Testing metadata",
        )
        session.session_metadata["editor"] = "VSCode"
        session.session_metadata["ide_version"] = "1.85.0"

        data = session.to_dict()
        assert data["session_metadata"]["editor"] == "VSCode"
        assert data["tags"] == ["frontend", "ui"]

    def test_empty_session_summary(self) -> None:
        session = CodingSession(title="Empty", project_path="/tmp")
        summary = session.compute_summary()
        assert summary.total_tokens == 0
        assert summary.message_count == 0
        assert summary.file_edits_count == 0
        assert summary.files_touched == []
