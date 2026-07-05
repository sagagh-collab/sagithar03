# TODO — Gmail & Calendar AI Agent

## Done
- [x] Google Cloud project + Gmail API + Calendar API enabled
- [x] OAuth consent screen + scopes configured
- [x] OAuth Desktop client created, `credentials.json` obtained
- [x] Basic connectivity test (draft + calendar event) — verified working
- [x] Gemini API key obtained (free tier, AI Studio)
- [x] `.env` set up and excluded from git
- [x] Full agent pipeline implemented (`main.py`)
- [x] Tested end-to-end against real inbox — 2 meetings booked, 6 correctly
      skipped
- [x] Git repo initialized, pushed to GitHub (`sagagh-collab/sagithar03`)
- [x] `.gitignore` covering `credentials.json`, `token.json`, `.env`,
      `.venv/`, `__pycache__/`

## Remaining
- [ ] Write PRD.md — done in this session
- [ ] Write PLAN.md — done in this session
- [ ] Write TODO.md — this file
- [ ] Write README.md with full setup walkthrough + screenshots
- [ ] Take/collect screenshots: Cloud Console setup, connectivity test
      output, agent full-run output, Calendar events created
- [ ] Add screenshots to README.md
- [ ] Final review of repo (public, correct name, no secrets committed)
- [ ] Export submission PDF from Moodle Word template with GitHub repo link
- [ ] Submit individually via Moodle

## Possible future improvements (not required for this assignment)
- [ ] Configurable business hours window for inferred meeting times
- [ ] Support for multiple calendars / attendee invites (not just description text)
- [ ] Structured logging to a file instead of console prints only
- [ ] Unit tests for the extraction/parsing logic
