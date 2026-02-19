# iCloud MCP Server

A local [Model Context Protocol](https://modelcontextprotocol.io/) server that gives Claude access to your iCloud **Calendar**, **Mail**, and **Reminders** — entirely on your Mac, with no third-party relay.

## Security model

| Concern | How it's handled |
|---|---|
| Credentials | Stored in **macOS Keychain** — never in files, env vars, or source code |
| Authentication | Uses an **app-specific password** (not your Apple ID password) |
| Network | Communicates directly with **Apple's iCloud APIs** only |
| Scope | Read + targeted write; no bulk deletes |

## Requirements

- macOS 12+
- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (`brew install uv`)
- An Apple ID with iCloud enabled
- An [app-specific password](https://support.apple.com/en-us/102654) for iCloud

## Setup

### 1. Install dependencies

```bash
uv sync
```

### 2. Store your credentials

```bash
uv run python auth.py store
```

You will be prompted for:
- Your Apple ID (e.g. `you@icloud.com`)
- An app-specific password — generate one at [appleid.apple.com](https://appleid.apple.com) under **Account › Sign‑In and Security › App‑Specific Passwords**

Credentials are stored in the macOS Keychain under the service name `icloud-mcp`.

### 3. Verify credentials

```bash
uv run python auth.py verify
```

### 4. Add to Claude Code

Add the server to your Claude Code MCP configuration (`~/.claude/claude_desktop_config.json` or via `claude mcp add`):

```json
{
  "mcpServers": {
    "icloud": {
      "command": "uv",
      "args": ["run", "python", "/path/to/iCloudMCP/server.py"]
    }
  }
}
```

Replace `/path/to/iCloudMCP` with the actual path to this repository.

## Available tools

### Calendar

| Tool | Description |
|---|---|
| `calendar_list_calendars` | List all calendars |
| `calendar_list_events` | List events in a date range (default: next 7 days) |
| `calendar_get_event` | Get a single event by UID |
| `calendar_create_event` | Create a new event |

### Mail

| Tool | Description |
|---|---|
| `mail_list_mailboxes` | List mailboxes with unread counts |
| `mail_list_messages` | List messages in a mailbox |
| `mail_get_message` | Get full content of a message |
| `mail_send_message` | Send an email |

### Reminders

| Tool | Description |
|---|---|
| `reminders_list_lists` | List all reminder lists |
| `reminders_list_reminders` | List reminders (optionally filter by list / completion) |
| `reminders_create_reminder` | Create a new reminder |
| `reminders_complete_reminder` | Mark a reminder as completed |

## Credential management

```bash
# Store credentials
uv run python auth.py store

# Test authentication
uv run python auth.py verify

# Remove credentials from Keychain
uv run python auth.py clear
```

## Two-factor authentication

If your Apple ID has 2FA enabled (recommended), the server will prompt for a 6-digit code on first startup. After entering the code it trusts the session for subsequent runs.

## Development

```bash
# Install in editable mode with dev extras
uv sync

# Run the server directly (for testing)
uv run python server.py
```

## Disclaimer

This project uses the unofficial `pyicloud` library which communicates with Apple's private iCloud APIs. Apple may change these APIs without notice. Use at your own risk. This project is not affiliated with or endorsed by Apple Inc.
