"""
iCloud MCP Server

Exposes iCloud Calendar, Mail, and Reminders as MCP tools.
Credentials are read from the macOS Keychain — never from env vars or files.

Run:
    uv run server.py
"""

from __future__ import annotations

import sys
from typing import Any

import mcp.server.stdio
import mcp.types as types
from mcp.server import Server
from pyicloud import PyiCloudService
from pyicloud.exceptions import PyiCloudFailedLoginException

from auth import get_credentials
from tools import calendar as cal_tools
from tools import mail as mail_tools
from tools import reminders as rem_tools

# ---------------------------------------------------------------------------
# iCloud session (initialised lazily on first tool call)
# ---------------------------------------------------------------------------

_api: PyiCloudService | None = None


def _get_api() -> PyiCloudService:
    global _api
    if _api is not None:
        return _api

    apple_id, app_password = get_credentials()

    try:
        api = PyiCloudService(apple_id, app_password)
    except PyiCloudFailedLoginException as exc:
        raise RuntimeError(
            "iCloud login failed. Check your credentials: python auth.py verify"
        ) from exc

    if api.requires_2fa:
        print(
            "Two-factor authentication is required.\n"
            "Enter the 6-digit code sent to your trusted device:",
            flush=True,
        )
        code = input().strip()
        if not api.validate_2fa_code(code):
            raise RuntimeError("2FA code was not accepted by Apple.")
        if not api.is_trusted_session:
            api.trust_session()

    _api = api
    return _api


# ---------------------------------------------------------------------------
# Server setup
# ---------------------------------------------------------------------------

