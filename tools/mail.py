"""iCloud Mail tools — IMAP/SMTP implementation.

Uses Apple's official IMAP (imap.mail.me.com:993) and SMTP
(smtp.mail.me.com:587) endpoints with Basic Auth (app-specific password).
No pyicloud dependency — uses Python built-ins only.
"""

from __future__ import annotations

import email
import imaplib
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid

IMAP_HOST = "imap.mail.me.com"
IMAP_PORT = 993
SMTP_HOST = "smtp.mail.me.com"
SMTP_PORT = 587


def _imap(apple_id: str, app_password: str) -> imaplib.IMAP4_SSL:
    """Return an authenticated IMAP connection."""
    conn = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
    conn.login(apple_id, app_password)
    return conn


def _decode_header(value: str | bytes | None) -> str:
    """Safely decode an email header value to a plain string."""
    if value is None:
        return ""
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    parts = email.header.decode_header(value)
    decoded = []
    for part, charset in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(part)
    return "".join(decoded)


def _fmt_message(uid: str, msg: email.message.Message) -> dict:
    return {
        "uid": uid,
        "subject": _decode_header(msg.get("Subject")),
        "from": _decode_header(msg.get("From")),
        "to": _decode_header(msg.get("To")),
        "date": _decode_header(msg.get("Date")),
        "message_id": _decode_header(msg.get("Message-ID")),
    }


def list_mailboxes(apple_id: str, app_password: str) -> list[dict]:
    """Return all mailboxes / folders with unread counts."""
    conn = _imap(apple_id, app_password)
    _, raw_list = conn.list()
    conn.logout()

    mailboxes: list[dict] = []
    for item in raw_list or []:
        if not item:
            continue
        decoded = item.decode() if isinstance(item, bytes) else item
        # Format: (\Flags) "delimiter" "name"
        parts = decoded.rsplit(" ", 1)
        name = parts[-1].strip().strip('"')
        mailboxes.append({"name": name})

    return mailboxes


def list_messages(
    apple_id: str,
    app_password: str,
    mailbox: str = "INBOX",
    limit: int = 20,
    unread_only: bool = False,
) -> list[dict]:
    """
    Return messages from a mailbox.

    Args:
        apple_id: iCloud Apple ID.
        app_password: App-specific password.
        mailbox: Mailbox name (default: INBOX).
        limit: Maximum number of messages to return (default 20, max 100).
        unread_only: If True, return only unread messages.
    """
    limit = min(limit, 100)
    conn = _imap(apple_id, app_password)

    conn.select(f'"{mailbox}"', readonly=True)
    criteria = "UNSEEN" if unread_only else "ALL"
    _, data = conn.search(None, criteria)

    uids = data[0].split() if data[0] else []
    # Most recent first
    uids = uids[-limit:][::-1]

    results: list[dict] = []
    for uid in uids:
        _, msg_data = conn.fetch(uid, "(RFC822.HEADER)")
        if not msg_data or not msg_data[0]:
            continue
        raw = msg_data[0][1] if isinstance(msg_data[0], tuple) else msg_data[0]
        msg = email.message_from_bytes(raw)
        results.append(_fmt_message(uid.decode(), msg))

    conn.logout()
    return results


def get_message(
    apple_id: str,
    app_password: str,
    uid: str,
    mailbox: str = "INBOX",
) -> dict | None:
    """
    Return the full content of a message.

    Args:
        apple_id: iCloud Apple ID.
        app_password: App-specific password.
        uid: Message UID (sequence number from list_messages).
        mailbox: Mailbox containing the message (default: INBOX).
    """
    conn = _imap(apple_id, app_password)
    conn.select(f'"{mailbox}"', readonly=True)
    _, msg_data = conn.fetch(uid, "(RFC822)")
    conn.logout()

    if not msg_data or not msg_data[0]:
        return None

    raw = msg_data[0][1] if isinstance(msg_data[0], tuple) else msg_data[0]
    msg = email.message_from_bytes(raw)
    result = _fmt_message(uid, msg)

    # Extract body
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            cd = str(part.get("Content-Disposition", ""))
            if ct == "text/plain" and "attachment" not in cd:
                body = part.get_payload(decode=True).decode(
                    part.get_content_charset() or "utf-8", errors="replace"
                )
                break
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            body = payload.decode(
                msg.get_content_charset() or "utf-8", errors="replace"
            )

    result["body"] = body
    return result


def send_message(
    apple_id: str,
    app_password: str,
    to: str,
    subject: str,
    body: str,
    cc: str = "",
    bcc: str = "",
) -> dict:
    """
    Send an email via iCloud SMTP.

    Args:
        apple_id: iCloud Apple ID (used as From address).
        app_password: App-specific password.
        to: Recipient address (or comma-separated list).
        subject: Email subject.
        body: Plain-text body.
        cc: Optional CC addresses.
        bcc: Optional BCC addresses.

    Returns:
        dict with 'status' and 'message_id'.
    """
    msg = MIMEMultipart()
    msg["From"] = apple_id
    msg["To"] = to
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg_id = make_msgid()
    msg["Message-ID"] = msg_id

    if cc:
        msg["Cc"] = cc
    if bcc:
        msg["Bcc"] = bcc

    msg.attach(MIMEText(body, "plain", "utf-8"))

    recipients = [r.strip() for r in to.split(",")]
    if cc:
        recipients += [r.strip() for r in cc.split(",")]
    if bcc:
        recipients += [r.strip() for r in bcc.split(",")]

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(apple_id, app_password)
        smtp.sendmail(apple_id, recipients, msg.as_bytes())

    return {"status": "sent", "message_id": msg_id}
