# Reference document

Current operating instructions are in START_HERE.md. The following retained reference describes the earlier architecture; changed screens and startup names are superseded by that guide.

SecureSense Walkthrough

Submission-ready local exercise build

Gophish + FastAPI/SQLite/AI + targeted learning + GRC dashboard

This walkthrough is the current exercise path. Older duplicate guides were removed from the root of the project. All simulation identities are fictional and all mail transport is designed for authorized local testing. The viva-ready build can populate five localhost-only Gophish category campaigns automatically.

1. Start the complete local stack

Double-click start_practice.bat from the project root. On first run it creates .venv, installs the runtime dependencies, creates a private .env from .env.example, and then launches the SecureSense-owned backend services through practice_launcher.py.

Service

Default address

Launcher behavior

SecureSense

http://127.0.0.1:8000/app/login.html

Started automatically

Test inbox

http://127.0.0.1:8025

Started automatically

Sandbox SMTP

127.0.0.1:1028

Started automatically

SMTP proxy

127.0.0.1:1027

Started automatically

Gophish admin

https://127.0.0.1:3333

Auto-started when GOPHISH_EXE is configured/found; otherwise start separately

Port 1027 is intentionally used for the Gophish Sending Profile because port 1025 is occupied on the exercise laptop. Press Ctrl+C once in the launcher window to stop services started by the supervisor.

First login

Administrator: admin@example.test. The generated password is stored locally in local_credentials.txt after first startup.

Employee exercise identities are listed in Walkthrough_Documents/05_practice_ACCOUNTS.md.

Do not include .env, local_credentials.txt, runtime databases, API keys or private certificates in the submitted archive or screen recording.

2. One-time Gophish preparation

Gophish is an official external download and is not redistributed in this project. Extract it separately, for example to C:\Gophish. The helper script creates a loopback-only configuration and a local SAN certificate while preserving a backup of the existing configuration.

.venv\Scripts\python.exe gophish_local_setup.py C:\Gophish

If Gophish phishing port 80 is unavailable, choose an alternative such as 8080 and use it consistently:

.venv\Scripts\python.exe gophish_local_setup.py C:\Gophish --phish-port 8080

Set the local paths and API connection in the private .env file:

GOPHISH_EXE=C:/Gophish/gophish.exe

GOPHISH_ADMIN_URL=https://127.0.0.1:3333

GOPHISH_CA_BUNDLE=C:/Gophish/securesense_admin.crt

GOPHISH_API_KEY=YOUR_LOCAL_API_KEY

GOPHISH_PHISHING_URL=http://127.0.0.1/

VIVA_AUTO_SEED_GOPHISH=1

Create the five-category Gophish viva showcase

When the local Gophish API key and CA bundle are configured, start_practice.bat automatically creates/reuses the viva resources through seed_viva_gophish.py. The Sending Profile remains localhost-only on 127.0.0.1:1027.

Five colorful HTML templates are provided in Member1/viva_templates/: Credential Harvesting, Financial Fraud, Social Engineering, Urgent Extortion and Malware Delivery. Each uses fictional branding and keeps the Gophish tracking placeholders intact.

The seeder creates safe landing pages and then replaces them with category-specific SecureSense learning bridges. Password capture is always disabled; form-based scenarios accept only a fictional test email.

One fictional @example.test user is assigned to each category so all five campaigns are visible without external mail or real identities.

The campaigns are named VIVA 01 through VIVA 05 and use the local phishing-server URL, never admin port 3333. To seed or refresh them manually while the stack is running, double-click prepare_viva_campaigns.bat.

3. Connect live Gophish evidence to SecureSense

The viva seeder performs the initial Gophish-to-SecureSense synchronization automatically when local administrator credentials are available. Select Live simulation on the dashboard to show the five categories.

For manual/custom campaigns, Integration setup and examples/gophish_sync.json remain available. Always ensure the category and objective match the actual local exercise.

For continuous polling, edit examples/gophish_profiles.json and run sync_gophish.py with a 10-second interval in a separate terminal.

