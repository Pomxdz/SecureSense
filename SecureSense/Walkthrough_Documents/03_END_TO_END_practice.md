# Updated behavior

Read ../START_HERE.md (project root START_HERE.md) first. Each launcher run now creates a fresh five-campaign session, uses five matching branded landing pages, and automatically polls live events every 10 seconds. Manual prepare_viva_campaigns.bat reuses the current session. Older reuse/automatic-redirect descriptions below are superseded by START_HERE.md.

# End-to-end exercise script

This order gives a clean presentation while keeping synthetic and live evidence visibly separate.

## 1. Start the stack

Double-click `start_practice.bat`. Show the final service summary, not any secrets. Confirm SecureSense and the local inbox opened. If using the real local engine, confirm the launcher reports Gophish as running.

## 2. Show the simulation tier

If the API key was configured, `start_practice.bat` should have created/reused the five-category viva showcase automatically. Otherwise run `prepare_viva_campaigns.bat` while the launcher remains open.

In Gophish show:

- the local Sending Profile using `127.0.0.1:1027`;
- five visually distinct HTML templates;
- one fictional local recipient group per category;
- **VIVA 01** through **VIVA 05**, covering Credential Harvesting, Financial Fraud, Social Engineering, Urgent Extortion and Malware Delivery;
- campaign URLs pointing to the local phishing server, never the admin port 3333.

Open `http://127.0.0.1:8025` and show the five colorful fictional messages. Explain that every recipient uses the reserved `.test` domain and every email is intercepted locally.

## 3. Show the controlled participant interaction

Open the message and follow the Gophish link. For a form exercise enter only the fictional `@example.test` address. Do not capture passwords. The native Gophish campaign should record the relevant click or submitted-data event.

## 4. Show middleware and evidence ingestion

The viva seeder performs an initial synchronization automatically. For interactions performed during the viva, run/keep `sync_gophish.py` polling if you want the dashboard to refresh continuously. In SecureSense select **Live simulation** and show the five campaign/category records without mixing them with synthetic fixtures. Explain that duplicate deliveries/events are normalized rather than counted as additional failed people.

## 5. Show targeted learning

Use the generated campaign bridge. Sign in as the exact linked employee. SecureSense checks the campaign, tracking mapping, logged-in identity and required imported telemetry before opening the matching lesson. Complete the five-question category quiz and show the server-graded result. At least four correct answers are required to pass.

## 6. Show behavioral analysis

In the participant drilldown distinguish:

- the deterministic/reproducible rules indicator;
- the experimental model-generated AI score when Gemini is genuinely configured.

If Gemini is not configured or unavailable, show the unavailable state honestly. Do not describe the rules indicator as an AI-generated score.

## 7. Show GRC evidence and follow-up

Show:

- source-separated summary rates and journeys;
- departmental/campaign context;
- participant history;
- learning completion and comparable retest status;
- action owner and due date;
- GRC awareness evidence owner/review date;
- authenticated CSV export.

Explain that `Review required` is an internal governance action and not automatic certification.

## 8. Close the exercise

State the verified local scope: fictional recipients, localhost mail transport, password capture disabled, no external email, no fabricated remote Gemini result and no claim of causal human-learning effectiveness from synthetic fixtures.

Press Ctrl+C in the launcher window to stop the SecureSense-owned services.
