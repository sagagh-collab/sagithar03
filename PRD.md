# PRD — Gmail & Calendar AI Agent
**L08 Bonus Assignment | Group code: sagithar03**

## 1. Overview

An AI agent that connects to a personal Gmail account and, on each run, scans
recent inbox messages to detect free-text meeting requests (not formal
calendar invites), extracts the meeting details using an LLM, checks Google
Calendar availability, and either books the meeting or replies that the
requested time is unavailable.

## 2. Goals

- Demonstrate a working OAuth 2.0 integration with the Gmail API and Google
  Calendar API using a single Desktop OAuth client.
- Demonstrate LLM-based understanding of unstructured, natural-language email
  content (Hebrew and English) rather than keyword matching alone.
- Demonstrate an end-to-end automated workflow: read → understand → decide →
  act (create event / send reply).

## 3. Scope

### In scope
- Gmail: read inbox messages from a configurable recent time window (default
  48 hours), create draft/send reply emails.
- Google Calendar: check free/busy status, create events on the primary
  calendar.
- Gemini API (`gemini-2.5-flash`) used to (a) classify whether an email is a
  genuine meeting request, and (b) extract date, time, duration, participants,
  and location from free text.

### Out of scope
- Formal `.ics` / calendar-invite emails (`text/calendar` MIME parts) are
  explicitly skipped — the assignment requires detecting requests written in
  free text only.
- Multi-account / Workspace organizational support (Internal audience type).
- Recurring meetings, multi-participant real-time negotiation, timezone
  conversion beyond the local system timezone.

## 4. User Flow

1. Agent authenticates once via OAuth (browser consent); reuses `token.json`
   on subsequent runs.
2. Agent lists inbox messages received within the last `LOOKBACK_HOURS` (48
   by default, configurable in code).
3. For each message:
   a. Skip if it contains a formal calendar-invite MIME part.
   b. Skip if it has no plain-text body.
   c. Send the email content to Gemini with a structured-JSON prompt asking
      whether this is a meeting request, and if so, to extract the details.
   d. Skip if Gemini determines it is not a meeting request, or if no date
      can be determined at all.
   e. If the time is missing but the date is present, Gemini infers a
      reasonable business-hours time and flags it as an assumed field
      (transparency is preserved in the created event's description).
   f. Query Calendar Free/Busy for the extracted time slot.
   g. If free → create a Calendar event with full details in the
      description (including any assumed fields).
   h. If busy → send a reply email to the original sender explaining the
      slot is unavailable.

## 5. Edge Case Decisions

| Case | Decision |
|---|---|
| Email has no date at all | Skip — cannot reasonably guess a full date |
| Email has a date but no time | LLM infers a reasonable business-hours time; marked as "assumed" in the event description |
| Email is a formal calendar invite (`.ics`) | Skipped — out of scope per assignment spec |
| Non-meeting email (newsletter, receipt, notification) | Classified as `is_meeting_request: false` by the LLM, skipped |
| Gemini free-tier rate limit (429) / transient server error (503) | Automatic retry with backoff, up to 5 attempts |

## 6. Required Permissions (OAuth Scopes)

- `https://www.googleapis.com/auth/gmail.modify`
- `https://www.googleapis.com/auth/calendar`

## 7. Technology Stack

- Python 3.10+, managed with `uv`
- `google-api-python-client`, `google-auth-oauthlib`, `google-auth-httplib2` — Gmail/Calendar API + OAuth
- `requests` — direct REST calls to the Gemini API
- Google Gemini API (`gemini-2.5-flash`, free tier) — meeting detection & extraction
- Git / GitHub — version control and submission

## 8. Security Considerations

- `credentials.json` (OAuth client secret), `token.json` (user access/refresh
  token), and `.env` (Gemini API key) are all excluded from version control
  via `.gitignore` and are never committed to the public repository.
