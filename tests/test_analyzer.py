"""Tests for SessionLens analyzer."""

from __future__ import annotations

from datetime import UTC, datetime

from session_lens.analyzer import ReportGenerator, SessionAnalyzer
from session_lens.models import (
    CodingSession,
    FileEdit,
    FileEditType,
    Message,
    MessageType,
)


class TestSessionAnalyzer:
    """Tests for the SessionAnalyzer class."""

    def test_estimate_tokens_empty(self) -> None:
        analyzer = SessionAnalyzer()
        assert analyzer.estimate_tokens("") == 0
        assert analyzer.estimate_tokens(None) == 0  # type: ignore[arg-type]

    def test_estimate_tokens_basic(self) -> None:
        analyzer = SessionAnalyzer()
        tokens = analyzer.estimate_tokens("Hello world, this is a test.")
        assert tokens > 0
        assert tokens < 100

    def test_analyze_simple_prompt(self) -> None:
        analyzer = SessionAnalyzer()
        analysis = analyzer.analyze_prompt("Add a login endpoint")
        assert analysis.intent == "creation"
        assert analysis.complexity == "medium"
        assert analysis.word_count == 4
        assert analysis.length_category == "short"
        assert not analysis.has_code
        assert not analysis.contains_questions

    def test_analyze_code_prompt(self) -> None:
        analyzer = SessionAnalyzer()
        analysis = analyzer.analyze_prompt(
            "Refactor the auth module to use JWT tokens. "
            "Here's the current code:\n```python\ndef login():\n    pass\n```"
        )
        assert analysis.has_code
        assert analysis.complexity == "high"
        assert analysis.intent == "refactoring"

    def test_analyze_question_prompt(self) -> None:
        analyzer = SessionAnalyzer()
        analysis = analyzer.analyze_prompt(
            "How does the authentication middleware work? "
            "What is the token expiration time?"
        )
        assert analysis.contains_questions
        assert analysis.intent == "learning"
        assert analysis.word_count > 10

    def test_analyze_long_prompt(self) -> None:
        analyzer = SessionAnalyzer()
        long_text = " ".join(["word"] * 600)
        analysis = analyzer.analyze_prompt(long_text)
        assert analysis.length_category == "very_long"
        assert analysis.word_count == 600

    def test_analyze_medium_prompt(self) -> None:
        analyzer = SessionAnalyzer()
        medium_text = " ".join(["word"] * 100)
        analysis = analyzer.analyze_prompt(medium_text)
        assert analysis.length_category == "medium"

    def test_analyze_file_reference(self) -> None:
        analyzer = SessionAnalyzer()
        analysis = analyzer.analyze_prompt(
            "Fix the bug in src/auth.py line 42"
        )
        assert analysis.has_files

    def test_analyze_session_basic(self) -> None:
        analyzer = SessionAnalyzer()
        session = CodingSession(
            title="Test session",
            project_path="/tmp/test",
            model="gpt-4o",
            started_at=datetime.now(UTC),
        )
        session.add_message(Message(MessageType.PROMPT, "user", "Add feature", token_count=20))
        session.add_message(Message(MessageType.RESPONSE, "assistant", "Done", token_count=50))
        session.add_file_edit(
            FileEdit("src/main.py", FileEditType.MODIFY, lines_added=10, lines_removed=3)
        )
        session.completed_at = session.started_at

        result = analyzer.analyze_session(session)
        assert result["session_id"] == session.id
        assert result["session_title"] == "Test session"
        assert result["total_tokens"] == 70
        assert result["prompt_count"] == 2
        assert result["file_edits_count"] == 1
        assert len(result["file_analysis"]) == 1
        assert len(result["insights"]) >= 0  # May or may not have insights
        assert result["engagement"]["total_prompts"] == 1

    def test_analyze_session_with_errors(self) -> None:
        analyzer = SessionAnalyzer()
        session = CodingSession(
            title="Error session",
            project_path="/tmp/test",
        )
        session.add_message(Message(MessageType.PROMPT, "user", "Fix bug", token_count=15))
        session.add_message(Message(MessageType.ERROR, "system", "Build failed", token_count=5))
        session.add_message(Message(MessageType.RESPONSE, "assistant", "Fixed", token_count=30))

        result = analyzer.analyze_session(session)
        # PROMPT (15) + RESPONSE (30) = 45; ERROR (5) not counted in total_tokens
        assert result["total_tokens"] == 45
        assert any(i["category"] == "quality" for i in result["insights"])

    def test_analyze_session_high_tokens(self) -> None:
        analyzer = SessionAnalyzer()
        session = CodingSession(
            title="Big session",
            project_path="/tmp/test",
        )
        session.add_message(Message(MessageType.PROMPT, "user", "Do everything", token_count=40000))
        session.add_message(Message(MessageType.RESPONSE, "assistant", "Long response", token_count=20000))

        result = analyzer.analyze_session(session)
        assert result["total_tokens"] == 60000
        assert any(i["category"] == "tokens" for i in result["insights"])

    def test_analyze_session_many_files(self) -> None:
        analyzer = SessionAnalyzer()
        session = CodingSession(
            title="Wide session",
            project_path="/tmp/test",
        )
        for i in range(25):
            session.add_file_edit(
                FileEdit(f"src/module_{i}.py", FileEditType.MODIFY, lines_added=5, lines_removed=2)
            )

        result = analyzer.analyze_session(session)
        assert result["file_edits_count"] == 25
        assert any(i["category"] == "scope" for i in result["insights"])

    def test_analyze_file_edit(self) -> None:
        analyzer = SessionAnalyzer()

        small = analyzer.analyze_file_edit(
            FileEdit("src/small.py", FileEditType.MODIFY, lines_added=5, lines_removed=2)
        )
        assert small["size_impact"] == "small"
        assert small["net_change"] == 3

        large = analyzer.analyze_file_edit(
            FileEdit("src/large.py", FileEditType.MODIFY, lines_added=300, lines_removed=100)
        )
        assert large["size_impact"] == "large"
        assert large["net_change"] == 200

    def test_analyze_empty_session(self) -> None:
        analyzer = SessionAnalyzer()
        session = CodingSession(title="Empty", project_path="/tmp")
        session.completed_at = session.started_at
        result = analyzer.analyze_session(session)
        assert result["total_tokens"] == 0
        assert result["engagement"]["average_length"] == 0
        assert result["engagement"]["length_trend"] == "n/a"


