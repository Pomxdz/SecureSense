import threading
import re

from email.message import EmailMessage
from html import escape, unescape
from pathlib import Path
import sys
import secrets
import httpx
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gophish_reporting import report_to_gophish

from aiosmtpd.controller import Controller
from aiosmtpd.handlers import AsyncMessage
from flask import request, Flask, jsonify, Response
import os
from urllib.parse import urlsplit, parse_qs

# ============================================================
# CONFIGURATION
# ============================================================

# smtp_proxy.py forwards simulation emails here
SMTP_HOST = os.getenv("MAILBOX_SMTP_HOST", "127.0.0.1")
SMTP_PORT = int(os.getenv("MAILBOX_SMTP_PORT", "1028"))

# Browser-accessible test inbox
WEB_HOST = os.getenv("MAILBOX_WEB_HOST", "127.0.0.1")
WEB_PORT = int(os.getenv("MAILBOX_WEB_PORT", "8025"))

# Gophish phishing server.
# Everything is currently running on the same laptop.
GOPHISH_BASE_URL = (
    os.getenv("GOPHISH_PHISHING_URL", "http://127.0.0.1/").rstrip("/") + "/"
)
if urlsplit(GOPHISH_BASE_URL).scheme not in ("http", "https"):
    raise ValueError("GOPHISH_PHISHING_URL must be an HTTP or HTTPS URL")


# ============================================================
# IN-MEMORY MAILBOX
# ============================================================

messages = []


# ============================================================
# EMAIL DECODING
# ============================================================


def decode_part(part):
    """
    Safely decode an email MIME part.
    """

    try:
        payload = part.get_payload(decode=True)

        if payload is None:

            raw_payload = part.get_payload()

            if isinstance(raw_payload, str):
                return raw_payload

            return str(raw_payload)

        charset = part.get_content_charset() or "utf-8"

        return payload.decode(charset, errors="replace")

    except Exception as error:

        print("Decode error:", error)

        return ""


# ============================================================
# HTML DETECTION
# ============================================================


def looks_like_html(content):
    """
    Detect HTML even if the email was labelled text/plain.
    """

    if not content:
        return False

    value = content.strip().lower()

    html_markers = [
        "<!doctype html",
        "<html",
        "<body",
        "<table",
        "<div",
        "<a ",
    ]

    return any(marker in value for marker in html_markers)


# ============================================================
# GOPHISH LINK FIX
# ============================================================


def fix_gophish_links(html_content):
    """
    Gophish may generate a relative tracking URL such as:

        ?rid=ABC123

    When rendered inside this Flask mailbox, the browser would
    incorrectly resolve that against:

        http://127.0.0.1:8025/message/...

    This converts the relative URL into:

        http://127.0.0.1/?rid=ABC123

    so the click goes to the local Gophish phishing server.
    """

    if not html_content:
        return html_content

    fixed_html = re.sub(r'<p\b[^>]*>\s*<a\b[^>]*href=["\'][^"\']*#report(?:Url|Rid)=[^"\']*["\'][^>]*>.*?</a>\s*</p>', '', html_content, flags=re.I | re.S)

    # --------------------------------------------------------
    # Case 1
    #
    # href="?rid=ABC123"
    # --------------------------------------------------------

    fixed_html = re.sub(
        r'href\s*=\s*["\']\?rid=([^"\']+)["\']',
        lambda match: f'href="{GOPHISH_BASE_URL}?rid={match.group(1)}"',
        fixed_html,
        flags=re.IGNORECASE,
    )

    # --------------------------------------------------------
    # Case 2
    #
    # href="/?rid=ABC123"
    # --------------------------------------------------------

    fixed_html = re.sub(
        r'href\s*=\s*["\']/\?rid=([^"\']+)["\']',
        lambda match: f'href="{GOPHISH_BASE_URL}?rid={match.group(1)}"',
        fixed_html,
        flags=re.IGNORECASE,
    )

    # Links in the email open the landing page in the SAME tab. The email is shown
    # inside an iframe, so "_top" replaces the whole tab instead of loading the
    # landing page inside the small email frame. No new tab is opened.
    def outside_frame(match):
        tag = match.group(0)
        tag = re.sub(r"\s+target\s*=\s*([\"']).*?\1", "", tag, flags=re.I)
        tag = re.sub(r"\s+rel\s*=\s*([\"']).*?\1", "", tag, flags=re.I)
        return tag[:-1] + ' target="_top">'
    fixed_html = re.sub(r"<a\b[^>]*>", outside_frame, fixed_html, flags=re.I)
    return fixed_html


