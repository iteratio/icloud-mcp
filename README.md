# iCloud MCP Server

A local [Model Context Protocol](https://modelcontextprotocol.io/) server that gives Claude access to your iCloud **Calendar**, **Mail**, and **Reminders** — entirely on your Mac, with no third-party relay.

## Protocols used

| Service | Protocol | Why |
|---|---|---|
| Calendar | **CalDAV** (`caldav.icloud.com`) | Apple's official calendar sync protocol |
| Mail | **IMAP / SMTP** (`imap.mail.me.com`) | Apple's official mail protocol, built into Python |
| Reminders | **EventKit** (macOS framework) | Native macOS API — no auth needed, uses Reminders.app |

> **Note on pyicloud**: Earlier versions of this server used pyicloud, which is now broken. Apple changed their web authentication flow in 2024–2025 to SRP-6a, which pyicloud does not support. The protocols above are official, stable, and will keep working.

## Security model

| Concern | How it's handled |
|---|---|
| Credentials | Stored in **macOS Keychain** — never in files, env vars, or source code |
| Authentication | Uses an **app-specific password** (not your Apple ID password) |
| Network | Communicates directly with **Apple's servers** only |
| Reminders | Uses EventKit (local macOS framework) — no network auth at all |

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

### 2. Generate an app-specific password

Go to [appleid.apple.com](https://appleid.apple.com) → **Account → Sign-In and Security → App-Specific Passwords → +**

Name it anything (e.g. `iCloud MCP`). Copy the generated password — you'll only see it once.

### 3. Store your credentials

```bash
uv run python3 auth.py store
```

You will be prompted for your Apple ID and the app-specific password you just generated. Credentials are stored in the macOS Keychain under the service name `icloud-mcp`.

### 4. Verify credentials

```bash
uv run python3 auth.py verify
```

Expected output:
```
Testing credentials for you@icloud.com ...

  CalDAV  ✓  (3 calendar(s) found)
  IMAP    ✓

All checks passed — credentials are valid.
```

### 5. Add to Claude Code

```bash
claude mcp add icloud -- uv --directory /Users/nicktyson/Documents/iCloudMCP run python3 server.py
```

Restart Claude Code. On first use of a Reminders tool, macOS will ask permission to access Reminders — click **OK**.

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
| `mail_list_mailboxes` | List mailboxes / folders |
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
uv run python3 auth.py store

# Test authentication (CalDAV + IMAP)
uv run python3 auth.py verify

# Remove credentials from Keychain
uv run python3 auth.py clear
```

## Development

```bash
# Install dependencies
uv sync

# Run the server directly (for testing)
uv run python3 server.py
```

## Disclaimer

This project uses Apple's official CalDAV and IMAP protocols, and the macOS EventKit framework. It is not affiliated with or endorsed by Apple Inc.
