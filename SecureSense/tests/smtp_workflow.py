"""Local SMTP relay-to-inbox check. Run from project root, with ports free."""

import subprocess, sys, time, smtplib, json, os
from pathlib import Path
from email.message import EmailMessage
import httpx

ROOT = Path(__file__).resolve().parents[1]
PROXY_PORT = int(os.getenv("TEST_PROXY_PORT", "11027"))
MAILBOX_SMTP_PORT = int(os.getenv("TEST_MAILBOX_SMTP_PORT", "11026"))
MAILBOX_WEB_PORT = int(os.getenv("TEST_MAILBOX_WEB_PORT", "18025"))
if __name__ == "__main__":
    children = []
    try:
        for name in ["mail_sandbox.py", "smtp_proxy.py"]:
            children.append(
                subprocess.Popen(
                    [sys.executable, str(ROOT / "Member1" / name)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    env=dict(os.environ, PROXY_PORT=str(PROXY_PORT), RELAY_PORT=str(MAILBOX_SMTP_PORT), MAILBOX_SMTP_PORT=str(MAILBOX_SMTP_PORT), MAILBOX_WEB_PORT=str(MAILBOX_WEB_PORT)),
                )
            )
        ready = False
        for _ in range(100):
            try:
                with smtplib.SMTP("127.0.0.1", PROXY_PORT, timeout=0.5) as smtp:
                    smtp.noop()
                if (
                    httpx.get(f"http://127.0.0.1:{MAILBOX_WEB_PORT}", trust_env=False).status_code
                    == 200
                ):
                    ready = True
                    break
            except Exception:
                pass
            time.sleep(0.1)
        assert ready, "Local services did not start"
        msg = EmailMessage()
        msg["From"] = "simulation@example.test"
        msg["To"] = "test@example.test"
        msg["Subject"] = "SecureSense local relay verification"
        msg["X-Gophish-Contact"] = "test@example.test"
        msg.set_content("Authorized local test.")
        msg.add_alternative(
            '<h1>Controlled local message</h1><a href="?rid=fixture">Test link</a><script>window.parent.testLeak=true</script>',
            subtype="html",
        )
        with smtplib.SMTP("127.0.0.1", PROXY_PORT, timeout=5) as smtp:
            smtp.send_message(msg)
        for _ in range(50):
            inbox = httpx.get(f"http://127.0.0.1:{MAILBOX_WEB_PORT}", trust_env=False)
            if msg["Subject"] in inbox.text:
                break
            time.sleep(0.1)
        assert msg["Subject"] in inbox.text
        message = httpx.get(f"http://127.0.0.1:{MAILBOX_WEB_PORT}/message/0", trust_env=False)
        assert (
            'sandbox="allow-same-origin allow-popups allow-popups-to-escape-sandbox allow-top-navigation-by-user-activation"'
            in message.text
        )
        assert 'src="/message/0/body"' in message.text
        body = httpx.get(f"http://127.0.0.1:{MAILBOX_WEB_PORT}/message/0/body", trust_env=False)
        # Email links navigate the whole tab (the email sits in an iframe), never a new tab.
        assert 'target="_top"' in body.text and 'target="_blank"' not in body.text
        assert "http://127.0.0.1/?rid=fixture" in body.text
        assert body.headers["X-Frame-Options"] == "SAMEORIGIN"
        assert "script-src 'none'" in body.headers["Content-Security-Policy"]
        # The outer message page runs only its own mailbox.js (Report Phishing button).
        assert "script-src 'self'" in message.headers["Content-Security-Policy"]
        assert 'class="topbar"' in message.text
        result = {
            "checks": [
                "Local SMTP relay delivered to in-memory sandbox",
                "Relative Gophish URL mapped to phishing server",
                "Email HTML isolated in iframe with scripts disabled",
            ],
            "status": "passed",
        }
        (ROOT / "evidence").mkdir(exist_ok=True)
        (ROOT / "evidence/smtp_results.json").write_text(json.dumps(result, indent=2))
        print(json.dumps(result))
    finally:
        for child in children:
            child.terminate()
        for child in children:
            child.wait(timeout=5)
