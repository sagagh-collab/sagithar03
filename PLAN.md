# PLAN — Gmail & Calendar AI Agent

## Phase 1: Google Cloud setup ✅ Done
- Create Google Cloud project (`gmail-calendar-agent`)
- Enable Gmail API and Google Calendar API
- Configure Google Auth Platform (OAuth consent screen, External audience)
- Add required scopes: `gmail.modify`, `calendar`
- Create OAuth Client (Desktop app type), download `credentials.json`
- Add test user for Testing-mode access

## Phase 2: Basic connectivity test ✅ Done
- `uv` project setup (`pyproject.toml`)
- Minimal script that authenticates via OAuth, creates a Gmail draft and a
  Calendar event, to confirm both APIs work end-to-end
- Confirmed working: draft created, calendar event created, `token.json`
  generated for reuse

## Phase 3: LLM integration ✅ Done
- Chose Gemini API (`gemini-2.5-flash`) — free tier, no credit card required
- Stored API key securely in `.env` (excluded from git via `.gitignore`)
- Built prompt for combined classification + extraction (JSON output mode)
- Added retry/backoff handling for rate limits (429) and transient server
  errors (503)

## Phase 4: Full agent pipeline ✅ Done
- Scan inbox for messages in the last 48 hours (configurable)
- Skip formal calendar invites (`text/calendar` MIME part)
- Classify + extract meeting details via Gemini
- Check Calendar free/busy for the extracted slot
- Create event if free / send decline reply if busy
- Tested against real inbox: 8 emails scanned, 2 correctly identified as
  meeting requests and booked, 6 correctly skipped (newsletters, receipts,
  unrelated correspondence, in Hebrew/English/Spanish)

## Phase 5: Documentation & submission (current)
- Write PRD.md, PLAN.md (this file), TODO.md
- Write README.md with setup instructions and screenshots
- Push all code + docs to public GitHub repo (`sagithar03`), verify
  `credentials.json`, `token.json`, `.env` are excluded via `.gitignore`
- Submit PDF via Moodle per course template, individually
