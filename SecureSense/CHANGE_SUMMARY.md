# Interface and workflow fixes

This release addresses mailbox reporting, simulation feedback, employee learning organization, persistent awareness guidance and the admin overview. Read UPDATED_RUN_GUIDE.md for startup, migration, existing Gophish landing-page refresh requirements and validation limits.

Updated code includes a shared native Gophish reporting helper, mailbox report endpoint and button, banner-based learning bridges, separated pending/completed learning, responsive teal styling and simplified admin summaries. Existing authentication, recipient matching, grading, source separation and advanced analysis remain available.

64 backend tests passed. Browser integration tests are included but not executed successfully in the editing environment. Real Gophish verification remains a local acceptance step.

## AI dashboard testing fix
- Moved AI behavioral analysis directly below Department details on the main admin dashboard.
- Added visible AI assessment explanation, optional source-specific AI summary, retry/run controls, and diagnostic failure messages.
- AI overview now scopes participants to recipient records in the selected source instead of listing unrelated employee accounts.
- Preserved the distinction between deterministic rules indicators and experimental Gemini scores.