server = Server("icloud-mcp")


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        # ── Calendar ──────────────────────────────────────────────────────
        types.Tool(
            name="calendar_list_calendars",
            description="List all iCloud calendars.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        types.Tool(
            name="calendar_list_events",
            description=(
                "List calendar events in a date range. "
                "Defaults to the next 7 days if no dates are given."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "from_date": {
                        "type": "string",
                        "description": "Start date (ISO-8601, e.g. 2025-03-01). Defaults to today.",
                    },
                    "to_date": {
                        "type": "string",
                        "description": "End date (ISO-8601). Defaults to 7 days from today.",
                    },
                    "calendar_uid": {
                        "type": "string",
                        "description": "Restrict results to this calendar UID.",
                    },
                },
                "required": [],
            },
        ),
        types.Tool(
            name="calendar_get_event",
            description="Get full details of a single calendar event by UID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "event_uid": {"type": "string", "description": "The event UID."}
                },
                "required": ["event_uid"],
            },
        ),
        types.Tool(
            name="calendar_create_event",
            description="Create a new calendar event.",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Event title."},
                    "start": {
                        "type": "string",
                        "description": "Start datetime (ISO-8601).",
                    },
                    "end": {
                        "type": "string",
                        "description": "End datetime (ISO-8601).",
                    },
                    "calendar_uid": {
                        "type": "string",
                        "description": "Target calendar UID (uses default if omitted).",
                    },
                    "location": {"type": "string", "description": "Optional location."},
                    "description": {
                        "type": "string",
                        "description": "Optional notes / description.",
                    },
                },
                "required": ["title", "start", "end"],
            },
        ),
        # ── Mail ──────────────────────────────────────────────────────────
        types.Tool(
            name="mail_list_mailboxes",
            description="List all iCloud Mail mailboxes / folders with unread counts.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        types.Tool(
            name="mail_list_messages",
            description="List messages in a mailbox (default: INBOX).",
            inputSchema={
                "type": "object",
                "properties": {
                    "mailbox": {
                        "type": "string",
                        "description": "Mailbox name (default: INBOX).",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max messages to return (default 20, max 100).",
                    },
                    "unread_only": {
                        "type": "boolean",
                        "description": "Return only unread messages.",
                    },
                },
                "required": [],
            },
        ),
        types.Tool(
            name="mail_get_message",
            description="Get the full content of an email by UID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "uid": {"type": "string", "description": "Message UID."},
                    "mailbox": {
                        "type": "string",
                        "description": "Mailbox containing the message (default: INBOX).",
                    },
                },
                "required": ["uid"],
            },
        ),
        types.Tool(
            name="mail_send_message",
            description="Send an email via iCloud Mail.",
            inputSchema={
                "type": "object",
                "properties": {
                    "to": {
                        "type": "string",
                        "description": "Recipient address (or comma-separated list).",
                    },
                    "subject": {"type": "string", "description": "Email subject."},
                    "body": {"type": "string", "description": "Plain-text body."},
                    "cc": {"type": "string", "description": "Optional CC addresses."},
                    "bcc": {"type": "string", "description": "Optional BCC addresses."},
                },
                "required": ["to", "subject", "body"],
            },
        ),
        # ── Reminders ─────────────────────────────────────────────────────
        types.Tool(
            name="reminders_list_lists",
            description="List all iCloud Reminder lists.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        types.Tool(
            name="reminders_list_reminders",
            description="List reminders, optionally filtered by list.",
            inputSchema={
                "type": "object",
                "properties": {
                    "list_uid": {
                        "type": "string",
                        "description": "Restrict to a specific reminder list UID.",
                    },
                    "include_completed": {
                        "type": "boolean",
                        "description": "Include completed reminders (default: false).",
                    },
                },
                "required": [],
            },
        ),
        types.Tool(
            name="reminders_create_reminder",
            description="Create a new reminder.",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Reminder title."},
                    "list_uid": {
                        "type": "string",
                        "description": "Target list UID (uses default list if omitted).",
                    },
                    "due": {
                        "type": "string",
                        "description": "Optional due date/time (ISO-8601).",
                    },
                    "description": {
                        "type": "string",
                        "description": "Optional notes.",
                    },
                    "priority": {
                        "type": "integer",
                        "description": "Priority: 0=none, 1=high, 5=medium, 9=low.",
                    },
                },
                "required": ["title"],
            },
        ),
        types.Tool(
            name="reminders_complete_reminder",
            description="Mark a reminder as completed.",
            inputSchema={
                "type": "object",
                "properties": {
                    "uid": {"type": "string", "description": "The reminder UID."}
                },
                "required": ["uid"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    api = _get_api()

    try:
        result: Any

        # ── Calendar ──────────────────────────────────────────────────────
        if name == "calendar_list_calendars":
            result = cal_tools.list_calendars(api)

        elif name == "calendar_list_events":
            result = cal_tools.list_events(
                api,
                from_date=arguments.get("from_date"),
                to_date=arguments.get("to_date"),
                calendar_uid=arguments.get("calendar_uid"),
            )

        elif name == "calendar_get_event":
            result = cal_tools.get_event(api, arguments["event_uid"])
            if result is None:
                result = {"error": f"Event '{arguments['event_uid']}' not found."}

        elif name == "calendar_create_event":
            result = cal_tools.create_event(
                api,
                title=arguments["title"],
                start=arguments["start"],
                end=arguments["end"],
                calendar_uid=arguments.get("calendar_uid"),
                location=arguments.get("location", ""),
                description=arguments.get("description", ""),
            )

        # ── Mail ──────────────────────────────────────────────────────────
        elif name == "mail_list_mailboxes":
            result = mail_tools.list_mailboxes(api)

        elif name == "mail_list_messages":
            result = mail_tools.list_messages(
                api,
                mailbox=arguments.get("mailbox", "INBOX"),
                limit=arguments.get("limit", 20),
                unread_only=arguments.get("unread_only", False),
            )

        elif name == "mail_get_message":
            result = mail_tools.get_message(
                api,
                uid=arguments["uid"],
                mailbox=arguments.get("mailbox", "INBOX"),
            )
            if result is None:
                result = {"error": f"Message '{arguments['uid']}' not found."}

        elif name == "mail_send_message":
            result = mail_tools.send_message(
                api,
                to=arguments["to"],
                subject=arguments["subject"],
                body=arguments["body"],
                cc=arguments.get("cc", ""),
                bcc=arguments.get("bcc", ""),
            )

        # ── Reminders ─────────────────────────────────────────────────────
        elif name == "reminders_list_lists":
            result = rem_tools.list_lists(api)

        elif name == "reminders_list_reminders":
            result = rem_tools.list_reminders(
                api,
                list_uid=arguments.get("list_uid"),
                include_completed=arguments.get("include_completed", False),
            )

        elif name == "reminders_create_reminder":
            result = rem_tools.create_reminder(
                api,
                title=arguments["title"],
                list_uid=arguments.get("list_uid"),
                due=arguments.get("due"),
                description=arguments.get("description", ""),
                priority=arguments.get("priority", 0),
            )

        elif name == "reminders_complete_reminder":
            found = rem_tools.complete_reminder(api, arguments["uid"])
            result = {"completed": found}

        else:
            result = {"error": f"Unknown tool: {name}"}

    except Exception as exc:  # noqa: BLE001
        result = {"error": str(exc)}

    import json

    return [types.TextContent(type="text", text=json.dumps(result, indent=2, default=str))]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def _run() -> None:
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def main() -> None:
    import asyncio

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
