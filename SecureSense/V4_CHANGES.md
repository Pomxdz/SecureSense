# V4 changes: AI-only risk scores, same-tab landing page, quiz banner, new theme

This file supersedes the AI rate-limit and "rules indicator" notes in `V3_AI_QUOTA_AND_QUIZ_ADMIN_NOTES.md` and `AI_SECTION_FIX_NOTES.md`.

## 1. AI rate limiting removed
- The 15-second spacing between Gemini calls and the long cooldown queue are gone (`proposal_features.py`).
- Jobs run back-to-back. A failed call is retried twice (after 10 s and 20 s), then marked Failed with a **Retry** button.
- Jobs parked by the old version are put back in the queue automatically at startup.
- `AI_MIN_CALL_INTERVAL_SECONDS` was removed from `.env.example`.
- A quota set by Google on your API key still applies. If you see repeated failures with 429 / RESOURCE_EXHAUSTED, use a key or plan with a higher quota.

## 2. Risk score comes only from AI
- `main.py` no longer calculates a score, severity or recurrence value. `profile_assessment` now only counts observed facts.
- The AI receives anonymised facts only (category, difficulty, clicked, submitted test form, reported, timing) and no Python-computed score.
- The prompt states: 0 = lowest risk, 100 = highest risk.
- The low/medium/high colours on the dashboard (0-33 / 34-66 / 67-100) are display only.
- Internally, `outcomes()` still keeps a per-event rank used to decide whether a person has an assessable outcome and for the retest comparison. It is not shown and not sent to the AI.

## 3. Email link opens in the same tab
- Links inside the email now navigate the whole tab (`target="_top"`, because the mailbox displays the email in an iframe). No new tab opens.
- Email templates no longer contain `target="_blank"`.

## 4. "Take the Quiz" banner in front of the landing page
- After the form button is pressed, a full-screen overlay appears in front of the landing page (dimmed, blurred background; envelope warning icon; red "Warning"; one **Take the Quiz** button).
- **Take the Quiz** opens SecureSense sign-in in a **new tab**. The landing tab stays as it is.
- Regenerate each campaign's landing HTML (`prepare_viva_campaigns.bat`, or Integration setup > "Generate campaign learning landing HTML") and update it in Gophish. Existing Gophish landing pages keep the old banner until you do.

## 5. Theme and admin dashboard
- One stylesheet (`style.css`) for login, employee, admin, integration setup and the mailbox pages: navy sidebar, teal buttons, green/amber/red used only for risk.
- Admin: Live/Practice switch, six summary cards, AI risk scores ranked highest first (expand a row for the reason and recommendation), department cards, participant table with Yes/No chips, quiz management, and a collapsed "Detailed analysis and administration" section.
- "Score everyone now" runs AI scoring for every listed person.
- Integration setup pre-fills a starter JSON request for each operation.
- Phishing landing pages keep their own fictional brand colours on purpose, so the simulation stays realistic. Only the banner uses the SecureSense theme.

## Tests
- `tests/test_workflow.py`: 71 tests.
- Browser tests need Chromium. Set `CHROMIUM_EXECUTABLE=/path/to/chromium` if Playwright cannot download its own.
