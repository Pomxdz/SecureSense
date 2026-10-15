# Proposal alignment and submission evidence

The implementation follows the supplied three-tier proposal. The original proposal and signatures have not been changed. Version 3 closes the earlier implementation gaps without replacing unknown real-world evidence with invented results.

| Proposal promise | Implementation | Evidence and limit |
| --- | --- | --- |
| Gophish simulations and scheduling | Official engine integration, local SMTP services, account and invoice templates | Actual local engine checked; external enterprise mail not tested |
| Secure Python webhook middleware | HMAC, normalized campaign mappings, deduplication, bounded metadata ingestion | Regression tests; campaign API polling supplements incomplete global webhook context |
| Generative AI calculates behavioral scores | Automatic anonymized assessment queue and validated model-generated 0–100 score | SDK configuration and mocked positive/invalid responses tested; successful external Gemini call still requires a valid account key/model |
| Individual histories and scores in SQL | Events, rule assessment snapshots, AI jobs/results with evidence fingerprint, model and timestamps | SQLite persistence verified; AI and rules labels remain distinct |
| Immediate targeted micro-learning | Expiring campaign handoff; matching account authentication; verified click or submission opens correct lesson | Actual local Gophish account, invoice and click-only workflows checked |
| Specific quizzes based on failure vector | Six distinct lessons; five category-specific questions each; graded 80% pass | Tests and browser workflows; Jigsaw is supplementary external practice |
| Executive and departmental dashboard | Source-separated rates, journeys, departments, trends, AI scores, retests and actions | Browser checks; AI overview scope explicitly separate from other filters |
| Compliance audit support | Four internal awareness requirements, evidence summary, owner, review date and export | Supports audit review; does not establish certification or full compliance |
| Privacy without capturing sensitive simulation credentials | Safe fictional-email form; password capture disabled; SecureSense stores only event metadata; anonymized AI inputs | Auth password hashes are separate from simulation submissions |

## What cannot be fabricated

- Actual team working hours, equal contributions and Kanban history must come from your team’s real records. A 30-hour proposal constraint is not proof of actual elapsed work.
- A successful remote Gemini score needs a valid provider key and an available model. Missing or failed service remains visibly unavailable. The ZIP contains no fake Gemini-generated scores.
- Synthetic retests show behavior comparisons, not measured human learning effectiveness or causation. A consented participant evaluation needs your own observations.
- External deployment and organization-specific compliance approval are beyond the local prototype. AI usage may incur provider costs; zero-cost access is not guaranteed.
- Check the cover’s degree specialization against the official program before submission. The supplied proposal says Information Technology; do not silently assume this administrative wording is correct.
- Correct the proposal’s unnumbered Figure captions using your document editor. Current implementation guides have clear numbered screenshots and describe the completed design.

## Evidence capture checklist

Record the localhost engine configuration, certificate-verified import, an account exercise, invoice exercise, automatic learning handoff, graded pass, dashboard evidence and comparable retest. If Gemini is configured, capture its current model, generated time, score/explanation and unavailable/retry behavior without exposing the key. Keep real human-study results separate from fixtures. Attach your genuine contribution and time records rather than backdating the generated implementation.
