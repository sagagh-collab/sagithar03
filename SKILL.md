# SKILL: Meeting Request Detection & Scheduling

This document defines the agent's core **skill** — the reusable capability
that combines an LLM prompt with a set of tools to accomplish a task. It is
separate from the orchestration code (`main.py`), which wires the skill to
the Gmail and Calendar APIs and runs it end-to-end.

## What this skill does

Given a single email (sender, subject, body, received timestamp), the skill
determines whether the email contains a **free-text request to schedule a
meeting**, and if so, extracts the structured information needed to act on
it: date, time, duration, participants, and location.

This is the "brain" of the agent — it does not read email or touch the
calendar itself. It receives text and returns a structured decision. The
surrounding code (tools) is what actually performs the Gmail/Calendar
actions based on that decision.

## When it's invoked

Once per email that:
- was received within the configured lookback window (default: 48 hours),
- has a plain-text body,
- is **not** a formal calendar invite (no `text/calendar` MIME part).

## Tools available to the agent

| Tool | Purpose |
|---|---|
| `list_recent_emails` (Gmail API) | Read inbox messages from a time window |
| `call_gemini` (Gemini API) | Run the skill's prompt against an LLM and get a structured JSON response |
| `is_slot_free` (Calendar API — freebusy) | Check whether a given time range is free, across **all** of the user's calendars (not just the primary one) |
| `create_meeting_event` (Calendar API — events.insert) | Book the meeting |
| `send_reply` (Gmail API — messages.send) | Reply to the sender if the slot is unavailable |

The skill itself is only responsible for the middle step: turning raw email
text into a structured scheduling decision. It doesn't decide what to do
with that decision — that's the orchestration logic in `main.py`.

## The prompt (the skill's "instructions")

This is the exact prompt sent to Gemini for every candidate email (see
`build_extraction_prompt` in `main.py`):

```
You are analyzing an email (Hebrew or English) to decide whether it contains
a free-text request/invitation to schedule a meeting. This is NOT a formal
calendar invite file - just natural language in the email body.

Email received at: {received_at}
Sender: {sender}
Subject: {subject}
Body:
---
{body_text}
---

Return ONLY a JSON object with exactly these fields, no markdown, no extra
text:
{
  "is_meeting_request": true or false,
  "date": "YYYY-MM-DD" or null,
  "time": "HH:MM" in 24h format, or null,
  "duration_minutes": integer,
  "participants": [list of participant names or email addresses mentioned],
  "location": string or null,
  "assumed_fields": [list of field names you had to infer because they were missing],
  "reasoning": short explanation, written in Hebrew
}

Rules:
- Resolve relative dates (e.g. "tomorrow", "מחר", "יום ראשון הבא") to an
  absolute date using the received date above.
- If a time is not stated explicitly but this is clearly a meeting request,
  infer a reasonable business-hours time (e.g. 10:00) and add "time" to
  assumed_fields.
- If duration is not mentioned, use 60.
- If there is no way to determine ANY date at all, set is_meeting_request
  to false.
- Only set is_meeting_request to true for genuine meeting scheduling
  requests - not newsletters, notifications, receipts, or unrelated
  correspondence.
```

## Input / Output contract

**Input:** one email (sender, subject, body text, received timestamp)

**Output (JSON):**

```json
{
  "is_meeting_request": true,
  "date": "2026-07-07",
  "time": "11:00",
  "duration_minutes": 60,
  "participants": ["דני", "danny@example.com"],
  "location": "המשרד",
  "assumed_fields": ["time"],
  "reasoning": "המייל מבקש לתאם פגישה ליום שלישי הקרוב, לא צוינה שעה"
}
```

## Why this counts as a "skill" and not just a function call

The behavior of this capability is defined almost entirely by the **prompt**,
not by branching code logic. Changing what counts as a "meeting request," how
aggressively to infer missing fields, or which languages to support are all
changes to the prompt text — not to the surrounding Python code. This is the
essence of an LLM-based skill: the instructions *are* the logic, and the code
around it is just plumbing (reading input, calling the model, parsing its
structured output, and acting on the result).

## Evaluation

Initial test: 8 real inbox emails (Hebrew, English, Spanish) — 2 correctly
classified as genuine meeting requests (and booked), 6 correctly classified
as non-meeting emails (newsletters, receipts, unrelated correspondence) —
see the "Example run" section in [`README.md`](./README.md) for the full
output and screenshots.

Expanded test (July 2026): 12 real inbox emails, mixing genuine meeting
requests, calendar notifications, formal invites, and marketing email.
This round surfaced three real bugs in the orchestration code (not the
prompt), all since fixed in `main.py`:

- **Header encoding crash** — replying to senders with a non-ASCII (Hebrew)
  display name raised `Invalid To header` and crashed the whole run,
  silently leaving remaining emails unprocessed.
- **Single-calendar conflict check** — availability was only checked
  against the `primary` calendar, so events on secondary calendars (e.g. a
  shared "family" calendar) were invisible to the conflict check.
- **No per-email error isolation** — one failing email (API error, bad
  data) would stop the entire batch instead of being logged and skipped.

## Known limitations

- **LLM non-determinism:** the same email body, run through the skill on
  different occasions, has been observed to receive different
  `is_meeting_request` classifications (true vs. false) for genuinely
  ambiguous phrasing (e.g. "קבענו פגישה מחר בשעה 15:00" — is this a new
  request or confirmation of an existing one?). This is inherent to
  LLM-based classification at `temperature=0.2` and is not a code defect;
  lowering temperature or adding few-shot examples to the prompt would
  reduce but not eliminate it.
- **Free-tier rate limits:** the Gemini free tier enforces a daily request
  quota (as low as 20 requests/day for `gemini-2.5-flash` at time of
  writing). Scanning even a modest inbox can exhaust it mid-run; the
  agent will retry with backoff and then log an `[error]` and move on
  rather than crash, but affected emails are simply never classified
  that day.