class TestReportGenerator:
    """Tests for the ReportGenerator class."""

    def test_generate_text_report(self) -> None:
        analyzer = SessionAnalyzer()
        session = CodingSession(
            title="Test Report",
            project_path="/tmp/test",
        )
        session.add_message(Message(MessageType.PROMPT, "user", "Add feature", token_count=20))
        session.add_message(Message(MessageType.RESPONSE, "assistant", "Done", token_count=50))
        session.add_file_edit(
            FileEdit("src/main.py", FileEditType.MODIFY, lines_added=10, lines_removed=3)
        )
        session.completed_at = session.started_at

        analysis = analyzer.analyze_session(session)
        generator = ReportGenerator(analyzer)
        report = generator.generate_text_report(analysis)

        assert "Session Lens Report" in report
        assert "Test Report" in report
        assert "70" in report  # total tokens
        assert "src/main.py" in report

    def test_generate_markdown_report(self) -> None:
        analyzer = SessionAnalyzer()
        session = CodingSession(
            title="Markdown Test",
            project_path="/tmp/test",
        )
        session.add_message(Message(MessageType.PROMPT, "user", "Test", token_count=10))
        session.add_message(Message(MessageType.RESPONSE, "assistant", "OK", token_count=20))
        session.completed_at = session.started_at

        analysis = analyzer.analyze_session(session)
        generator = ReportGenerator(analyzer)
        report = generator.generate_markdown_report(analysis)

        assert "# Session Lens Report" in report
        assert "## Markdown Test" in report
        assert "| Metric | Value |" in report

    def test_report_no_insights(self) -> None:
        analyzer = SessionAnalyzer()
        session = CodingSession(
            title="Good session",
            project_path="/tmp/test",
        )
        session.add_message(Message(MessageType.PROMPT, "user", "Add small feature", token_count=10))
        session.add_message(Message(MessageType.RESPONSE, "assistant", "Done", token_count=30))
        session.add_file_edit(
            FileEdit("src/small.py", FileEditType.CREATE, lines_added=5)
        )
        session.completed_at = session.started_at

        analysis = analyzer.analyze_session(session)
        generator = ReportGenerator(analyzer)
        report = generator.generate_text_report(analysis)

        assert "No issues detected" in report