# ============================================================
# SMTP HANDLER
# ============================================================


class MailSandbox(AsyncMessage):

    async def handle_message(self, message: EmailMessage):

        html_body = ""
        text_body = ""

        # ----------------------------------------------------
        # MULTIPART EMAIL
        # ----------------------------------------------------

        if message.is_multipart():

            for part in message.walk():

                # Skip multipart containers
                if part.is_multipart():
                    continue

                content_type = part.get_content_type()

                decoded = decode_part(part)

                if content_type == "text/html":

                    if decoded:
                        html_body = decoded

                elif content_type == "text/plain":

                    if decoded:
                        text_body = decoded

        # ----------------------------------------------------
        # SINGLE-PART EMAIL
        # ----------------------------------------------------

        else:

            content_type = message.get_content_type()

            decoded = decode_part(message)

            if content_type == "text/html":

                html_body = decoded

            else:

                text_body = decoded

        # ----------------------------------------------------
        # HTML INSIDE TEXT/PLAIN FIX
        # ----------------------------------------------------

        if not html_body and looks_like_html(text_body):

            html_body = text_body

            text_body = ""

        # ----------------------------------------------------
        # MESSAGE INFORMATION
        # ----------------------------------------------------

        sender = message.get("From", "")

        recipient = message.get("To", "")

        subject = message.get("Subject", "(No Subject)")

        simulation = message.get("X-Security-Awareness-Simulation", "")

        # ----------------------------------------------------
        # TERMINAL OUTPUT
        # ----------------------------------------------------

        print("\n" + "=" * 70)

        print("SIMULATION EMAIL RECEIVED")

        print("=" * 70)

        print("From       :", sender)

        print("To         :", recipient)

        print("Subject    :", subject)

        print("Simulation :", simulation)

        print("Content-Type :", message.get_content_type())

        print("HTML length  :", len(html_body))

        print("TEXT length  :", len(text_body))

        if html_body:

            print("Body type    : HTML")

        elif text_body:

            print("Body type    : Plain Text")

        else:

            print("Body type    : Empty")

        # Show whether a Gophish tracking link exists
        if "?rid=" in html_body:

            print("Gophish link : Detected")

        else:

            print("Gophish link : Not detected")

        print("=" * 70 + "\n")

        # ----------------------------------------------------
        # STORE MESSAGE
        # ----------------------------------------------------

        messages.append(
            {
                "from": sender,
                "to": recipient,
                "subject": subject,
                "html": html_body,
                "text": text_body,
                "simulation": simulation,
                "report_token": secrets.token_urlsafe(24),
            }
        )


# ============================================================
# FLASK APPLICATION
# ============================================================

app = Flask(__name__)


@app.after_request
def security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Frame-Options"] = "SAMEORIGIN" if request.path.endswith("/body") else "DENY"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; connect-src 'self'; style-src 'self' 'unsafe-inline'; img-src * data:; frame-src 'self'; form-action http://127.0.0.1 https://127.0.0.1; base-uri 'none'"
    )
    if request.path.endswith('/body'):
        response.headers['Content-Security-Policy'] = "default-src 'none'; script-src 'none'; style-src 'unsafe-inline'; img-src * data:; base-uri 'none'; form-action 'none'"
    return response


# ============================================================
# INBOX PAGE
# ============================================================


