# Updated behavior

Read ../START_HERE.md (project root START_HERE.md) first. Each launcher run now creates a fresh five-campaign session, uses five matching branded landing pages, and automatically polls live events every 10 seconds. Manual prepare_viva_campaigns.bat reuses the current session. Older reuse/automatic-redirect descriptions below are superseded by START_HERE.md.

# Gophish setup and campaign walkthrough

Use this only for an authorized localhost exercise with fictional identities. Gophish is a separate official download and is not included in the project ZIP.


## Fast viva setup: populate all five categories automatically

After the one-time Gophish preparation in section A and after placing the local API key and CA bundle in `.env`, the easiest viva path is simply to rerun `start_practice.bat`. With `VIVA_AUTO_SEED_GOPHISH=1`, the launcher calls `seed_viva_gophish.py` after the local stack is ready. The seeder is idempotent: it creates missing resources and reuses existing named resources rather than sending duplicate campaigns on every launch.

You can also run it manually while `start_practice.bat` remains open:

```bat
prepare_viva_campaigns.bat
```

The local Gophish database will contain one campaign for each supported category:

| Category | Viva campaign | Fictional recipient | Trigger |
| --- | --- | --- | --- |
| Credential Harvesting | VIVA 01 - Credential Harvesting | Amali Perera | test-form submission |
| Financial Fraud | VIVA 02 - Financial Fraud | Kasun Fernando | test-form submission |
| Social Engineering | VIVA 03 - Social Engineering | Nuwan Wickramasinghe | link click |
| Urgent Extortion | VIVA 04 - Urgent Extortion | Amaya Herath | link click |
| Malware Delivery | VIVA 05 - Malware Delivery | Dilini Jayasinghe | link click |

Each campaign uses a distinct colorful HTML email from `Member1/viva_templates/`, a fictional `@example.test` participant, the localhost SMTP proxy, and a safe landing/learning bridge. No password capture, payment capture, software download or external email is used. After seeding, switch the SecureSense dashboard source to **Live simulation** to show category coverage from actual local Gophish campaigns.

## A. Prepare Gophish once

1. Extract the official Gophish package, for example to `C:\Gophish`.
2. From the SecureSense project folder run:

```bat
.venv\Scripts\python.exe gophish_local_setup.py C:\Gophish
```

The helper backs up the existing Gophish configuration, binds the services to loopback and creates a local SAN certificate. If port 80 is unavailable, use for example:

```bat
.venv\Scripts\python.exe gophish_local_setup.py C:\Gophish --phish-port 8080
```

Then set `GOPHISH_PHISHING_URL=http://127.0.0.1:8080/` in `.env`.

3. Put the executable path and certificate path in `.env`:

```dotenv
GOPHISH_EXE=C:/Gophish/gophish.exe
GOPHISH_ADMIN_URL=https://127.0.0.1:3333
GOPHISH_CA_BUNDLE=C:/Gophish/securesense_admin.crt
```

4. Run `start_practice.bat`. If the launcher can find Gophish, it starts it together with the SecureSense services. Otherwise start `gophish.exe` manually from its own directory.
5. Open `https://127.0.0.1:3333`, sign in and change the initial Gophish administrator password when prompted.
6. Copy the local Gophish API key into the private `.env` as `GOPHISH_API_KEY=...`, then restart `start_practice.bat` so SecureSense reads it.

## B. Create the Sending Profile

Gophish -> **Sending Profiles** -> **New Profile**:

| Field | Value |
| --- | --- |
| Name | SecureSense Local SMTP |
| From | ShieldPay <support@shieldpay.example.test> |
| Host | **127.0.0.1:1027** |
| Username | blank |
| Password | blank |

Send a test message to `amali.perera@example.test`, then confirm it appears at `http://127.0.0.1:8025`.

## C. Create the Email Template

Gophish -> **Email Templates** -> **New Template**.

For the one-off manual account-security scenario import `Member1/shieldpay_gophish_email.html`; for the invoice/BEC scenario import `Member1/shieldpay_invoice_email.html`. The automated viva showcase uses the five richer templates in `Member1/viva_templates/`. Keep Gophish placeholders such as `{{.URL}}`, `{{.FirstName}}` and `{{.Tracker}}` intact.

## D. Create the initial safe Landing Page

Gophish -> **Landing Pages** -> **New Page** and import:

`Member1/shieldpay_landing_page.html`

For a form-submission exercise enable **Capture Submitted Data** but keep **Capture Passwords disabled**. The page is designed for a fictional test email only. Never enter real passwords, OTPs, card details or bank information.

## E. Create the target Group

Use only the fictional users in `05_practice_ACCOUNTS.md`. For a simple first run create a one-person group for Amali Perera:

- First name: Amali
- Last name: Perera
- Email: `amali.perera@example.test`
- Position: Finance

## F. Create the Campaign

Gophish -> **Campaigns** -> **New Campaign**:

- Name: `ShieldPay Account Security Exercise`
- Email Template: the template created above
- Landing Page: the safe landing page
- URL: `http://127.0.0.1` or your configured phishing port such as `http://127.0.0.1:8080`
- Sending Profile: `SecureSense Local SMTP`
- Group: the fictional target group

Do **not** use `https://127.0.0.1:3333` as the campaign URL. Port 3333 is the administrator interface.

## G. Synchronize the campaign into SecureSense

1. Open SecureSense as `admin@example.test`.
2. Go to **Integration setup -> Synchronize live Gophish campaign**.
3. Copy `examples/gophish_sync.json`, replace the placeholder campaign ID and launch time, choose the correct category/objective and submit it.
4. This imports the Gophish recipient mappings and native timeline. Synchronization does not launch or send a campaign.

For continuous polling, edit `examples/gophish_profiles.json` with the approved live campaign and run in a separate terminal:

```bat
.venv\Scripts\python.exe sync_gophish.py examples\gophish_profiles.json --interval 10
```

The poller asks for the SecureSense administrator login unless `SECURESENSE_SYNC_EMAIL` and `SECURESENSE_SYNC_PASSWORD` are set locally.

## H. Generate the targeted-learning bridge

1. SecureSense -> **Integration setup -> Generate campaign learning landing HTML**.
2. Start from `examples/learning_bridge.json`.
3. Use `test_form_submission` for a form exercise or `clicked` for a click-triggered exercise.
4. Download the generated campaign-specific landing HTML.
5. Replace the HTML of the **same Gophish landing page used by that campaign** with the generated bridge HTML.
6. Keep polling active. Open the campaign email in the local inbox and perform the configured trigger.
7. Sign in using the matching fictional employee account. Once the imported telemetry confirms the trigger, SecureSense opens the category-specific learning learning task.

The bridge is campaign-specific and expires. Regenerate it if expired; never reuse one campaign's bridge for another campaign.
