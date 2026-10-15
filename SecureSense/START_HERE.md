> **Latest changes (V4):** see [V4_CHANGES.md](V4_CHANGES.md): AI-only risk scores, no AI throttle, same-tab landing page, "Take the Quiz" banner and the new theme.

> **Updated interface:** Read [UPDATED_RUN_GUIDE.md](UPDATED_RUN_GUIDE.md) first. It replaces older popup, automatic-tab and report-link instructions in the historical walkthroughs.

# Start here

Extract into a NEW folder. Stop the old services. Run **start_practice.bat** and keep it open. The configured launcher sends a fresh set of five local campaigns. If setup is incomplete, follow Walkthrough_Documents/01_QUICK_START.md.

Inbox → email (opens in a new tab) → the email link opens the landing page in the SAME tab → the form button shows a "Warning" banner in front of the page → "Take the Quiz" opens SecureSense sign-in in a new tab → mandatory quiz. Password values are cleared locally and never posted. Use the recipient example.test email as Username and a training-only password on the campaign page. Use the actual local_credentials.txt account password only on SecureSense sign-in.

Report phishing in the email opens SecureSense sign-in. After authentication you reach the report section, select the message and submit. Only the logged-in recipient can report that message. This explicit report submission records the outcome; merely opening the report link does not. Reports appear in SecureSense. They are not forwarded to Gophish’s native report API.

The dashboard defaults to live campaigns and displays department charts, participant click/submission/report evidence and latest quiz results. AI risk scores are listed highest first. Detailed audit tools remain in the expandable "Detailed analysis and administration" section.

Browsers may block automatic tabs. A sign-in link appears when that occurs. All addresses and services remain local and fictional. Old emails belong to the old campaign session.
