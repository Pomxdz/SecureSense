> **Updated interface:** Read [UPDATED_RUN_GUIDE.md](UPDATED_RUN_GUIDE.md) first. It replaces older popup, automatic-tab and report-link instructions in the historical walkthroughs.

> Updated release: read **UPDATED_RUN_GUIDE.md** first. All five new campaigns have practice credential forms.

# SecureSense updated practice

Start with **START_HERE.md**. Every launcher start creates and sends a fresh five-campaign local session. Each email opens its matching landing page, then offers targeted learning. Live telemetry synchronizes every 10 seconds.

# SecureSense - Submission-Ready Build

This package is the cleaned exercise build of the Interactive Cyber Security Awareness and Phishing Simulation Platform. The implementation follows the proposed three-tier design: official Gophish for authorized local simulations, Python/FastAPI + SQLite + optional Groq-backed AI scoring for telemetry and analysis, and the SecureSense web portal for GRC review and targeted learning.

## Fastest start on Windows

1. Extract the ZIP into a new folder.
2. Make sure Python 3.11+ is installed. Run the first setup once before the presentation while internet access is available so Python packages can be installed.
3. Double-click **`start_practice.bat`**.
4. Keep the launcher window open during the exercise.

The launcher creates `.venv` if needed, installs `requirements.txt`, creates `.env` from `.env.example` on first run, and starts the SecureSense-owned backend services:

- SecureSense/FastAPI: `http://127.0.0.1:8000/app/login.html`
- local test inbox: `http://127.0.0.1:8025`
- SMTP sandbox: `127.0.0.1:1028`
- SMTP proxy: `127.0.0.1:1027`

Port **1027** is the default Gophish-facing SMTP port in this submission build because 1025 is reserved on the exercise laptop.

Gophish is an official external download and is intentionally not included in this archive. If `.env` contains a valid `GOPHISH_EXE` path, the launcher also starts it. Otherwise it reports that Gophish must be started separately. The default admin URL is `https://127.0.0.1:3333`.

Press **Ctrl+C once in the launcher window** to stop the SecureSense-owned services.

## First login

The first practice start generates the administrator password in `local_credentials.txt`. Use:

- administrator: `admin@example.test`
- employee exercise accounts: see `Walkthrough_Documents/05_practice_ACCOUNTS.md`

Do not submit or screen-record generated credentials, `.env`, API keys, databases or runtime logs.

## Walkthroughs

All current exercise instructions are isolated from the source tree in **`Walkthrough_Documents/`**. Start with `00_WALKTHROUGH_INDEX.md`. The build now includes a localhost-only **five-category viva showcase**. When Gophish is running and `.env` contains a valid local API key and trusted CA bundle, `start_practice.bat` automatically creates/reuses one Gophish campaign for each supported attack category, synchronizes them into SecureSense, and refreshes the targeted-learning bridge. You can also run `prepare_viva_campaigns.bat` manually.

## Project layout

- `Member1/` - local simulation mail transport plus safe Gophish templates, including five colorful viva showcase emails.
- `Member2/` - FastAPI backend, SQLite evidence, learning, and Groq-backed AI risk scores (the only source of risk scores).
- `Member3/frontend/` - administrator and employee interfaces.
- `examples/` - current Gophish synchronization and learning-bridge request examples.
- `tests/` - regression, browser, SMTP and isolated local Gophish workflow checks.
- `Documentation/Reference/` - proposal alignment, methodology, verification results, change record and submission manifest.
- `Documentation/Reports/` - technical report.

## Optional developer verification

Install test dependencies only when needed:

```bat
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m pytest tests\test_workflow.py -q
.venv\Scripts\python.exe tests\smtp_workflow.py
```

Browser and isolated real-Gophish checks require Playwright Chromium and an extracted official Gophish engine. See the walkthroughs and `Documentation/Reference/TEST_RESULTS.md`.

## Safety and scope

Use only fictional `@example.test` identities and authorized local/loopback campaigns. Keep Gophish password capture disabled. The local prototype supports awareness evidence review; it does not claim enterprise certification, production hardening or measured causal training effectiveness.