MAIL_CSS = """
:root{--ink:#0f213d;--muted:#5a6b82;--line:#dcebf6;--page:#f3f8fc;--blue:#0b7bb5;--danger:#c62828}
*{box-sizing:border-box}
body{margin:0;min-height:100vh;background:linear-gradient(180deg,#f3f9fe,#eef5fb);color:var(--ink);font:15px/1.55 Inter,"Segoe UI",system-ui,-apple-system,Roboto,Arial,sans-serif;-webkit-font-smoothing:antialiased}
.topbar{position:relative;overflow:hidden;display:flex;align-items:center;gap:16px;padding:0 32px;height:64px;background:linear-gradient(100deg,#e3f2fd 0,#d4ebfb 70%,#c6e5fa 100%);border-bottom:1px solid #c9e0f0;box-shadow:0 2px 10px rgba(30,80,130,.08);color:var(--ink)}
.topbar:before,.topbar:after{content:"";position:absolute;border-radius:50%;pointer-events:none}
.topbar:before{right:-120px;top:-170px;width:520px;height:520px;background:rgba(160,212,248,.45)}
.topbar:after{right:-230px;top:-250px;width:560px;height:560px;background:rgba(120,190,245,.55)}
.topbar>*{position:relative;z-index:1}
.brand-name{font-size:26px;font-weight:800;letter-spacing:-.9px;color:#0e2240}
.topbar .divider{width:1px;height:26px;background:#b7d3e8}
.topbar .page-name{font-size:15px;font-weight:500;color:#2c4766}
.container,.message-container{width:min(1180px,calc(100% - 80px));margin:32px auto;background:#fff;border:1px solid var(--line);border-radius:18px;padding:22px;box-shadow:0 10px 40px rgba(30,80,130,.08)}
.container{margin:32px auto}
.message-container{margin:20px auto 32px;padding:14px}
.mail-table{border:1px solid #dcebf6;border-radius:14px;overflow:hidden}
table{width:100%;border-collapse:collapse;font-size:14px}
th{text-align:left;padding:14px 22px;color:#4a5b72;font-size:13px;font-weight:600;background:#e3f1fc}
td{padding:15px 22px;border-top:1px solid #dcebf6;vertical-align:middle}
td.addr strong{display:block;font-size:14.5px;font-weight:700;color:#0e2240}
td.addr span{display:block;color:#5a6b82;font-size:13px;margin-top:1px;overflow-wrap:anywhere}
td.subject{width:34%}
tr:hover td{background:#f6fbff}
a{color:var(--blue);text-decoration:none;font-weight:600}
a:hover{text-decoration:underline}
.empty{text-align:center;padding:60px;color:var(--muted)}
.notice,.simulation-label{background:#fdf1dc;color:#5c3a05;border:1px solid #f4dcae;padding:12px 16px;border-radius:10px;margin-bottom:20px;font-size:14px}
.toolbar{display:flex;justify-content:space-between;align-items:center;gap:16px;flex-wrap:wrap;background:#fff;padding:12px 32px;border-bottom:1px solid var(--line)}
.email-info{background:#fff;padding:14px 32px;border-bottom:1px solid var(--line);line-height:1.7;font-size:14px}
.plain-text{white-space:pre-wrap;word-wrap:break-word;font-family:inherit}
#reportPhishing{margin-left:auto;background:var(--danger);color:#fff;border:0;border-radius:10px;padding:9px 18px;font:inherit;font-size:14px;font-weight:700;cursor:pointer}
#reportPhishing:hover{background:#a51f1f}
#reportPhishing:disabled{background:#8497aa;cursor:default}
#reportPhishing:focus-visible{outline:3px solid #7cc1ee;outline-offset:3px}
#reportStatus{width:100%;margin:0;color:#17603a;font-size:14px}
#reportStatus:empty{display:none}
@media(max-width:760px){.topbar{height:58px;padding:0 16px;gap:10px}.brand-name{font-size:22px}.topbar .page-name{font-size:14px}.container,.message-container{width:auto;margin:18px 12px;padding:14px;border-radius:18px}th,td{padding:10px 12px}th{font-size:12.5px}table{font-size:13.5px}td.subject{width:auto}.toolbar,.email-info{padding:14px 18px}}
"""

TOPBAR = '<div class="topbar"><span class="brand-name">SecureSense</span><span class="divider" aria-hidden="true"></span><span class="page-name">Simulation mailbox</span></div>'


def split_address(value):
    """Split '"Name" <a@b>' into (name, address) for a two-line display."""
    m = re.match(r'^\s*"?(.*?)"?\s*<([^<>]+)>\s*$', value or "")
    if m and m.group(1):
        return m.group(1), "<" + m.group(2) + ">"
    return value or "", ""


def address_cell(value):
    name, addr = split_address(value)
    inner = f"<strong>{escape(name)}</strong>" + (f"<span>{escape(addr)}</span>" if addr else "")
    return f'<td class="addr">{inner}</td>'


