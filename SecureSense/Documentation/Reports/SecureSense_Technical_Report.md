# Reference document

Current operating instructions are in START_HERE.md. The following retained reference describes the earlier architecture; changed screens and startup names are superseded by that guide.

SecureSense Technical Report

Version 3 implements the proposed Gophish, Python SQL AI and dashboard architecture as a local learning task prototype. It adds automatic model-generated behavioral assessments, authenticated point-of-interaction learning and category-specific quizzes to the earlier reproducible behavioral analysis. The system supports awareness evidence review without claiming enterprise certification or measured human-training effectiveness.

Implemented architecture

Tier

Implementation

Simulation

Separate official Gophish engine; local SMTP proxy and sandbox; account and invoice exercise templates; campaign scheduling in Gophish.

Middleware

FastAPI normalizes signed webhooks and campaign API timelines. SQLite preserves evidence, assignments, assessment lineage and audit records. A background queue calls Gemini when configured.

Application

Role-restricted administrator dashboard, employee portal, authenticated learning handoff, graded training and internal GRC evidence review.

Module responsibilities

Member 1 components provide simulation templates and local mail transport. Member 2 components provide event normalization, persistence, Gemini jobs, access checks and grading. Member 3 components present dashboards, lessons, quizzes and integration operations. These component responsibilities do not prove actual personal contribution or working hours.

Verification scope

The regression suite covers 53 cases. Twelve browser checks verify the portal and Jigsaw separation. Twenty-one actual local Gophish checks cover account, invoice and click-only campaign-to-learning workflows. Positive Gemini responses were fixture-tested; a successful remote generation is not claimed without a genuine key and model.

Behavioral evidence and reproducible scoring

The unit of analysis is one recipient in one campaign. Multiple clicks and repeated webhook deliveries do not create extra failed people. Sending eligibility uses normalized successful sending events. An Email Sent event does not prove inbox delivery, reading or human intent. Campaign IDs and recipient tracking mappings are explicit; ambiguous events are quarantined instead of assigned by guesswork.

Observed outcome

Rule severity

Test-form submission

80

Click without submission

40

Report without interaction

0

No assessable recorded action

Unknown; excluded from severity mean

The reproducible indicator is mean assessable severity plus recurrence, capped at 100. Recurrence is 20 multiplied by max(0, interaction campaigns minus 1), divided by successfully sent campaign observations. Multiple clicks within a campaign count once. A submission implies interaction even when click telemetry is missing.

Journeys and context

Reporting without interaction, reporting before a later interaction, clicking then reporting, submitting then reporting and no observed action remain distinct. Reporting after exposure is recovery and does not subtract points. Category, difficulty, objective and persuasion remain visible; overlapping tags describe message associations rather than employee motives.

Uncertainty

Coverage is limited below three assessable outcomes, moderate for three to five and broader for six or more. These labels describe evidence quantity. Rate tables show counts and descriptive Wilson intervals; correlated observations from repeated participants do not establish causal effects. Missing timestamps stay unknown. Fast action is not treated as proof of impulsiveness.

Automatic AI behavioral assessments

New normalized evidence automatically creates an anonymized assessment job. On startup, current participant evidence is queued when the service is configured. A background worker checks for jobs every two seconds and uses a 15-second network timeout. Pending older snapshots are superseded to reduce obsolete requests. The system stores AI-generated scores separately from the deterministic rule comparator.

Stored field

Purpose

Evidence fingerprint and source

Tie the output to a particular practice or live history.

Model and timestamps

Record which configured model generated the output and when.

Score and explanation

Validated finite 0 to 100 indicator and bounded plain-language reasoning.

Recommendation

An allowed learning category; advisory rather than a replacement for the observed failure vector.

Status and attempts

Pending, running, available, unavailable, failed, unassessed or superseded states; failures retry up to three times.

The model receives category, difficulty, journey, relative click/report times and summarized evidence. Names, emails, tracking IDs, form values, IP addresses and user agents are omitted. The reproducible comparator is supplied as context. The model is instructed not to infer personality, diagnosis, compromise probability or causation.

Invalid scores, non-finite values, invalid recommendations and malformed replies never become a fabricated zero. Missing credentials/model remain unavailable; no assessable evidence remains unassessed. Current profiles hide scores tied to stale evidence. Administrators can queue an explicit retry. Model outputs are experimental, not independently calibrated; deterministic settings do not guarantee identical outputs.

Live configuration limit

The submission-ready runtime requirements include the Google GenAI SDK. Set GEMINI_API_KEY and GEMINI_MODEL in a private .env, then restart the launcher. The installed SDK configuration and successful/invalid mocked outputs were checked. Remote success still requires an account key and available model. Provider access and cost cannot be guaranteed by the prototype.

Targeted learning and secure handoff

An observed interaction creates an learning task unique to recipient, campaign and category. The administrator generates campaign-specific landing HTML after importing mappings. A submission bridge records the native Gophish form POST before navigating to the learning entry; a click bridge navigates immediately after opening the native campaign page. The selected trigger is checked against imported evidence.

