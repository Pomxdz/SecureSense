# AI dashboard fix notes

This revision addresses the admin dashboard behavior seen during live testing.

## What the previous statuses meant

- `unassessed`: the participant has no assessable observed outcome for that source. A delivered/opened message alone is intentionally not treated as a behavioral score. A verified report, click, or test-form submission creates an assessable outcome.
- `failed`: SecureSense attempted the Gemini job three times but either the provider call failed or the returned payload failed validation. The previous build deliberately hid the provider exception behind a generic message.
- `not_requested / not configured`: the previous overview listed every employee account, even if that person did not have a recipient record in the selected data source. This was misleading.

## Changes in this revision

1. **AI behavioral analysis is now a first-class dashboard section immediately after Department details.**
2. The section shows the automatic model assessment explanation, AI score, recommendation, provider/model status, detailed AI summary, and action buttons.
3. **Generate AI summary** is available directly in the AI section; it no longer requires opening the participant drill-down first.
4. **Run AI score / Retry AI score** is available directly in the AI section.
5. The overview now lists only participants who actually have recipient records in the selected source.
6. AI summaries are generated for the currently selected source (`live` or `practice`) and are tagged with that source.
7. Failed AI jobs now retain a redacted diagnostic message so configuration, quota, network, permission, timeout, or response-validation problems can be distinguished during testing.
8. The UI states why `unassessed` does not produce a score.

## Important behavior

The deterministic rules indicator and model-generated AI score remain separate. SecureSense does not fabricate a zero when Gemini is unavailable or when evidence is insufficient.

After replacing the project files, restart SecureSense and hard-refresh the browser so the updated JavaScript is loaded.
