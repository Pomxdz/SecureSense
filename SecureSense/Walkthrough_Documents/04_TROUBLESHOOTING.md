# Updated behavior

Read ../START_HERE.md (project root START_HERE.md) first. Each launcher run now creates a fresh five-campaign session, uses five matching branded landing pages, and automatically polls live events every 10 seconds. Manual prepare_viva_campaigns.bat reuses the current session. Older reuse/automatic-redirect descriptions below are superseded by START_HERE.md.

# Troubleshooting

## Port 1025 is occupied

This submission build no longer uses 1025 by default. Gophish should send to **127.0.0.1:1027**. The proxy relays internally to the sandbox SMTP listener on 1028.

To check the port on Windows:

```bat
netstat -ano | findstr :1027
```

If 1027 is also occupied, edit `.env` and choose another free local port, for example `PROXY_PORT=1029`, then use the same port in the Gophish Sending Profile.

## Launcher says a project port is already in use

Close stale SecureSense/mail processes or change the relevant `.env` port. The launcher intentionally refuses to silently attach to an unknown process on the SecureSense-owned ports.

## Gophish is reported as not started

Gophish is not bundled. Confirm either:

```dotenv
GOPHISH_EXE=C:/Gophish/gophish.exe
```

or start `gophish.exe` manually from the extracted Gophish directory. If Gophish is already running on the configured admin port, the launcher detects it and does not start a second copy.

## Test email does not appear in the inbox

Check the launcher summary and verify:

- Gophish Sending Profile host is `127.0.0.1:1027`;
- SMTP proxy is listening on 1027;
- sandbox SMTP is listening on 1028;
- the inbox opens at `http://127.0.0.1:8025`.

## Gophish API synchronization fails

Check `.env`:

```dotenv
GOPHISH_ADMIN_URL=https://127.0.0.1:3333
GOPHISH_CA_BUNDLE=C:/Gophish/securesense_admin.crt
GOPHISH_API_KEY=...
```

Use the SAN certificate created by `gophish_local_setup.py`. Do not disable TLS certificate verification as a workaround.

## Campaign opens the wrong page or no page

The campaign URL must be the Gophish **phishing server**, normally `http://127.0.0.1` (or your configured alternative such as port 8080). Do not use the admin URL on port 3333.

## Learning bridge waits for telemetry

Confirm the real campaign was synchronized before the participant interaction and keep `sync_gophish.py` polling. A short wait until the next poll is expected. Ensure the logged-in employee matches the Gophish recipient mapping and the bridge trigger matches the campaign objective.

## Wrong account / expired bridge

Sign out and use the exact linked fictional participant. If the bridge expired, generate a new campaign landing HTML in SecureSense and re-import it into the same Gophish landing page.

## AI score is unavailable

This is expected without a genuine Gemini key and available model. Check `GEMINI_API_KEY` and `GEMINI_MODEL` in the private `.env`, then restart the launcher. Do not fabricate a model score for the exercise.

## Reset to the clean synthetic practice

Stop the launcher, extract a fresh copy of the submission ZIP into a new folder and run `start_practice.bat`. Runtime databases and generated credentials are deliberately excluded from the submitted archive.

## Viva campaigns were not created automatically

Automatic population requires all of the following while `start_practice.bat` is running:

```dotenv
VIVA_AUTO_SEED_GOPHISH=1
GOPHISH_API_KEY=...
GOPHISH_CA_BUNDLE=C:/Gophish/securesense_admin.crt
```

Gophish must be reachable at the configured local admin URL. After fixing `.env`, rerun `start_practice.bat`, or leave the stack running and launch `prepare_viva_campaigns.bat`. The seeder refuses non-loopback Gophish or phishing URLs.

## Only three categories appear on Synthetic practice

That is expected for the fixed historical synthetic fixture. For the viva category showcase choose **Live simulation** after `seed_viva_gophish.py` has populated and synchronized the five real local Gophish campaigns. The supported platform categories are Financial Fraud, Credential Harvesting, Urgent Extortion, Social Engineering, Malware Delivery and the General fallback.
