# Submission manifest and cleanup record

## Submission-ready changes

- `start_practice.bat` now starts the complete SecureSense-owned backend stack through `practice_launcher.py` instead of only starting FastAPI.
- SMTP proxy default changed from 1025 to **1027** to avoid the antivirus-reserved port on the exercise laptop.
- Local mail sandbox ports are environment-configurable.
- Optional Gophish auto-start is supported through `GOPHISH_EXE`; the official engine remains external and is not redistributed.
- Runtime dependencies were consolidated into one `requirements.txt`; test-only packages are in `requirements-dev.txt`.
- Walkthrough material was consolidated under `Walkthrough_Documents/` and all links/instructions updated to the current launcher and port layout.
- Reference/report material was separated under `Documentation/`.
- Legacy/duplicate per-member requirement files, the obsolete campaign-import example, and the byte-for-byte duplicate frontend index/login page were removed.
- Runtime secrets, databases, caches, evidence output and logs remain excluded by `.gitignore` and are not included in the clean archive.
- A localhost-only viva campaign seeder now creates/reuses five Gophish category campaigns through the official API rather than shipping or directly editing a Gophish database.
- Five colorful safe email templates are retained under `Member1/viva_templates/`, and a dedicated viva showcase walkthrough is retained under `Walkthrough_Documents/`.

## Files deliberately retained

- All three functional member source areas.
- Current Gophish templates and live integration scripts.
- Regression, SMTP, browser and isolated Gophish workflow checks as verification evidence.
- Proposal alignment, behavioral-analysis methodology, test evidence and technical report.

## External dependency not bundled

Gophish is an official third-party executable and must be downloaded separately. `gophish_local_setup.py` prepares a local loopback configuration and certificate without redistributing the Gophish binary.