The handoff contains an opaque, expiring campaign ticket and recipient tracking ID. Only the token hash is stored; tickets expire after seven days. A ticket never signs in a participant or creates an interaction from a GET. The participant must authenticate with the matching account, and the required click or submission must be present before the learning task opens. Missing telemetry waits for polling or webhook ingestion. Suspected scanner evidence is withheld.

Category

Lesson focus

Credential Harvesting

Unexpected forms, full domains, independent official access and reporting.

Financial Fraud

Invoice changes, trusted supplier contacts, payment approvals and recovery.

Urgent Extortion

Threats, pausing, preserving evidence and independent escalation.

Social Engineering

Impersonation, authority pressure and attempts to bypass procedures.

Malware Delivery

Unexpected attachments and approved software/update channels; harmless examples only.

General

Recognize, verify and report.

Each category has four distinct lesson paragraphs and five category-specific questions. The server records attempts and grades at least four correct answers as passed. Opening a lesson does not pass it. A later failed review does not erase a previous pass; canceled assignments retain attempts while leaving active denominators.

Google Jigsaw is optional general phishing practice opened externally. SecureSense cannot verify its results, and neither opening nor completing it changes learning task completion or behavioral scores. Comparable retests require matching source, category, difficulty and objective after a pass; lower observed severity is not proof of training causation.

Dashboard GRC evidence and safeguards

The dashboard separates practice and live sources and provides filters for department, campaign, category, difficulty and dates. It shows journeys, rates, contextual trends, individual histories, learning, retests and owner/date follow-up actions. The automatic AI overview covers all participants in the selected source; other dashboard filters do not apply to that panel and its scope is labelled.

Figure 1. Verified local dashboard using synthetic fixtures. Full-page views also show the automatic AI and GRC sections below the summary.

GRC awareness evidence

Internal requirements AW-01 through AW-04 cover authorized simulation evidence, verified learning, effectiveness follow-up and privacy/data-quality review. Each has evidence, owner, review date and an authenticated export. Owner/date edits are audited. Review required is a governance action, not a claim of certification or complete organizational compliance.

Security controls

Passwords use salted PBKDF2 hashes. Revocable role-restricted sessions, login limits, bounded HMAC webhook ingestion, safe DOM construction, restrictive content security policy and isolated email HTML reduce prototype risks. Simulation form values are not persisted in SecureSense. CSV exports neutralize spreadsheet formula prefixes. Gophish API certificate verification stays enabled.

Deployment evaluation and proposal alignment

Start the local practice with start_practice.bat. The submission-ready launcher starts SecureSense, the local mail sandbox and the SMTP proxy together, and can also auto-start a separately installed official Gophish executable when GOPHISH_EXE is configured. The default Gophish-facing SMTP proxy port is 1027. When the local Gophish API key and trusted CA bundle are configured, the launcher can idempotently create or reuse five localhost-only viva campaigns covering Credential Harvesting, Financial Fraud, Social Engineering, Urgent Extortion and Malware Delivery, then synchronize them into SecureSense and refresh their targeted-learning bridges. The certificate helper creates a localhost/IP SAN certificate and backs up configuration. Use the actual phishing-server URL in campaigns; port 3333 is administration. Keep password capture disabled and use fictional test-email fields only.

Campaign synchronization imports native results and timelines without launching campaigns. Some native campaign-created events are intentionally unsupported and quarantined. Global webhooks can lack enough campaign context for some sending events; campaign-scoped polling repairs this context. The learning handoff may wait for the next synchronization interval, so near-real-time ingestion should not be described as instantaneous delivery.

Actual local engine evidence

The official Gophish v0.12.1 engine was exercised on loopback with fictional account, invoice and click-only campaigns. Tests verified HTTPS trust, native mappings and interactions, authenticated handoff, correct category lessons, server-graded passes and the live dashboard. The browser fixture used a normal browser user-agent to exercise the human-evidence path; scanner-like evidence remains subject to review. No external mail or real participant study was performed.

Submission limits and records

The proposal’s automatic AI scoring and targeted redirection are now implemented alongside the richer reproducible analysis. A remote Gemini response still needs genuine credentials. Human effectiveness measurements, actual equal contributions, Kanban history and a 30-hour work record must come from the team’s real evidence. These cannot be fabricated from software tests. Verify administrative degree wording and proposal captions against the final submission requirements.

This SQLite/localhost application is an learning task prototype. Enterprise identity, distributed resilience, production HTTPS for SecureSense, organization-approved retention and monitoring require further deployment work. See Documentation/Reference/PROPOSAL_ALIGNMENT.md and Documentation/Reference/TEST_RESULTS.md for traceability and verification limits.

Technical references

Gophish User Guide and API documentation: https://docs.getgophish.com/Google GenAI Python SDK: https://github.com/googleapis/python-genaiGemini structured output documentation: https://ai.google.dev/gemini-api/docs/structured-output