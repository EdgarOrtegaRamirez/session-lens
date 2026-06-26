"""Session analysis engine — extract insights from coding sessions."""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import tiktoken

from .models import (
    CodingSession,
    FileEdit,
    FileEditType,
    Message,
    MessageType,
)


@dataclass
class PromptAnalysis:
    """Analysis of a prompt's characteristics."""

    complexity: str = "low"
    word_count: int = 0
    token_estimate: int = 0
    has_code: bool = False
    has_files: bool = False
    intent: str = "unknown"
    length_category: str = "short"
    contains_questions: bool = False


@dataclass
class SessionInsight:
    """A single insight derived from session analysis."""

    category: str
    severity: str  # "info", "warning", "suggestion"
    message: str
    details: str = ""


@dataclass
class ProductivityMetric:
    """Productivity measurement for a session."""

    net_lines_added: int = 0
    net_lines_removed: int = 0
    files_changed: int = 0
    edits_per_minute: float = 0.0
    tokens_per_line: float = 0.0
    error_rate: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "net_lines_added": self.net_lines_added,
            "net_lines_removed": self.net_lines_removed,
            "files_changed": self.files_changed,
            "edits_per_minute": self.edits_per_minute,
            "tokens_per_line": self.tokens_per_line,
            "error_rate": self.error_rate,
        }


