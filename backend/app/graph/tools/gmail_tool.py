import os
import email
from email.header import decode_header
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import imaplib
import smtplib
import re
from typing import Optional
from dotenv import load_dotenv, find_dotenv
from langchain_core.tools import tool

load_dotenv(find_dotenv())

GMAIL_IMAP_SERVER = "imap.gmail.com"
GMAIL_IMAP_PORT = 993
GMAIL_SMTP_SERVER = "smtp.gmail.com"
GMAIL_SMTP_PORT = 465


def _get_gmail_credentials() -> tuple[Optional[str], Optional[str]]:
    """Retrieve Gmail credentials from environment variables."""
    email_address = os.getenv("GMAIL_EMAIL") or os.getenv("GMAIL_USER")
    app_password = os.getenv("GMAIL_APP_PASSWORD") or os.getenv("GMAIL_PASSWORD")
    if email_address and any(p in email_address.lower() for p in ("your_", "example.com", "none")):
        email_address = None
    if app_password and any(p in app_password.lower() for p in ("your_", "placeholder", "none")):
        app_password = None
    if app_password:
        # Strip any spaces that Google App Passwords often have (e.g. 'abcd efgh ijkl mnop')
        app_password = app_password.replace(" ", "").strip()
    return email_address, app_password


def _decode_header_str(header_val: Optional[str]) -> str:
    """Decode encoded email header fields into plain text."""
    if not header_val:
        return "(No Subject)"
    try:
        decoded_fragments = decode_header(header_val)
        parts = []
        for fragment, encoding in decoded_fragments:
            if isinstance(fragment, bytes):
                try:
                    parts.append(fragment.decode(encoding or "utf-8", errors="replace"))
                except Exception:
                    parts.append(fragment.decode("latin-1", errors="replace"))
            else:
                parts.append(str(fragment))
        return "".join(parts).strip()
    except Exception:
        return str(header_val)


def _extract_body_snippet(msg: email.message.Message, max_chars: int = 1000) -> str:
    """Extract plain text snippet or cleaned HTML content from an email message."""
    body = ""
    try:
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition", ""))
                if content_type == "text/plain" and "attachment" not in content_disposition.lower():
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or "utf-8"
                        body = payload.decode(charset, errors="replace")
                        break
            # Fallback to HTML if plain text wasn't found
            if not body:
                for part in msg.walk():
                    content_type = part.get_content_type()
                    content_disposition = str(part.get("Content-Disposition", ""))
                    if content_type == "text/html" and "attachment" not in content_disposition.lower():
                        payload = part.get_payload(decode=True)
                        if payload:
                            charset = part.get_content_charset() or "utf-8"
                            html_text = payload.decode(charset, errors="replace")
                            clean_text = re.sub(r"<[^>]+>", " ", html_text)
                            body = " ".join(clean_text.split())
                            break
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or "utf-8"
                raw_text = payload.decode(charset, errors="replace")
                if msg.get_content_type() == "text/html":
                    raw_text = re.sub(r"<[^>]+>", " ", raw_text)
                body = " ".join(raw_text.split())
    except Exception as e:
        body = f"(Could not parse email body: {str(e)})"

    body = body.strip()
    if len(body) > max_chars:
        body = body[:max_chars] + "...\n[Content truncated]"
    return body or "(Empty body)"


@tool
def read_gmail_messages(
    query: str = "",
    max_results: int = 5,
    unread_only: bool = False
) -> str:
    """
    Read or search emails from Gmail inbox.

    Parameters:
    - query (str, optional): Search keyword, sender email, or Gmail query (e.g. 'from:boss@example.com', 'invoice', or 'meeting').
      Leave empty to retrieve the most recent emails.
    - max_results (int, optional): Number of emails to retrieve (default is 5, max is 15).
    - unread_only (bool, optional): If True, only search and fetch unread emails. Default is False.

    Returns:
    - Formatted list of emails with Subject, From, Date, and Body preview.
    """
    email_address, app_password = _get_gmail_credentials()

    if not email_address or not app_password:
        return (
            "Gmail credentials are not configured. "
            "Please add `GMAIL_EMAIL` and `GMAIL_APP_PASSWORD` to your `.env` file.\n"
            "Note: Generate a 16-character App Password at: https://myaccount.google.com/apppasswords"
        )

    max_results = max(1, min(max_results, 15))
    mail = None

    try:
        mail = imaplib.IMAP4_SSL(GMAIL_IMAP_SERVER, GMAIL_IMAP_PORT)
        mail.login(email_address, app_password)
        mail.select("INBOX")

        clean_query = query.strip()
        search_ids = []

        # 1. Try Gmail-specific search (X-GM-RAW) if query is provided
        if clean_query:
            raw_search_query = clean_query
            if unread_only:
                raw_search_query = f"is:unread {clean_query}"
            try:
                status, response = mail.search(None, f'X-GM-RAW "{raw_search_query}"')
                if status == "OK" and response[0]:
                    search_ids = response[0].split()
            except Exception:
                search_ids = []

        # 2. Fallback to standard IMAP search
        if not search_ids:
            criteria = "UNSEEN" if unread_only else "ALL"
            status, response = mail.search(None, criteria)
            if status == "OK" and response[0]:
                search_ids = response[0].split()

        if not search_ids:
            filter_desc = "unread " if unread_only else ""
            query_desc = f" matching '{query}'" if query else ""
            return f"No {filter_desc}emails found in Gmail inbox{query_desc}."

        # Recent emails come last in IMAP, so reverse to get newest first
        search_ids.reverse()

        messages_data = []
        for msg_id in search_ids:
            if len(messages_data) >= max_results:
                break

            status, msg_data = mail.fetch(msg_id, "(RFC822)")
            if status != "OK" or not msg_data or not msg_data[0]:
                continue

            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)

            subject = _decode_header_str(msg.get("Subject"))
            sender = _decode_header_str(msg.get("From"))
            date_str = msg.get("Date", "Unknown Date")
            body_snippet = _extract_body_snippet(msg, max_chars=800)

            # If user had a query and standard search was used as fallback, do in-memory filtering
            if clean_query and clean_query.lower() not in (subject + sender + body_snippet).lower():
                continue

            messages_data.append(
                f"### Email {len(messages_data) + 1}\n"
                f"- **Subject**: {subject}\n"
                f"- **From**: {sender}\n"
                f"- **Date**: {date_str}\n"
                f"- **Body Preview**:\n```\n{body_snippet}\n```"
            )

        if not messages_data:
            return f"No emails matched your criteria '{query}' among recent messages."

        return f"Found {len(messages_data)} email(s):\n\n" + "\n\n".join(messages_data)

    except imaplib.IMAP4.error as e:
        return (
            f"Gmail IMAP authentication error: {str(e)}. "
            "Please check that your `GMAIL_EMAIL` and `GMAIL_APP_PASSWORD` are valid and "
            "IMAP is enabled in your Gmail settings (Settings -> Forwarding and POP/IMAP -> Enable IMAP)."
        )
    except Exception as e:
        return f"Error reading emails from Gmail: {str(e)}"
    finally:
        if mail:
            try:
                mail.close()
            except Exception:
                pass
            try:
                mail.logout()
            except Exception:
                pass