The five viva campaigns receive campaign-specific learning bridges automatically: Credential Harvesting and Financial Fraud use test_form_submission; Social Engineering, Urgent Extortion and Malware Delivery use clicked.

Rerunning the viva seeder refreshes the seven-day learning bridge tickets and updates the same local Gophish landing pages through the API.

Open one of the five local inbox messages, perform the configured trigger, synchronize/poll the campaign if needed, then sign in as the exact mapped employee. Verified telemetry must exist before SecureSense opens the category-specific lesson.

.venv\Scripts\python.exe sync_gophish.py examples\gophish_profiles.json --interval 10

The bridge is campaign-specific, expiring and identity-checked. Possessing the URL alone does not grant access or create telemetry. A short waiting state is normal until the next poll imports the native event.

Optional automatic Gemini scoring

The runtime requirements already include the Google GenAI SDK. To show real model-generated scores, configure a genuine key and a model available to that account in .env, then restart the launcher:

GEMINI_API_KEY=YOUR_KEY

GEMINI_MODEL=YOUR_AVAILABLE_MODEL

If the provider is unavailable or credentials are absent, the UI must show unavailable/failed honestly. The deterministic rules indicator remains a separately labelled auditable comparator.

4. Recommended presentation sequence

Start start_practice.bat and show the ready service summary without exposing secrets.

In Gophish show VIVA 01 through VIVA 05, the five colorful templates, the local Sending Profile on port 1027, fictional groups and the loopback campaign URL.

Open the local inbox at port 8025 and show the five visually distinct authorized simulation emails.

Choose one category for the live interaction. Perform the configured click or fictional test-email submission and show the corresponding native Gophish event.

Switch SecureSense to Live simulation and show the five campaign/category records. Keep the poller active for interactions performed during the viva and show imported recipient evidence and data-quality handling.

Follow the generated learning bridge, sign in as the matching employee, open the category-specific lesson and complete the five-question server-graded quiz.

Open the participant drilldown and explain the deterministic rules indicator separately from the experimental AI-generated score.

Show learning completion, comparable retest/follow-up status, action owner/due date, GRC awareness evidence and CSV export.

Close by stating the limits: fictional identities, localhost mail, password capture disabled, no external email and no causal human-effectiveness claim from synthetic fixtures.

5. exercise safeguards

Use only fictional @example.test accounts and authorized localhost targets.

Never enable Gophish password capture for this project.

Never enter real OTPs, passwords, card data or banking details into the simulation form.

Keep certificate verification enabled for the local Gophish API connection.

Do not call the deterministic score an AI score; model outputs and rules indicators are intentionally separate.

Review required is a governance status, not proof of certification or complete organizational compliance.

6. Troubleshooting checklist

Problem

Action

Port 1025 occupied

Use the current default 127.0.0.1:1027 in the Gophish Sending Profile. If 1027 is occupied, change PROXY_PORT in .env and use the same port in Gophish.

Gophish not started

Set GOPHISH_EXE in .env or start the official executable manually from its extracted directory.

No test mail

Verify proxy 1027, sandbox SMTP 1028 and inbox 8025 are running; then test the Gophish Sending Profile again.

Gophish API fetch fails

Check the HTTPS admin URL, local API key and SAN certificate path. Do not disable certificate verification.

Learning waits

Keep sync_gophish.py polling, verify the campaign mapping and confirm the bridge trigger matches the exercise.

Wrong account / expired bridge

Use the exact mapped participant or regenerate and re-import the campaign-specific bridge.

AI unavailable

Check a genuine key/model and provider access. Do not fabricate a score.

Need a clean reset

Stop services, extract a fresh copy of the submission ZIP and run start_practice.bat again.

7. Verification statement

The retained project evidence records 53 API/regression tests, 12 browser workflow checks and 21 actual local Gophish workflow checks from the proposal-aligned iteration. The cleaned packaging keeps those tests and updates the SMTP tests to use high isolated ports so they do not depend on port 1025. A successful remote Gemini call still requires a genuine provider key/model and is not fabricated by the package.

For detailed methodology, alignment and verification limits, see Documentation/Reference/.