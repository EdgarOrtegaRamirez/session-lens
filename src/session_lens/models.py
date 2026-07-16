"""Data models for SessionLens sessions."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any


class MessageType(StrEnum):
    """Types of messages in a coding session."""

    PROMPT = "prompt"
    RESPONSE = "response"
    FILE_EDIT = "file_edit"
    TOOL_CALL = "tool_call"
    ERROR = "error"
    SYSTEM = "system"


class FileEditType(StrEnum):
    """Types of file edits."""

    CREATE = "create"
    MODIFY = "modify"
    DELETE = "delete"
    RENAME = "rename"


class SessionStatus(StrEnum):
    """Status of a coding session."""

    ACTIVE = "active"
    COMPLETED = "completed"
    INTERRUPTED = "interrupted"
    ERRORED = "errored"


class Message:
    """A single message in a coding session."""

    __slots__ = (
        "id",
        "type",
        "role",
        "content",
        "timestamp",
        "metadata",
        "token_count",
    )

    def __init__(
        self,
        message_type: MessageType,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
        token_count: int | None = None,
    ):
        self.id: str = str(uuid.uuid4())[:8]
        self.type: MessageType = message_type
        self.role: str = role
        self.content: str = content
        self.timestamp: datetime = datetime.now(UTC)
        self.metadata: dict[str, Any] = metadata or {}
        self.token_count: int | None = token_count

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value if isinstance(self.type, MessageType) else self.type,
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
            "token_count": self.token_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Message:
        msg = cls.__new__(cls)
        msg.id = data["id"]
        msg_type = data["type"]
        msg.type = MessageType(msg_type) if isinstance(msg_type, str) else msg_type
        msg.role = data["role"]
        msg.content = data["content"]
        msg.timestamp = datetime.fromisoformat(data["timestamp"])
        msg.metadata = data.get("metadata", {})
        msg.token_count = data.get("token_count")
        return msg

    @property
    def is_prompt(self) -> bool:
        return self.type == MessageType.PROMPT

    @property
    def is_response(self) -> bool:
        return self.type == MessageType.RESPONSE


class FileEdit:
    """Track a file edit made during a session."""

    def __init__(
        self,
        path: str,
        edit_type: FileEditType,
        lines_added: int = 0,
        lines_removed: int = 0,
        description: str | None = None,
    ):
        self.id: str = str(uuid.uuid4())[:8]
        self.path: str = path
        self.edit_type: FileEditType = edit_type
        self.lines_added: int = lines_added
        self.lines_removed: int = lines_removed
        self.description: str | None = description
        self.timestamp: datetime = datetime.now(UTC)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "path": self.path,
            "edit_type": self.edit_type.value
            if isinstance(self.edit_type, FileEditType)
            else self.edit_type,
            "lines_added": self.lines_added,
            "lines_removed": self.lines_removed,
            "description": self.description,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FileEdit:
        edit = cls.__new__(cls)
        edit.id = data["id"]
        edit.path = data["path"]
        edit_type = data["edit_type"]
        edit.edit_type = FileEditType(edit_type) if isinstance(edit_type, str) else edit_type
        edit.lines_added = data.get("lines_added", 0)
        edit.lines_removed = data.get("lines_removed", 0)
        edit.description = data.get("description")
        edit.timestamp = datetime.fromisoformat(data["timestamp"])
        return edit


class SessionSummary:
    """Summary statistics for a coding session."""

    def __init__(
        self,
        total_tokens: int = 0,
        prompt_tokens: int = 0,
        response_tokens: int = 0,
        message_count: int = 0,
        file_edits_count: int = 0,
        files_touched: list[str] | None = None,
        avg_response_time_ms: float = 0.0,
        tool_calls_count: int = 0,
        error_count: int = 0,
    ):
        self.total_tokens: int = total_tokens
        self.prompt_tokens: int = prompt_tokens
        self.response_tokens: int = response_tokens
        self.message_count: int = message_count
        self.file_edits_count: int = file_edits_count
        self.files_touched: list[str] = files_touched or []
        self.avg_response_time_ms: float = avg_response_time_ms
        self.tool_calls_count: int = tool_calls_count
        self.error_count: int = error_count

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_tokens": self.total_tokens,
            "prompt_tokens": self.prompt_tokens,
            "response_tokens": self.response_tokens,
            "message_count": self.message_count,
            "file_edits_count": self.file_edits_count,
            "files_touched": self.files_touched,
            "avg_response_time_ms": self.avg_response_time_ms,
            "tool_calls_count": self.tool_calls_count,
            "error_count": self.error_count,
        }


class CodingSession:
    """A complete AI coding session with messages, edits, and metadata."""

    def __init__(
        self,
        title: str,
        project_path: str,
        session_id: str | None = None,
        status: SessionStatus = SessionStatus.ACTIVE,
        model: str | None = None,
        tags: list[str] | None = None,
        notes: str | None = None,
        messages: list[Message] | None = None,
        file_edits: list[FileEdit] | None = None,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
    ):
        self.id: str = session_id or str(uuid.uuid4())[:8]
        self.title: str = title
        self.project_path: str = project_path
        self.status: SessionStatus = status
        self.model: str | None = model
        self.tags: list[str] = tags or []
        self.notes: str | None = notes
        self.messages: list[Message] = messages or []
        self.file_edits: list[FileEdit] = file_edits or []
        self.started_at: datetime = started_at or datetime.now(UTC)
        self.completed_at: datetime | None = completed_at
        self.summary: SessionSummary = SessionSummary()
        self.session_metadata: dict[str, Any] = {}

    @property
    def duration_seconds(self) -> float:
        end = self.completed_at or datetime.now(UTC)
        return (end - self.started_at).total_seconds()

    @property
    def duration_human(self) -> str:
        secs = self.duration_seconds
        if secs < 60:
            return f"{secs:.0f}s"
        mins = secs / 60
        if mins < 60:
            return f"{mins:.1f}m"
        hours = mins / 60
        return f"{hours:.1f}h"

    def add_message(self, message: Message) -> Message:
        self.messages.append(message)
        return message

    def add_file_edit(self, edit: FileEdit) -> FileEdit:
        self.file_edits.append(edit)
        return edit

    def compute_summary(self) -> SessionSummary:
        prompt_tokens = sum(
            m.token_count for m in self.messages if m.type == MessageType.PROMPT and m.token_count
        )
        response_tokens = sum(
            m.token_count for m in self.messages if m.type == MessageType.RESPONSE and m.token_count
        )
        tool_calls = sum(1 for m in self.messages if m.type == MessageType.TOOL_CALL)
        errors = sum(1 for m in self.messages if m.type == MessageType.ERROR)
        files = list(set(e.path for e in self.file_edits))
        self.summary = SessionSummary(
            total_tokens=prompt_tokens + response_tokens,
            prompt_tokens=prompt_tokens,
            response_tokens=response_tokens,
            message_count=len(self.messages),
            file_edits_count=len(self.file_edits),
            files_touched=files,
            tool_calls_count=tool_calls,
            error_count=errors,
        )
        return self.summary

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "project_path": self.project_path,
            "status": self.status.value if isinstance(self.status, SessionStatus) else self.status,
            "model": self.model,
            "tags": self.tags,
            "notes": self.notes,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_human": self.duration_human,
            "messages": [m.to_dict() for m in self.messages],
            "file_edits": [e.to_dict() for e in self.file_edits],
            "summary": self.summary.to_dict(),
            "session_metadata": self.session_metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CodingSession:
        session = cls.__new__(cls)
        session.id = data["id"]
        session.title = data["title"]
        session.project_path = data["project_path"]
        status = data["status"]
        session.status = SessionStatus(status) if isinstance(status, str) else status
        session.model = data.get("model")
        tags = data.get("tags", [])
        if isinstance(tags, str):
            tags = json.loads(tags)
        session.tags = tags
        session.notes = data.get("notes")
        session.started_at = datetime.fromisoformat(data["started_at"])
        completed = data.get("completed_at")
        session.completed_at = datetime.fromisoformat(completed) if completed else None
        session.messages = [Message.from_dict(m) for m in data.get("messages", [])]
        session.file_edits = [FileEdit.from_dict(e) for e in data.get("file_edits", [])]
        summary_data = data.get("summary", {})
        session.summary = SessionSummary(
            total_tokens=summary_data.get("total_tokens", 0),
            prompt_tokens=summary_data.get("prompt_tokens", 0),
            response_tokens=summary_data.get("response_tokens", 0),
            message_count=summary_data.get("message_count", 0),
            file_edits_count=summary_data.get("file_edits_count", 0),
            files_touched=summary_data.get("files_touched", []),
            avg_response_time_ms=summary_data.get("avg_response_time_ms", 0.0),
            tool_calls_count=summary_data.get("tool_calls_count", 0),
            error_count=summary_data.get("error_count", 0),
        )
        session.session_metadata = data.get("session_metadata", {})
        return session

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(self.to_dict(), indent=2))

    @classmethod
    def load(cls, path: Path) -> CodingSession:
        return cls.from_dict(json.loads(path.read_text()))