@app.route("/")
def inbox():

    rows = ""

    # Newest email first
    for i, msg in enumerate(reversed(messages)):

        real_index = len(messages) - 1 - i

        rows += (
            "<tr>"
            + address_cell(msg["from"])
            + address_cell(msg["to"])
            + f'<td class="subject"><a target="_blank" rel="noopener" href="/message/{real_index}">{escape(msg["subject"])}</a></td>'
            + "</tr>"
        )

    # --------------------------------------------------------
    # EMPTY INBOX
    # --------------------------------------------------------

    if not rows:

        rows = """
        <tr>

            <td
                colspan="3"
                class="empty"
            >

                No simulation emails received yet.

            </td>

        </tr>
        """

    # --------------------------------------------------------
    # INBOX HTML
    # --------------------------------------------------------

    return f"""
    <!DOCTYPE html>

    <html lang="en">

    <head>

        <meta charset="UTF-8">

        <meta
            name="viewport"
            content="width=device-width,
            initial-scale=1.0"
        >

        <title>
            SecureSense · Simulation mailbox
        </title>


        <style>{MAIL_CSS}</style>

    </head>


    <body>
        {TOPBAR}
        <div class="container">


            <div class="mail-table"><table>


                <thead>

                    <tr>

                        <th>
                            From
                        </th>

                        <th>
                            To
                        </th>

                        <th>
                            Subject
                        </th>

                    </tr>

                </thead>


                <tbody>

                    {rows}

                </tbody>


            </table></div>


        </div>


    </body>

    </html>
    """


# ============================================================
# INDIVIDUAL EMAIL VIEW
# ============================================================



def message_rid(msg):
    content = unescape(msg.get('html', '') + ' ' + msg.get('text', ''))
    ids = set(re.findall(r'[?&]rid=([A-Za-z0-9_-]{1,256})(?=[&\s"\'<>#]|$)', content))
    return next(iter(ids)) if len(ids) == 1 else None


@app.post('/message/<int:index>/report')
def report_message(index):
    if not 0 <= index < len(messages):
        return jsonify(error='Message not found'), 404
    msg = messages[index]
    token = msg.get('report_token', '')
    if not token or not secrets.compare_digest(request.headers.get('X-Report-Token', ''), token):
        return jsonify(error='Reload the message and try again.'), 403
    rid = message_rid(msg)
    if not rid:
        return jsonify(error='This message has no unique simulation tracking ID.'), 422
    if msg.get('reported'):
        return jsonify(status='already_reported')
    try:
        report_to_gophish(rid)
    except (httpx.HTTPError, ValueError):
        return jsonify(error='Report could not be recorded in Gophish. Check the server and try again.'), 502
    msg['reported'] = True
    return jsonify(status='reported')


@app.get('/mailbox.js')
def mailbox_script():
    return Response("""'use strict';
const messageFrame = document.getElementById('messageFrame');
function fitFrame() {
 try { const d = messageFrame.contentDocument; if (d && d.body) messageFrame.style.height = Math.max(400, d.documentElement.scrollHeight + 4) + 'px'; } catch (e) {}
}
if (messageFrame) { messageFrame.addEventListener('load', fitFrame); window.addEventListener('resize', fitFrame); fitFrame(); }
const reportButton = document.getElementById('reportPhishing');
reportButton?.addEventListener('click', async () => {
 const status = document.getElementById('reportStatus');
 reportButton.disabled = true; status.textContent = 'Recording report…';
 try {
  const response = await fetch(reportButton.dataset.endpoint, {method:'POST', headers:{'X-Report-Token':reportButton.dataset.token}});
  const result = await response.json();
  if (!response.ok) throw new Error(result.error);
  status.textContent = 'Thank you. Your report has been recorded in Gophish.';
  reportButton.textContent = 'Phishing reported';
 } catch (error) { status.textContent = error.message || 'Unable to report. Please try again.'; reportButton.disabled = false; }
});""", mimetype='application/javascript')


@app.route("/message/<int:index>/body")
def message_body(index):
    if index < 0 or index >= len(messages):
        return "Message not found", 404
    msg = messages[index]
    content = msg["html"].strip() or msg["text"].strip()
    return fix_gophish_links(content) if looks_like_html(content) else "<pre>" + escape(content) + "</pre>"

