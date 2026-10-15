# Updated behavior

Read ../START_HERE.md (project root START_HERE.md) first. Each launcher run now creates a fresh five-campaign session, uses five matching branded landing pages, and automatically polls live events every 10 seconds. Manual prepare_viva_campaigns.bat reuses the current session. Older reuse/automatic-redirect descriptions below are superseded by START_HERE.md.

# Quick start - exercise laptop

## One command

Double-click `start_practice.bat` from the project root. Keep its console open. Perform the first setup before the presentation while internet access is available so the virtual environment can install its packages.

On the first run it creates a virtual environment, installs the runtime dependencies, creates a private `.env` from `.env.example`, starts the local mail sandbox, starts the SMTP proxy on **127.0.0.1:1027**, and starts SecureSense on port 8000. If an official Gophish executable is configured or found, it is started too.

Expected service summary:

| Service | Address | Started by launcher |
| --- | --- | --- |
| SecureSense | http://127.0.0.1:8000/app/login.html | Yes |
| Test inbox | http://127.0.0.1:8025 | Yes |
| Sandbox SMTP | 127.0.0.1:1028 | Yes |
| SMTP proxy | 127.0.0.1:1027 | Yes |
| Gophish admin | https://127.0.0.1:3333 | Yes when `GOPHISH_EXE` is valid; otherwise start separately |

The browser normally opens SecureSense and the local inbox automatically. Set `AUTO_OPEN_BROWSER=0` in `.env` if you do not want that.

## One-time `.env` settings for live Gophish

Edit `.env` locally and keep it private:

```dotenv
GOPHISH_EXE=C:/Gophish/gophish.exe
GOPHISH_PHISHING_URL=http://127.0.0.1/
GOPHISH_ADMIN_URL=https://127.0.0.1:3333
GOPHISH_CA_BUNDLE=C:/Gophish/securesense_admin.crt
GOPHISH_API_KEY=YOUR_LOCAL_API_KEY
VIVA_AUTO_SEED_GOPHISH=1
```

Optional real Gemini scoring also needs:

```dotenv
GEMINI_API_KEY=YOUR_KEY
GEMINI_MODEL=YOUR_AVAILABLE_MODEL
```

Never put real keys in the submitted ZIP.

When Gophish is reachable and `GOPHISH_API_KEY` is configured, the launcher automatically creates/reuses five **localhost-only viva campaigns** (Credential Harvesting, Financial Fraud, Social Engineering, Urgent Extortion and Malware Delivery). The messages go only to the local sandbox through `127.0.0.1:1027`. If you prefer to seed them manually, leave the launcher running and double-click `prepare_viva_campaigns.bat`.

## First login

After the first run, open `local_credentials.txt` locally and use the generated password for `admin@example.test`. Employee practice credentials are in `05_practice_ACCOUNTS.md`.

## Stop everything

Press **Ctrl+C once** in the launcher window. The supervisor stops the SecureSense-owned child services that it started. If Gophish was already running before the launcher, it is left running.
