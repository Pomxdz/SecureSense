# Port compatibility update

- Changed the local mail sandbox SMTP default from port 1026 to **1028** because 1026 is unavailable on the target PC; the Gophish-facing proxy remains on 1027.

# Viva showcase additions

- Added `seed_viva_gophish.py` and `prepare_viva_campaigns.bat` to create/reuse five localhost-only Gophish campaigns covering Credential Harvesting, Financial Fraud, Social Engineering, Urgent Extortion and Malware Delivery.
- Added five colorful responsive HTML simulation emails under `Member1/viva_templates/`; all use fictional branding, `.test` recipients, local tracking links and no external assets.
- Added optional automatic campaign seeding from `start_practice.bat` when Gophish is running and the local API key/certificate are configured.
- The viva seeder synchronizes the five native Gophish campaigns into SecureSense and refreshes category-specific learning bridges while keeping password capture disabled.
- Added `Walkthrough_Documents/06_VIVA_CAMPAIGN_SHOWCASE.md` and updated the quick start, Gophish guide, end-to-end script, troubleshooting guide, walkthrough DOCX and technical report.
- Re-ran the core API/regression suite after these changes: 53/53 passed.
# Submission-ready packaging changes

- Added `practice_launcher.py`; `start_practice.bat` now starts SecureSense, local inbox SMTP/web service and the SMTP proxy together, with optional local Gophish auto-start.
- Moved the exercise SMTP proxy default to port 1027 because port 1025 is reserved on the target laptop.
- Consolidated runtime dependencies and exercise documentation.
- Removed duplicate per-member requirement/documentation stubs, the obsolete `campaign_import.json` example, and the byte-for-byte duplicate frontend index page.
- Reorganized current walkthroughs under `Walkthrough_Documents/` and reports/reference evidence under `Documentation/`.

# Version 3 changes

- Added automatic anonymized Gemini scoring jobs with validation, lineage, retries, stale-output handling and explicit separation from rules indicators.
- Added expiring campaign-specific learning bridges for click and submission triggers; matching login and observed telemetry are required.
- Added six distinct lessons with five category-specific questions each; retained independent server grading and optional Jigsaw practice.
- Added a safe invoice/BEC-style email scenario and category-aware generated landing pages alongside the account-review exercise.
- Added GRC internal awareness evidence, owners, review dates, audit updates and export.
- Added local certificate preparation with localhost/IP SANs and certificate-verified Gophish API requests that ignore unrelated proxy environment settings.
- Verified actual Gophish account, invoice and click-only workflows using loopback SMTP and fictional identities.
- Updated implementation guides and alignment notes; omitted obsolete reports, runtime data, secrets, caches and raw logs.
- Preserved existing named employee roster, rule scoring, behavioral journeys, filters, retests and authentication safeguards.