@app.route("/message/<int:index>")
def view_message(index):

    # --------------------------------------------------------
    # VALIDATE INDEX
    # --------------------------------------------------------

    if index < 0 or index >= len(messages):

        return ("Message not found", 404)

    msg = messages[index]
    msg.setdefault('report_token', secrets.token_urlsafe(24))

    html_content = msg["html"].strip()

    text_content = msg["text"].strip()

    # --------------------------------------------------------
    # RENDER HTML EMAIL
    # --------------------------------------------------------

    if html_content:

        body = fix_gophish_links(html_content)

    # --------------------------------------------------------
    # HTML ACCIDENTALLY STORED AS TEXT
    # --------------------------------------------------------

    elif looks_like_html(text_content):

        body = fix_gophish_links(text_content)

    # --------------------------------------------------------
    # NORMAL TEXT EMAIL
    # --------------------------------------------------------

    else:

        body = f"""
        <pre class="plain-text">
{escape(text_content)}
        </pre>
        """

    # --------------------------------------------------------
    # EMAIL PAGE
    # --------------------------------------------------------

    return f"""
    <!DOCTYPE html>

    <html lang="en">

    <head>

        <meta charset="UTF-8">

        <meta
            name="viewport"
            content="width=device-width,
            initial-scale=1.0"
        >

        <title>
            {escape(msg["subject"])}
        </title>


        <style>{MAIL_CSS}</style>

    </head>


    <body>
        {TOPBAR}
        <script src="/mailbox.js" defer></script>
        <div class="toolbar">

            <a href="/">← Back to Inbox</a>
            <button id="reportPhishing" type="button" data-endpoint="/message/{index}/report" data-token="{escape(msg['report_token'])}" {'disabled' if msg.get('reported') else ''}>{'Phishing reported' if msg.get('reported') else 'Report Phishing'}</button>
            <p id="reportStatus" role="status" aria-live="polite">{'Your report has been recorded in Gophish.' if msg.get('reported') else ''}</p>

        </div>



        <div class="email-info">


            <strong>
                From:
            </strong>

            {escape(msg["from"])}

            <br>


            <strong>
                To:
            </strong>

            {escape(msg["to"])}

            <br>


            <strong>
                Subject:
            </strong>

            {escape(msg["subject"])}


            <br>


            


        </div>


        <div class="message-container">

            <iframe id="messageFrame" title="Simulation email" sandbox="allow-same-origin allow-popups allow-popups-to-escape-sandbox allow-top-navigation-by-user-activation" src="/message/{index}/body" style="width:100%;height:900px;border:0;display:block"></iframe>

        </div>


    </body>

    </html>
    """


# ============================================================
# START WEB SERVER
# ============================================================


def start_web_server():

    app.run(host=WEB_HOST, port=WEB_PORT, debug=False, use_reloader=False)


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    # --------------------------------------------------------
    # START WEB INBOX
    # --------------------------------------------------------

    web_thread = threading.Thread(target=start_web_server, daemon=True)

    web_thread.start()

    # --------------------------------------------------------
    # START SMTP SERVER
    # --------------------------------------------------------

    controller = Controller(MailSandbox(), hostname=SMTP_HOST, port=SMTP_PORT)

    controller.start()

    # --------------------------------------------------------
    # STARTUP INFORMATION
    # --------------------------------------------------------

    print("\n" + "=" * 65)

    print("CONTROLLED SECURITY AWARENESS TEST MAILBOX")

    print("=" * 65)

    print(f"SMTP Listener : " f"{SMTP_HOST}:{SMTP_PORT}")

    print(f"Local Inbox   : http://{WEB_HOST}:{WEB_PORT}")

    print("Inbox access  : loopback only")

    print(f"Gophish       : " f"{GOPHISH_BASE_URL}")

    print("=" * 65)

    print("Waiting for authorized simulation emails...")

    print("Press CTRL+C to stop.")

    print("=" * 65 + "\n")

    # --------------------------------------------------------
    # KEEP RUNNING
    # --------------------------------------------------------

    try:

        threading.Event().wait()

    except KeyboardInterrupt:

        print("\nStopping controlled test mailbox...")

    finally:

        controller.stop()
