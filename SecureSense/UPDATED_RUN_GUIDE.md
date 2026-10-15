# SecureSense interface and workflow update

## Run the updated application

1. Stop the old SecureSense and mailbox processes. Extract this archive into a new folder.
2. Carry over your existing `.env` configuration if you have one. To preserve learning records, also copy `Member2/securesense_v2.db` while the old services are stopped. No schema migration is required by this update.
3. Confirm `GOPHISH_PHISHING_URL` points to the Gophish **phishing server**, not its admin port. The default is `http://127.0.0.1/`.
4. Run `start_practice.bat` as before. Keep the launcher open. Use the normal local training accounts.
5. Existing Gophish landing pages contain their own HTML. Refresh them using `prepare_viva_campaigns.bat` (for the bundled local showcase) or regenerate the learning bridge in Integration setup and paste the returned HTML into each campaign landing page. Keep Gophish's Redirect URL empty and Capture Passwords off. Bridge tickets expire after seven days.
6. Hard-refresh the portal to reload `script.js` and `style.css`.

Do not use real passwords in the simulation forms. Simulation password fields are cleared locally and never posted.

## What changed

- The mailbox has a red **Report Phishing** button at the upper right of an opened message. It calls the configured Gophish `/report?rid=…` endpoint and stays on the message. Success appears inline; failures leave the action available for retry. Duplicate clicks are suppressed. Legacy report links are removed from the mailbox's rendered email content.
- Authenticated reports from the employee portal are also forwarded to Gophish for live campaigns. Practice records remain local. Mailbox reports reach SecureSense through the existing signed webhook or campaign polling integration; keep that integration running.
- The email link opens the landing page in the same tab. Simulation feedback is a "Warning" banner shown in front of the landing page with one **Take the Quiz** button. There is no cancel button or automatic sign-in tab. Pressing **Take the Quiz** opens SecureSense sign-in in a new tab.
- A bridge configured with `clicked` shows its banner when the landing page opens. A bridge configured with `test_form_submission` shows it after Gophish accepts the form POST. The five bundled showcase campaigns retain their submission trigger. Both modes still require the appropriate verified event and matching signed-in recipient before opening the assigned quiz.
- Employee learning is divided into pending and completed quizzes. New assignments are labelled; the newest pending assignment (or the assignment from a simulation handoff) is highlighted. Failed attempts remain pending with a retry action. Completed means the assignment has been passed at 80% or above.
- Phishing consequences and the Google Jigsaw practice link appear on sign-in, the employee portal, and the quiz view. Awareness banners are not shown in the mailbox.
- The admin overview shows four clear counts, a brief activity summary and compact department progress. Filters, individual results and detailed technical analysis can be expanded when needed.

## Verification

64 backend regression tests pass, including reporting ownership, retries, duplicate reports, Gophish endpoint construction, handoff validation and quiz grading. JavaScript syntax and Python compilation checks pass.

The browser integration test was updated for six scenarios: the five category submission flows plus a click-triggered flow. It also checks no-navigation reporting, pending-to-completed quiz movement and mobile overflow. Chromium could not launch in the editing environment, so this updated browser test and visual rendering still need to be run on your machine. A real Gophish instance was not available here; reporting was verified against the documented endpoint contract with mocked transport.

```sh
pip install -r requirements-dev.txt
python -m playwright install chromium
python -m pytest tests/test_workflow.py -q
python tests/browser_handoff_workflow.py
```

Test execution here used FastAPI 0.115.12, Flask 3.1.0, HTTPX 0.28.1, Pydantic 2.11.3 and pytest 8.3.5. The application's supplied dependency pins are unchanged.

## Manual acceptance checks

- Open a campaign message, press Report Phishing and confirm the page stays in place. Refresh the Gophish campaign results and verify **Email Reported** for that recipient. Reporting must not create a **Clicked Link** event.
- Disconnect Gophish temporarily: reporting should show a retryable error, not a success message.
- For a click-triggered bridge, open the email link. For a submission-triggered bridge, submit the fictional form. Confirm the Warning banner appears in front of the landing page, that nothing navigates until Take the Quiz is pressed, and that it then opens SecureSense sign-in in a new tab.
- Sign in as the matching recipient, complete the quiz and confirm it moves from Pending quizzes to Completed quizzes only after a passing score.
- Check the portal at desktop and mobile widths, and follow the Jigsaw link in a new tab.

Gophish reporting reference: https://docs.getgophish.com/user-guide/documentation/email-reporting

## Follow-up interface cleanup

The technical red warning about verified interaction and webhook telemetry has been removed from the employee handoff flow. Pending synchronization now shows a neutral status under Pending quizzes. SecureSense still waits for a verified Gophish event; this presentation change does not bypass verification or repair an unavailable integration. If it persists, check campaign synchronization, webhook delivery and the bridge trigger.

Phishing-awareness banners have been removed from the mailbox. They remain on SecureSense sign-in, employee learning and quiz views.