class SessionAnalyzer:
    """Analyzes coding sessions to extract patterns, insights, and metrics."""

    # Complexity indicators
    COMPLEXITY_PATTERNS = [
        (r"\b(refactor|restructure|redesign|migrate|rewrite)\b", "high"),
        (r"\b(architecture|design.*pattern|clean.*code| SOLID)\b", "high"),
        (r"\b(debug|fix.*bug|error.*handling|race.*condition|memory)\b", "medium"),
        (r"\b(add|implement|create|build)\b", "medium"),
        (r"\b(explain|what.*do|how.*works)\b", "low"),
    ]

    # Intent detection patterns
    INTENT_PATTERNS = [
        (r"\b(want|need|require|should|please|could you|can you)\b.*\b(create|implement|build|add|write|make)\b", "creation"),
        (r"\b(create|implement|build|add|write|make)\b.*\b(endpoint|feature|module|function|class)\b", "creation"),
        (r"\b(fix|resolve|patch|correct)\b.*\b(bug|error|issue|problem)\b", "debugging"),
        (r"\b(refactor|restructure|improve)\b", "refactoring"),
        (r"\b(explain|teach|show.*how|what.*is)\b", "learning"),
        (r"\b(write.*test|test.*case|spec|assert)\b", "testing"),
        (r"\b(document|docstring|comment|readme)\b", "documentation"),
        (r"\b(code.*review|review.*code|pr|pull.*request)\b", "code_review"),
        (r"\b(migrate|migrate.*from|migrate.*to)\b", "migration"),
    ]

    def __init__(self, encoding_name: str = "cl100k_base"):
        try:
            self._encoder = tiktoken.get_encoding(encoding_name)
        except Exception:
            self._encoder = tiktoken.get_encoding("r50k_base")

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for a text string."""
        if not text:
            return 0
        return len(self._encoder.encode(text))

    def analyze_prompt(self, prompt: str) -> PromptAnalysis:
        """Analyze a prompt for complexity, intent, and characteristics."""
        analysis = PromptAnalysis(
            word_count=len(prompt.split()),
            token_estimate=self.estimate_tokens(prompt),
            has_code=bool(re.search(r"```|<code>|/\*|function |def |class |import ", prompt)),
            has_files=bool(re.search(r"\.(py|js|ts|go|rs|md|json|yaml|yml|toml|txt|css|html)", prompt)),
            contains_questions=bool(re.search(r"\?", prompt)),
        )

        # Detect intent
        for pattern, intent in self.INTENT_PATTERNS:
            if re.search(pattern, prompt, re.IGNORECASE):
                analysis.intent = intent
                break

        # Detect complexity
        for pattern, complexity in self.COMPLEXITY_PATTERNS:
            if re.search(pattern, prompt, re.IGNORECASE):
                analysis.complexity = complexity
                break

        # Classify length
        word_count = analysis.word_count
        if word_count > 500:
            analysis.length_category = "very_long"
        elif word_count > 200:
            analysis.length_category = "long"
        elif word_count > 50:
            analysis.length_category = "medium"
        else:
            analysis.length_category = "short"

        return analysis

    def analyze_file_edit(self, edit: FileEdit) -> dict[str, Any]:
        """Analyze a file edit for patterns."""
        net_change = edit.lines_added - edit.lines_removed
        total_change = edit.lines_added + edit.lines_removed

        size_impact = "none"
        if total_change > 200:
            size_impact = "large"
        elif total_change > 50:
            size_impact = "moderate"
        elif total_change > 0:
            size_impact = "small"

        return {
            "path": edit.path,
            "edit_type": edit.edit_type,
            "lines_added": edit.lines_added,
            "lines_removed": edit.lines_removed,
            "net_change": net_change,
            "total_change": total_change,
            "size_impact": size_impact,
        }

    def analyze_session(self, session: CodingSession) -> dict[str, Any]:
        """Perform a full analysis of a coding session."""
        session.compute_summary()

        # Analyze prompts
        prompts = [m for m in session.messages if m.type == MessageType.PROMPT]
        analyses = [self.analyze_prompt(m.content) for m in prompts]

        # Calculate productivity metrics
        metrics = self._calculate_productivity(session)

        # Generate insights
        insights = self._generate_insights(session, analyses, metrics)

        # Calculate engagement pattern
        engagement = self._analyze_engagement(session, analyses)

        return {
            "session_id": session.id,
            "session_title": session.title,
            "duration_seconds": session.duration_seconds,
            "duration_human": session.duration_human,
            "total_tokens": session.summary.total_tokens,
            "prompt_count": session.summary.message_count,
            "file_edits_count": session.summary.file_edits_count,
            "files_touched": session.summary.files_touched,
            "productivity": metrics.to_dict(),
            "prompt_analysis": {
                "average_complexity": self._avg_complexity([a.complexity for a in analyses]),
                "dominant_intent": self._mode_intent([a.intent for a in analyses]),
                "average_token_estimate": statistics.mean(
                    [a.token_estimate for a in analyses]
                ) if analyses else 0,
                "prompts_with_code": sum(1 for a in analyses if a.has_code),
                "prompts_with_questions": sum(1 for a in analyses if a.contains_questions),
                "length_distribution": self._length_distribution(analyses),
            },
            "file_analysis": [
                self.analyze_file_edit(e) for e in session.file_edits
            ],
            "insights": [
                {"category": i.category, "severity": i.severity, "message": i.message, "details": i.details}
                for i in insights
            ],
            "engagement": engagement,
        }

    def _calculate_productivity(self, session: CodingSession) -> ProductivityMetric:
        """Calculate productivity metrics for a session."""
        total_added = sum(e.lines_added for e in session.file_edits)
        total_removed = sum(e.lines_removed for e in session.file_edits)
        duration_min = session.duration_seconds / 60 if session.duration_seconds > 0 else 1

        return ProductivityMetric(
            net_lines_added=total_added - total_removed,
            net_lines_removed=total_removed,
            files_changed=len(set(e.path for e in session.file_edits)),
            edits_per_minute=len(session.file_edits) / duration_min if duration_min > 0 else 0,
            tokens_per_line=(
                session.summary.total_tokens / max(total_added, 1)
            ),
            error_rate=0,
        )

    def _generate_insights(
        self,
        session: CodingSession,
        prompt_analyses: list[PromptAnalysis],
        metrics: ProductivityMetric,
    ) -> list[SessionInsight]:
        """Generate insights from session data."""
        insights: list[SessionInsight] = []

        # High token usage insight
        if session.summary.total_tokens > 50000:
            insights.append(SessionInsight(
                category="tokens",
                severity="warning",
                message="High token usage detected",
                details=f"Session used {session.summary.total_tokens:,} tokens. Consider breaking this task into smaller sessions.",
            ))

        # Low productivity insight
        if metrics.edits_per_minute < 0.1 and session.duration_seconds > 300:
            insights.append(SessionInsight(
                category="productivity",
                severity="suggestion",
                message="Low edit rate detected",
                details=f"Only {metrics.edits_per_minute:.2f} edits/min. Review if the AI is taking too long to produce useful changes.",
            ))

        # Excessive file touching
        files_touched = session.summary.files_touched
        if len(files_touched) > 20:
            insights.append(SessionInsight(
                category="scope",
                severity="warning",
                message="Many files touched in session",
                details=f"Session modified {len(files_touched)} files. Consider if the task scope should be narrowed.",
            ))

        # Code prompt ratio
        prompts_with_code = sum(1 for a in prompt_analyses if a.has_code)
        if prompts_with_code > 0 and len(prompt_analyses) > 0:
            ratio = prompts_with_code / len(prompt_analyses)
            if ratio > 0.8:
                insights.append(SessionInsight(
                    category="prompts",
                    severity="info",
                    message="High code prompt ratio",
                    details=f"{prompts_with_code}/{len(prompt_analyses)} prompts include code. Consider including code context upfront.",
                ))

        # Session duration insight
        if session.duration_seconds > 3600:
            insights.append(SessionInsight(
                category="duration",
                severity="warning",
                message="Very long session detected",
                details=f"Session lasted {session.duration_human}. Consider breaking into focused, shorter sessions.",
            ))

        # Error rate insight
        if session.summary.error_count > 0:
            error_ratio = session.summary.error_count / max(session.summary.message_count, 1)
            if error_ratio > 0.1:
                insights.append(SessionInsight(
                    category="quality",
                    severity="warning",
                    message=f"Error rate: {error_ratio:.0%}",
                    details=f"Session had {session.summary.error_count} errors out of {session.summary.message_count} messages.",
                ))

        return insights

    def _analyze_engagement(
        self,
        session: CodingSession,
        analyses: list[PromptAnalysis],
    ) -> dict[str, Any]:
        """Analyze user engagement pattern during a session."""
        if not analyses:
            return {"average_length": 0, "length_trend": "n/a", "question_ratio": 0}

        word_counts = [a.word_count for a in analyses]
        question_count = sum(1 for a in analyses if a.contains_questions)

        # Simple trend detection
        if len(word_counts) >= 3:
            first_half = statistics.mean(word_counts[:len(word_counts)//2])
            second_half = statistics.mean(word_counts[len(word_counts)//2:])
            if second_half > first_half * 1.2:
                trend = "increasing"
            elif second_half < first_half * 0.8:
                trend = "decreasing"
            else:
                trend = "stable"
        else:
            trend = "insufficient_data"

        return {
            "average_length": statistics.mean(word_counts) if word_counts else 0,
            "length_trend": trend,
            "question_ratio": question_count / max(len(analyses), 1),
            "total_prompts": len(analyses),
        }

    @staticmethod
    def _avg_complexity(complexities: list[str]) -> str:
        """Return the most common complexity level."""
        counts: dict[str, int] = {}
        for c in complexities:
            counts[c] = counts.get(c, 0) + 1
        if not counts:
            return "n/a"
        return max(counts, key=counts.get)

    @staticmethod
    def _mode_intent(intents: list[str]) -> str:
        """Return the most common intent."""
        counts: dict[str, int] = {}
        for i in intents:
            counts[i] = counts.get(i, 0) + 1
        if not counts:
            return "n/a"
        return max(counts, key=counts.get)

    @staticmethod
    def _length_distribution(analyses: list[PromptAnalysis]) -> dict[str, int]:
        """Count prompts by length category."""
        dist: dict[str, int] = {"short": 0, "medium": 0, "long": 0, "very_long": 0}
        for a in analyses:
            dist[a.length_category] = dist.get(a.length_category, 0) + 1
        return dist


class ReportGenerator:
    """Generate human-readable reports from session analysis."""

    def __init__(self, analyzer: SessionAnalyzer | None = None):
        self.analyzer = analyzer or SessionAnalyzer()

    def generate_text_report(self, analysis: dict[str, Any]) -> str:
        """Generate a text report from analysis results."""
        lines: list[str] = []

        lines.append(f"{'='*60}")
        lines.append(f"Session Lens Report")
        lines.append(f"{'='*60}")
        lines.append(f"Session: {analysis['session_title']}")
        lines.append(f"ID: {analysis['session_id']}")
        lines.append(f"Duration: {analysis['duration_human']} ({analysis['duration_seconds']:.0f}s)")
        lines.append(f"")

        # Token stats
        lines.append(f"{'─'*40}")
        lines.append(f"Token Usage")
        lines.append(f"{'─'*40}")
        lines.append(f"Total tokens: {analysis['total_tokens']:,}")
        lines.append(f"Messages: {analysis['prompt_count']}")
        lines.append(f"")

        # Productivity
        lines.append(f"{'─'*40}")
        lines.append(f"Productivity")
        lines.append(f"{'─'*40}")
        prod = analysis.get("productivity", {})
        lines.append(f"Net lines added: {prod.get('net_lines_added', 0):+,}")
        lines.append(f"Lines removed: {prod.get('net_lines_removed', 0):+,}")
        lines.append(f"Files changed: {prod.get('files_changed', 0)}")
        lines.append(f"Edits per minute: {prod.get('edits_per_minute', 0):.2f}")
        lines.append(f"Tokens per line: {prod.get('tokens_per_line', 0):.1f}")
        lines.append(f"")

        # Files touched
        files = analysis.get("files_touched", [])
        if files:
            lines.append(f"{'─'*40}")
            lines.append(f"Files ({len(files)})")
            lines.append(f"{'─'*40}")
            for f_path in files[:20]:
                lines.append(f"  • {f_path}")
            if len(files) > 20:
                lines.append(f"  ... and {len(files) - 20} more")
            lines.append(f"")

        # File edits detail
        edits = analysis.get("file_analysis", [])
        if edits:
            lines.append(f"{'─'*40}")
            lines.append(f"File Edits Detail")
            lines.append(f"{'─'*40}")
            for edit in edits[:15]:
                lines.append(
                    f"  {edit['edit_type']:8s}  {edit['path']:30s}  "
                    f"+{edit['lines_added']} -{edit['lines_removed']}  "
                    f"[{edit['size_impact']}]"
                )
            lines.append(f"")

        # Prompt analysis
        prompt_info = analysis.get("prompt_analysis", {})
        lines.append(f"{'─'*40}")
        lines.append(f"Prompt Analysis")
        lines.append(f"{'─'*40}")
        lines.append(f"Average complexity: {prompt_info.get('average_complexity', 'n/a')}")
        lines.append(f"Dominant intent: {prompt_info.get('dominant_intent', 'n/a')}")
        lines.append(f"Avg token estimate: {prompt_info.get('average_token_estimate', 0):.0f}")
        lines.append(f"Prompts with code: {prompt_info.get('prompts_with_code', 0)}")
        lines.append(f"Prompts with questions: {prompt_info.get('prompts_with_questions', 0)}")
        dist = prompt_info.get("length_distribution", {})
        lines.append(f"Length distribution: short={dist.get('short', 0)}, medium={dist.get('medium', 0)}, long={dist.get('long', 0)}, very_long={dist.get('very_long', 0)}")
        lines.append(f"")

        # Engagement
        engagement = analysis.get("engagement", {})
        lines.append(f"{'─'*40}")
        lines.append(f"Engagement")
        lines.append(f"{'─'*40}")
        lines.append(f"Avg prompt length: {engagement.get('average_length', 0):.0f} words")
        lines.append(f"Length trend: {engagement.get('length_trend', 'n/a')}")
        lines.append(f"Question ratio: {engagement.get('question_ratio', 0):.0%}")
        lines.append(f"")

        # Insights
        insights = analysis.get("insights", [])
        if insights:
            lines.append(f"{'─'*40}")
            lines.append(f"Insights")
            lines.append(f"{'─'*40}")
            for insight in insights:
                icon = {"info": "ℹ", "warning": "⚠", "suggestion": "💡"}.get(
                    insight["severity"], "•"
                )
                lines.append(f"  {icon} [{insight['severity'].upper():9s}] {insight['message']}")
                if insight.get("details"):
                    lines.append(f"     {insight['details']}")
            lines.append(f"")
        else:
            lines.append(f"{'─'*40}")
            lines.append(f"Insights")
            lines.append(f"{'─'*40}")
            lines.append(f"  ✅ No issues detected — session looks good!")
            lines.append(f"")

        lines.append(f"{'='*60}")
        return "\n".join(lines)

    def generate_markdown_report(self, analysis: dict[str, Any]) -> str:
        """Generate a markdown report from analysis results."""
        lines: list[str] = []

        lines.append(f"# Session Lens Report")
        lines.append(f"")
        lines.append(f"## {analysis['session_title']}")
        lines.append(f"- **Session ID:** `{analysis['session_id']}`")
        lines.append(f"- **Duration:** {analysis['duration_human']} ({analysis['duration_seconds']:.0f}s)")
        lines.append(f"- **Total Tokens:** {analysis['total_tokens']:,}")
        lines.append(f"- **Messages:** {analysis['prompt_count']}")
        lines.append(f"")

        # Productivity
        prod = analysis.get("productivity", {})
        lines.append(f"## Productivity Metrics")
        lines.append(f"")
        lines.append(f"| Metric | Value |")
        lines.append(f"|--------|-------|")
        lines.append(f"| Net Lines Added | {prod.get('net_lines_added', 0):+,} |")
        lines.append(f"| Lines Removed | {prod.get('net_lines_removed', 0):+,} |")
        lines.append(f"| Files Changed | {prod.get('files_changed', 0)} |")
        lines.append(f"| Edits/Minute | {prod.get('edits_per_minute', 0):.2f} |")
        lines.append(f"| Tokens/Line | {prod.get('tokens_per_line', 0):.1f} |")
        lines.append(f"")

        # Prompt Analysis
        prompt_info = analysis.get("prompt_analysis", {})
        lines.append(f"## Prompt Analysis")
        lines.append(f"")
        lines.append(f"| Metric | Value |")
        lines.append(f"|--------|-------|")
        lines.append(f"| Avg Complexity | {prompt_info.get('average_complexity', 'n/a')} |")
        lines.append(f"| Dominant Intent | {prompt_info.get('dominant_intent', 'n/a')} |")
        lines.append(f"| Avg Tokens/Prompt | {prompt_info.get('average_token_estimate', 0):.0f} |")
        lines.append(f"| Prompts With Code | {prompt_info.get('prompts_with_code', 0)} |")
        lines.append(f"| Prompts With Questions | {prompt_info.get('prompts_with_questions', 0)} |")
        lines.append(f"")

        # File Edits
        edits = analysis.get("file_analysis", [])
        if edits:
            lines.append(f"## File Edits ({len(edits)})")
            lines.append(f"")
            lines.append(f"| Type | Path | Added | Removed | Size |")
            lines.append(f"|------|------|-------|---------|------|")
            for e in edits[:20]:
                lines.append(
                    f"| {e['edit_type']} | `{e['path']}` | {e['lines_added']} | {e['lines_removed']} | {e['size_impact']} |"
                )
            lines.append(f"")

        # Insights
        insights = analysis.get("insights", [])
        if insights:
            lines.append(f"## Insights")
            lines.append(f"")
            for i in insights:
                lines.append(f"- **[{i['severity'].upper()}]** {i['message']}")
                if i.get("details"):
                    lines.append(f"  - {i['details']}")
            lines.append(f"")
        else:
            lines.append(f"## Insights")
            lines.append(f"")
            lines.append(f"✅ No issues detected.")
            lines.append(f"")

        return "\n".join(lines)
