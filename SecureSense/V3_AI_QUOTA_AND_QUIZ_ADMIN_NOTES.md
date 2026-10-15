# SecureSense V3 update: AI quota control and quiz administration

## AI quota/rate-limit handling

- All Gemini calls now go through one paced gateway.
- SecureSense enforces a minimum 15-second interval between Gemini calls, keeping application traffic at or below 4 requests/minute.
- `AI_MIN_CALL_INTERVAL_SECONDS` can be increased in `.env` for stricter quotas; values below 15 are ignored.
- Automatic behavioral scoring and optional AI summaries share the same limiter.
- HTTP 429 / `RESOURCE_EXHAUSTED` responses are no longer retried immediately.
- Score jobs enter `rate_limited`, display a short friendly reason, and automatically resume after a cooldown.
- Cooldowns increase after repeated 429 responses. Daily-quota-style errors receive a longer cooldown.
- Existing stored 429 failures are migrated into the cooldown queue at application startup.
- The dashboard shows the scheduled automatic retry instead of the raw provider exception.
- The “Run AI score” action now requests only the currently selected source (`live` or `practice`) to avoid unnecessary duplicate Gemini calls.

## Administrator navigation

- The Admin Team Overview no longer links to **My learning**.
- If an administrator manually opens `employee.html`, the UI redirects back to the Admin Team Overview.
- Admin navigation now includes **Quiz management**.

## Quiz management

A dedicated **Quiz management** section is available on the Admin Team Overview, immediately after the AI analysis block.

Administrators can:

- Select any supported phishing category quiz.
- Add a question.
- Edit a question, answer options, category, and correct answer.
- Delete individual questions.
- Delete all questions in the selected category quiz.

Quiz questions are stored in SQLite and the original category questions are seeded automatically only once. Deleted questions are not silently restored on restart.

The employee training endpoints now read the current database-managed quiz. Question counts are dynamic (1–20 supported by submission validation), and the percentage score is calculated from the actual number of current questions. The pass mark remains 80%.

Historical quiz-attempt scores remain stored and are not recalculated when an administrator later edits a quiz.

## Validation completed

- Python compilation: passed.
- Frontend JavaScript syntax check: passed.
- Backend regression suite: 63 tests passed.
- One pre-existing mailbox test is not runnable in this environment because the optional `aiosmtpd` dependency is not installed here.
