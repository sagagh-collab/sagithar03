"""
Gmail & Calendar AI Agent
=========================
Scans recent Gmail messages, uses an LLM (Gemini) to detect free-text meeting
requests, extracts date/time/participants/location, checks Google Calendar
availability, and either creates the event or replies that the time doesn't work.

Setup required before running:
  - credentials.json (Google OAuth Desktop client) in this folder
  - .env file with a line: GEMINI_API_KEY=your_key_here
  - `uv sync` to install dependencies
"""

from __future__ import annotations

import base64
import json
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from email.header import Header
from email.mime.text import MIMEText
from email.utils import formataddr, parseaddr
from pathlib import Path
from typing import Optional

import requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar",
]
CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "token.json"

LOOKBACK_HOURS = 48  # how many hours back to scan the inbox (configurable)
DEFAULT_MEETING_DURATION_MINUTES = 60
GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_API_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
)


# ---------------------------------------------------------------------------
# .env loader (no extra dependency needed)
# ---------------------------------------------------------------------------

def load_env_file(path: str = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


# ---------------------------------------------------------------------------
# Google OAuth (Gmail + Calendar)
# ---------------------------------------------------------------------------

def get_credentials() -> Credentials:
    creds = None
    if Path(TOKEN_FILE).exists():
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        Path(TOKEN_FILE).write_text(creds.to_json(), encoding="utf-8")
    return creds


# ---------------------------------------------------------------------------
# Gmail helpers
# ---------------------------------------------------------------------------

@dataclass
class EmailMessage:
    id: str
    thread_id: str
    sender: str
    subject: str
    received_at: datetime
    body_text: str
    message_id_header: Optional[str] = None
    has_calendar_invite: bool = False


def _decode_body(data: str) -> str:
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")


def _extract_plain_text(payload: dict) -> tuple[str, bool]:
    """Returns (plain_text_body, has_calendar_invite_part)."""
    has_invite = False
    texts: list[str] = []

    def walk(part: dict):
        nonlocal has_invite
        mime_type = part.get("mimeType", "")
        if mime_type == "text/calendar":
            has_invite = True
        if mime_type == "text/plain" and "data" in part.get("body", {}):
            texts.append(_decode_body(part["body"]["data"]))
        for sub in part.get("parts", []) or []:
            walk(sub)

    walk(payload)
    return "\n".join(texts).strip(), has_invite


def list_recent_emails(gmail_service, hours: int) -> list[EmailMessage]:
    days = max(1, -(-hours // 24)) + 1  # broad query, filtered precisely below
    query = f"in:inbox newer_than:{days}d"
    threshold = datetime.now().astimezone() - timedelta(hours=hours)

    results = gmail_service.users().messages().list(userId="me", q=query, maxResults=50).execute()
    message_ids = [m["id"] for m in results.get("messages", [])]

    emails: list[EmailMessage] = []
    for msg_id in message_ids:
        full = gmail_service.users().messages().get(
            userId="me", id=msg_id, format="full"
        ).execute()

        internal_ms = int(full["internalDate"])
        received_at = datetime.fromtimestamp(internal_ms / 1000).astimezone()
        if received_at < threshold:
            continue

        headers = {h["name"]: h["value"] for h in full["payload"].get("headers", [])}
        body_text, has_invite = _extract_plain_text(full["payload"])

        emails.append(EmailMessage(
            id=full["id"],
            thread_id=full["threadId"],
            sender=headers.get("From", ""),
            subject=headers.get("Subject", ""),
            received_at=received_at,
            body_text=body_text,
            message_id_header=headers.get("Message-ID"),
            has_calendar_invite=has_invite,
        ))
    return emails


def send_reply(gmail_service, original: EmailMessage, reply_text: str) -> str:
    msg = MIMEText(reply_text, _charset="utf-8")
    name, addr = parseaddr(original.sender)
    msg["To"] = formataddr((str(Header(name, "utf-8")), addr)) if name else addr
    msg["Subject"] = str(Header(f"Re: {original.subject}", "utf-8"))
    if original.message_id_header:
        msg["In-Reply-To"] = original.message_id_header
        msg["References"] = original.message_id_header
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    sent = gmail_service.users().messages().send(
        userId="me",
        body={"raw": raw, "threadId": original.thread_id},
    ).execute()
    return sent["id"]


# ---------------------------------------------------------------------------
# LLM (Gemini) — classification + extraction
# ---------------------------------------------------------------------------

@dataclass
class MeetingExtraction:
    is_meeting_request: bool
    date: Optional[str] = None
    time: Optional[str] = None
    duration_minutes: int = DEFAULT_MEETING_DURATION_MINUTES
    participants: list[str] = field(default_factory=list)
    location: Optional[str] = None
    assumed_fields: list[str] = field(default_factory=list)
    reasoning: str = ""


def call_gemini(prompt: str, api_key: str, max_retries: int = 5) -> str:
    url = f"{GEMINI_API_URL}?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "response_mime_type": "application/json"},
    }

    for attempt in range(max_retries):
        resp = requests.post(url, json=payload, timeout=30)
        if resp.status_code in (429, 503):
            print(f"  --- Gemini error details (attempt {attempt + 1}, status {resp.status_code}) ---")
            print(resp.text[:1000])
            print("  ---------------------------------------------------")
            wait_seconds = int(resp.headers.get("Retry-After", 15))
            print(f"  (waiting {wait_seconds}s before retry {attempt + 1}/{max_retries}...)")
            time.sleep(wait_seconds)
            continue
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]

    raise RuntimeError("Gemini API rate limit exceeded after multiple retries.")


def build_extraction_prompt(email: EmailMessage) -> str:
    now_str = email.received_at.strftime("%Y-%m-%d %H:%M (%A)")
    return f"""You are analyzing an email (Hebrew or English) to decide whether it contains
a free-text request/invitation to schedule a meeting. This is NOT a formal calendar
invite file - just natural language in the email body.

Email received at: {now_str}
Sender: {email.sender}
Subject: {email.subject}
Body:
---
{email.body_text[:4000]}
---

Return ONLY a JSON object with exactly these fields, no markdown, no extra text:
{{
  "is_meeting_request": true or false,
  "date": "YYYY-MM-DD" or null,
  "time": "HH:MM" in 24h format, or null,
  "duration_minutes": integer,
  "participants": [list of participant names or email addresses mentioned],
  "location": string or null,
  "assumed_fields": [list of field names you had to infer because they were missing],
  "reasoning": short explanation, written in Hebrew
}}

Rules:
- Resolve relative dates (e.g. "tomorrow", "מחר", "יום ראשון הבא") to an absolute
  date using the received date above.
- If a time is not stated explicitly but this is clearly a meeting request, infer a
  reasonable business-hours time (e.g. 10:00) and add "time" to assumed_fields.
- If duration is not mentioned, use 60.
- If there is no way to determine ANY date at all, set is_meeting_request to false.
- Only set is_meeting_request to true for genuine meeting scheduling requests -
  not newsletters, notifications, receipts, or unrelated correspondence.
"""


def extract_meeting_info(email: EmailMessage, api_key: str) -> MeetingExtraction:
    raw = call_gemini(build_extraction_prompt(email), api_key)
    print(f"\n=== DEBUG: {email.subject!r} מאת {email.sender!r} ===")
    print(f"--- טקסט המייל המקורי ---\n{email.body_text[:500]}")
    print(f"--- תשובת Gemini הגולמית ---\n{raw}")
    print("=== סוף DEBUG ===\n")
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    data = json.loads(raw)
    return MeetingExtraction(
        is_meeting_request=bool(data.get("is_meeting_request", False)),
        date=data.get("date"),
        time=data.get("time"),
        duration_minutes=int(data.get("duration_minutes") or DEFAULT_MEETING_DURATION_MINUTES),
        participants=data.get("participants") or [],
        location=data.get("location"),
        assumed_fields=data.get("assumed_fields") or [],
        reasoning=data.get("reasoning", ""),
    )


# ---------------------------------------------------------------------------
# Calendar helpers
# ---------------------------------------------------------------------------

def list_calendar_ids(calendar_service) -> list[str]:
    """Returns IDs of all calendars the user has access to (primary + shared/family/etc.)."""
    calendars = calendar_service.calendarList().list().execute()
    return [cal["id"] for cal in calendars.get("items", [])]


def is_slot_free(calendar_service, start: datetime, end: datetime) -> bool:
    calendar_ids = list_calendar_ids(calendar_service)
    body = {
        "timeMin": start.isoformat(),
        "timeMax": end.isoformat(),
        "items": [{"id": cal_id} for cal_id in calendar_ids],
    }
    result = calendar_service.freebusy().query(body=body).execute()
    for cal_id, cal_data in result.get("calendars", {}).items():
        if cal_data.get("busy"):
            return False
    return True


def create_meeting_event(calendar_service, extraction: MeetingExtraction,
                          start: datetime, end: datetime, source_email: EmailMessage) -> tuple[str, str]:
    description_lines = [
        f"נוצר אוטומטית מתוך מייל מאת: {source_email.sender}",
        f"נושא המייל: {source_email.subject}",
    ]
    if extraction.participants:
        description_lines.append("משתתפים: " + ", ".join(extraction.participants))
    if extraction.assumed_fields:
        description_lines.append(
            "שדות שהושלמו אוטומטית (לא צוינו במקור): " + ", ".join(extraction.assumed_fields)
        )
    if extraction.reasoning:
        description_lines.append(f"נימוק הסוכן: {extraction.reasoning}")

    event = {
        "summary": f"פגישה - {source_email.subject}"[:200],
        "description": "\n".join(description_lines),
        "location": extraction.location or "",
        "start": {"dateTime": start.isoformat()},
        "end": {"dateTime": end.isoformat()},
    }
    created = calendar_service.events().insert(calendarId="primary", body=event).execute()
    return created["id"], created.get("htmlLink", "")


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def process_email(gmail_service, calendar_service, email: EmailMessage, api_key: str) -> None:
    if email.has_calendar_invite:
        print(f"[skip] {email.subject!r} - formal calendar invite (not free text), skipping")
        return

    if not email.body_text:
        print(f"[skip] {email.subject!r} - no text body")
        return

    extraction = extract_meeting_info(email, api_key)

    if not extraction.is_meeting_request:
        print(f"[skip] {email.subject!r} - not a meeting request")
        return

    if not extraction.date:
        print(f"[skip] {email.subject!r} - meeting request detected but no date could be determined")
        return

    time_str = extraction.time or "10:00"
    try:
        start = datetime.fromisoformat(f"{extraction.date}T{time_str}:00").astimezone()
    except ValueError:
        print(f"[skip] {email.subject!r} - could not parse date/time: {extraction.date} {time_str}")
        return

    end = start + timedelta(minutes=extraction.duration_minutes)

    if is_slot_free(calendar_service, start, end):
        event_id, link = create_meeting_event(calendar_service, extraction, start, end, email)
        print(f"[created] {email.subject!r} -> event {event_id} ({link})")
    else:
        reply_text = (
            f"שלום,\n\n"
            f"קיבלנו את בקשתך לקביעת פגישה בתאריך {extraction.date} בשעה {time_str}, "
            f"אך לצערנו מועד זה כבר תפוס ביומן.\n"
            f"נשמח לתאם מועד חלופי.\n\n"
            f"תודה,\nהסוכן האוטומטי"
        )
        reply_id = send_reply(gmail_service, email, reply_text)
        print(f"[busy] {email.subject!r} -> sent decline reply {reply_id}")


def main():
    load_env_file()
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit("GEMINI_API_KEY not found. Check your .env file.")

    creds = get_credentials()
    gmail_service = build("gmail", "v1", credentials=creds)
    calendar_service = build("calendar", "v3", credentials=creds)

    emails = list_recent_emails(gmail_service, LOOKBACK_HOURS)
    print(f"Found {len(emails)} email(s) from the last {LOOKBACK_HOURS} hours.\n")

    for email in emails:
        try:
            process_email(gmail_service, calendar_service, email, api_key)
        except Exception as exc:
            print(f"[error] {email.subject!r} מאת {email.sender!r} - נכשל: {exc}")
        time.sleep(4)  # small pause between emails to stay under free-tier rate limits


if __name__ == "__main__":
    main()
