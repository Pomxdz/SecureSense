# Verification results

The latest automated regression run executed **72 pytest cases** covering authentication, access control, Gophish integration fixtures, phishing landing-page behavior, AI score validation, targeted learning, quiz processing, phishing reporting, and GRC evidence. The final recorded run completed with **72 passed, 0 failed, 2 warnings in 17.19 seconds**.

| Area | Result |
| --- | --- |
| Latest automated regression suite | 72 passed, 0 failed |
| Pytest warnings | 2 non-critical dependency deprecation warnings |
| Execution time | 17.19 seconds |
| Retained browser workflow verification | 12 checks passed in the earlier proposal-aligned verification cycle |
| Retained local Gophish workflow verification | 21 checks passed in the earlier proposal-aligned verification cycle |

The automated suite verifies the behavior represented by its test cases; it does not independently prove long-term human learning effectiveness, production-scale reliability, or continuous availability of external services. Provider-backed AI scoring still requires a valid `GROQ_API_KEY` and `GROQ_MODEL`. Missing or failed provider access remains an explicit unavailable state rather than a fabricated score.

The retained browser and local Gophish figures above are historical integration evidence from the earlier proposal-aligned verification cycle. All recipients and exercises used fictional identities and local/loopback services; no external email was required.

## Repeat the automated regression suite

```sh
python -m pip install -r requirements-dev.txt
python -m pytest tests/test_workflow.py -q
```

Optional browser and isolated real-Gophish checks require Playwright Chromium and an extracted official Gophish engine:

```sh
python -m playwright install chromium
python tests/browser_workflow.py
python tests/gophish_workflow.py /path/to/extracted/gophish
```

Tests create runtime state locally. Databases, caches, private configuration, credentials, logs, and generated evidence are excluded from the GitHub-ready archive.
