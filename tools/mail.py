"""iCloud Mail tools for MCP."""

from __future__ import annotations

from typing import Any


def _fmt_message(msg: Any) -> dict:
    """Normalise a pyicloud mail message to a plain dict."""
    return {
        "uid": getattr(msg, "uid", ""),
        "subject": getattr(msg, "subject", "(no subject)"),
        "from": getattr(msg, "sender", ""),
        "to": getattr(msg, "to", ""),
        "date": str(getattr(msg, "date", "")),
        "read": getattr(msg, "read", True),
        "flagged": getattr(msg, "flagged", False),
        "has_attachments": getattr(msg, "has_attachments", False),
    }


def list_mailboxes(api: Any) -> list[dict]:
    """Return all mailboxes / folders."""
    mailboxes = api.mail.get_mailboxes()
    return [
        {
            "uid": mb.get("id", ""),
            "name": mb.get("displayName", mb.get("name", "")),
            "unread": mb.get("unseenCount", 0),
            "total": mb.get("totalCount", 0),
        }
        for mb in mailboxes
    ]


def list_messages(
    api: Any,
    mailbox: str = "INBOX",
    limit: int = 20,
    unread_only: bool = False,
) -> list[dict]:
    """
    Return messages from a mailbox.

    Args:
        api: Authenticated PyiCloudService instance.
        mailbox: Mailbox name (default: INBOX).
        limit: Maximum number of messages to return (default: 20, max: 100).
        unread_only: If True, return only unread messages.
    """
    limit = min(limit, 100)
    messages = api.mail.get_messages(mailbox=mailbox, limit=limit)
    result = [_fmt_message(m) for m in messages]

    if unread_only:
        result = [m for m in result if not m["read"]]

    return result


def get_message(api: Any, uid: str, mailbox: str = "INBOX") -> dict | None:
    """
    Return the full content of a message.

    Args:
        api: Authenticated PyiCloudService instance.
        uid: Message UID.
        mailbox: Mailbox containing the message (default: INBOX).
    """
    msg = api.mail.get_message(uid=uid, mailbox=mailbox)
    if msg is None:
        return None

    result = _fmt_message(msg)
    result["body"] = getattr(msg, "body", "")
    return result


def send_message(
    api: Any,
    to: str,
    subject: str,
    body: str,
    cc: str = "",
    bcc: str = "",
) -> dict:
    """
    Send an email via iCloud Mail.

    Args:
        api: Authenticated PyiCloudService instance.
        to: Recipient address (or comma-separated list).
        subject: Email subject.
        body: Plain-text body.
        cc: Optional CC addresses.
        bcc: Optional BCC addresses.

    Returns:
        dict with 'status' and 'message_id'.
    """
    result = api.mail.send(
        to=to,
        subject=subject,
        body=body,
        cc=cc or None,
        bcc=bcc or None,
    )
    return {
        "status": "sent",
        "message_id": getattr(result, "message_id", ""),
    }