@tool
def send_gmail_message(
    recipient: str,
    subject: str,
    body: str,
    cc: str = ""
) -> str:
    """
    Send an email using Gmail SMTP.

    Parameters:
    - recipient (str): The email address of the receiver (e.g. 'john@example.com').
    - subject (str): Subject line of the email.
    - body (str): The plain text content or body of the email.
    - cc (str, optional): Optional comma-separated list of CC email addresses.

    Returns:
    - A confirmation string indicating whether the email was sent successfully.
    """
    recipient = recipient.strip()
    if not recipient or "@" not in recipient:
        return "Please provide a valid recipient email address."

    subject = subject.strip()
    if not subject:
        return "Please provide an email subject."

    body = body.strip()
    if not body:
        return "Please provide the email body content."

    # Enforce Human-in-the-Loop approval for sensitive outbound email
    try:
        from langgraph.types import interrupt
        from langgraph.errors import GraphInterrupt
        approval = interrupt({
            "action": "send_gmail_message",
            "question": f"Do you approve sending an email to {recipient} with subject '{subject}'?",
            "recipient": recipient,
            "subject": subject,
            "body_snippet": body[:120] + ("..." if len(body) > 120 else ""),
        })
        if not approval or str(approval).lower() in ("false", "reject", "no", "0"):
            return f"Action cancelled by user: Email to {recipient} was not sent."
    except GraphInterrupt:
        raise
    except (RuntimeError, KeyError):
        # Running outside of a LangGraph execution context (e.g. standalone test)
        pass

    email_address, app_password = _get_gmail_credentials()
    if not email_address or not app_password:
        return (
            "Gmail credentials are not configured. "
            "Please add `GMAIL_EMAIL` and `GMAIL_APP_PASSWORD` to your `.env` file.\n"
            "Note: Generate a 16-character App Password at: https://myaccount.google.com/apppasswords"
        )

    msg = MIMEMultipart()
    msg["From"] = email_address
    msg["To"] = recipient
    msg["Subject"] = subject

    all_recipients = [recipient]
    if cc.strip():
        cc_list = [c.strip() for c in cc.split(",") if c.strip() and "@" in c]
        if cc_list:
            msg["Cc"] = ", ".join(cc_list)
            all_recipients.extend(cc_list)

    msg.attach(MIMEText(body, "plain", "utf-8"))

    server = None
    try:
        server = smtplib.SMTP_SSL(GMAIL_SMTP_SERVER, GMAIL_SMTP_PORT, timeout=20)
        server.login(email_address, app_password)
        server.sendmail(email_address, all_recipients, msg.as_string())

        cc_info = f"\n- **CC**: {msg['Cc']}" if "Cc" in msg else ""
        return (
            f"Email sent successfully!\n"
            f"- **To**: {recipient}"
            f"{cc_info}\n"
            f"- **Subject**: {subject}\n"
            f"- **Sender**: {email_address}"
        )
    except smtplib.SMTPAuthenticationError:
        return (
            "Gmail SMTP authentication failed. "
            "Please verify your `GMAIL_EMAIL` and `GMAIL_APP_PASSWORD` in your `.env` file. "
            "Make sure 2-Step Verification is enabled and you are using an App Password."
        )
    except Exception as e:
        return f"Failed to send email: {str(e)}"
    finally:
        if server:
            try:
                server.quit()
            except Exception:
                pass
