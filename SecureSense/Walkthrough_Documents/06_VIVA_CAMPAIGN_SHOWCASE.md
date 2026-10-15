# Updated behavior

Read ../START_HERE.md (project root START_HERE.md) first. Each launcher run now creates a fresh five-campaign session, uses five matching branded landing pages, and automatically polls live events every 10 seconds. Manual prepare_viva_campaigns.bat reuses the current session. Older reuse/automatic-redirect descriptions below are superseded by START_HERE.md.

# Five-category viva campaign showcase

This build includes a localhost-only Gophish showcase so the viva can show every explicit phishing/social-engineering category supported by SecureSense without sending email outside the laptop.

## Categories included

| # | Category | Email theme | Fictional recipient | Learning trigger |
| --- | --- | --- | --- | --- |
| 1 | Credential Harvesting | SecureHub account protection | Amali Perera (`amali.perera@example.test`) | test-form submission |
| 2 | Financial Fraud | ApexPay supplier invoice change | Kasun Fernando (`kasun.fernando@example.test`) | test-form submission |
| 3 | Social Engineering | PeoplePlus employee reward | Nuwan Wickramasinghe (`nuwan.wickramasinghe@example.test`) | link click |
| 4 | Urgent Extortion | CoreGuard incident notice | Amaya Herath (`amaya.herath@example.test`) | link click |
| 5 | Malware Delivery | WorkSuite update notice | Dilini Jayasinghe (`dilini.jayasinghe@example.test`) | link click |

`General` remains a fallback training category rather than a dedicated viva lure.

## One-time prerequisites

1. Prepare the official local Gophish engine using `gophish_local_setup.py`.
2. Put the local executable path, trusted SAN certificate and API key in the private `.env`.
3. Keep the phishing URL on loopback, for example `http://127.0.0.1/` or `http://127.0.0.1:8080/`.
4. Keep the Gophish SMTP profile on `127.0.0.1:1027`.

The seeder deliberately refuses non-loopback Gophish/phishing URLs. All targets use the reserved `.test` domain.

## Automatic setup

With this in `.env`:

```dotenv
VIVA_AUTO_SEED_GOPHISH=1
GOPHISH_API_KEY=YOUR_LOCAL_API_KEY
GOPHISH_CA_BUNDLE=C:/Gophish/securesense_admin.crt
```

running `start_practice.bat` automatically executes the viva seeder after SecureSense, the local inbox, SMTP proxy and Gophish are ready.

Manual alternative:

```bat
prepare_viva_campaigns.bat
```

The operation is idempotent. Existing named campaigns are reused instead of launching duplicates. Rerunning it refreshes the 7-day targeted-learning bridge tickets.

## What gets created in Gophish

- `SecureSense Viva Local SMTP` using `127.0.0.1:1027`.
- Five colorful, responsive HTML email templates from `Member1/viva_templates/`.
- Five safe landing pages with password capture disabled.
- Five one-person fictional target groups.
- Five local campaigns named `VIVA 01` through `VIVA 05`.
- A SecureSense live-campaign record for each Gophish campaign.
- A campaign-specific targeted-learning bridge for each scenario.

The first run sends five fictional messages through the local SMTP chain into `http://127.0.0.1:8025`. It does not send external email.

## Recommended viva sequence

1. Show **Gophish -> Campaigns** and point out all five categories.
2. Show **Email Templates** and open two or three colorful designs.
3. Open the local inbox and show the five messages side-by-side.
4. Choose one scenario to execute live. Credential Harvesting or Financial Fraud shows the safe test-email form; the other three show click-based learning handoff.
5. After the interaction, run the Gophish poller if needed, then select **Live simulation** in SecureSense.
6. Show Category outcomes, campaign evidence and the participant timeline.
7. Sign in as the matching fictional employee and show the category-specific learning module and five-question quiz.
8. Return to the dashboard to show training evidence and behavioral assessment.

## Email design notes

The templates use only inline HTML/CSS, gradients, colored information cards and a single local Gophish CTA. They do not load external images or scripts. Each template includes an authorization footer and a reminder not to provide real credentials, payment data, secrets or software permissions.

## Reset

For a completely fresh Gophish showcase, use a clean local Gophish database/profile and rerun the seeder. Do not delete or directly edit the Gophish SQLite database during a viva; use the official API and UI so campaign relationships remain valid.
