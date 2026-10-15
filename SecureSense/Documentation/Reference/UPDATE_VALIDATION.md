# Current validation

- 58 backend workflow tests passed.
- 12 browser UI checks passed without page errors.
- Actual local SMTP proxy-to-inbox integration passed.
- Five complete browser journeys passed: SMTP delivered HTML email -> visible protected email frame -> top-level branded landing -> native-shaped signed fixture telemetry -> corresponding employee login -> matching quiz -> 100% result -> persisted passed learning task.
- Fresh/reused campaign lifecycle checked against a mocked API.
- Native Windows Gophish executable was not run here. The browser journeys use a local fixture phishing server, not real engine delivery.

The blocked-content screenshot was caused by DENY framing on a srcdoc email frame. Email body now has a dedicated same-origin route with SAMEORIGIN framing; all other inbox pages retain DENY. Scripts remain disabled in the email body. Links explicitly navigate the top-level tab so landing scripts/forms run outside the protected frame. Existing email templates are refreshed through the official API.
