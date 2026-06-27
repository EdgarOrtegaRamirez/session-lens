"""MCP server for SessionLens — integrate with AI coding agents."""

from __future__ import annotations

import json
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from .analyzer import SessionAnalyzer
from .storage import SessionStore


def create_mcp_server(store: SessionStore | None = None) -> Server:
    """Create an MCP server instance for SessionLens."""
    store = store or SessionStore()
    analyzer = SessionAnalyzer()
    report_gen = None  # lazily imported for efficiency

    server = Server("session-lens")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="session_lens_list_sessions",
                description="List coding sessions with optional filtering by status.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "status": {
                            "type": "string",
                            "enum": ["active", "completed", "interrupted", "errored"],
                            "description": "Filter by session status",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results",
                            "default": 20,
                        },
                    },
                    "required": [],
                },
            ),
            Tool(
                name="session_lens_analyze_session",
                description="Analyze a coding session for insights, token usage, productivity metrics, and prompts patterns.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "session_id": {
                            "type": "string",
                            "description": "The session ID to analyze",
                        },
                        "format": {
                            "type": "string",
                            "enum": ["text", "json", "markdown"],
                            "description": "Output format for the analysis report",
                            "default": "text",
                        },
                    },
                    "required": ["session_id"],
                },
            ),
            Tool(
                name="session_lens_get_stats",
                description="Get aggregate statistics across all coding sessions.",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any] | None = None) -> list[TextContent]:
        arguments = arguments or {}

        if name == "session_lens_list_sessions":
            status = arguments.get("status")
            limit = arguments.get("limit", 20)
            sessions = store.list_sessions(status=status, limit=limit)
            data = [{
                "id": s.id,
                "title": s.title,
                "status": s.status.value if hasattr(s.status, 'value') else s.status,
                "project_path": s.project_path,
                "model": s.model,
                "started_at": s.started_at.isoformat(),
                "duration_human": s.duration_human,
                "token_count": s.compute_summary().total_tokens,
            } for s in sessions]
            return [TextContent(type="text", text=json.dumps(data, indent=2))]

        elif name == "session_lens_analyze_session":
            session_id = arguments.get("session_id")
            if not session_id:
                return [TextContent(type="text", text="Error: session_id is required.")]
            session = store.get_session(session_id)
            if not session:
                return [TextContent(type="text", text=f"Session {session_id} not found.")]

            analysis = analyzer.analyze_session(session)
            fmt = arguments.get("format", "json")

            if fmt == "json":
                return [TextContent(type="text", text=json.dumps(analysis, indent=2))]

            nonlocal report_gen
            if report_gen is None:
                from .analyzer import ReportGenerator
                report_gen = ReportGenerator(analyzer)

            if fmt == "markdown":
                return [TextContent(type="text", text=report_gen.generate_markdown_report(analysis))]
            else:
                return [TextContent(type="text", text=report_gen.generate_text_report(analysis))]

        elif name == "session_lens_get_stats":
            stats = store.get_stats()
            return [TextContent(type="text", text=json.dumps(stats, indent=2))]

        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    return server


async def run_mcp_server() -> None:
    """Run the SessionLens MCP server over stdio."""
    store = SessionStore()
    server = create_mcp_server(store)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream)


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_mcp_server())
