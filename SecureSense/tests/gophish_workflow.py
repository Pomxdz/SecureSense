import atexit, datetime, ipaddress, json, os, secrets, sqlite3, subprocess, sys, time, ssl
from pathlib import Path
import httpx
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from playwright.sync_api import sync_playwright
import argparse, shutil, tempfile

parser = argparse.ArgumentParser(
    description="Isolated local Gophish end-to-end check; no external email"
)
parser.add_argument("gophish_directory", type=Path)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
ADMIN_PORT = 13334
PHISH_PORT = 18129
APP_PORT = 18123
MAILBOX_WEB_PORT = 18025
PROXY_PORT = 11027
MAILBOX_SMTP_PORT = 11026
scratch = Path(tempfile.mkdtemp(prefix="securesense-gophish-"))
lab = scratch / "engine"
shutil.copytree(
    args.gophish_directory.resolve(),
    lab,
    ignore=shutil.ignore_patterns(
        "*.db", "*.db-*", "*.log", "*.key", "config.before_securesense.json"
    ),
)
engine = lab / ("gophish.exe" if os.name == "nt" else "gophish")
if not engine.exists():
    raise RuntimeError("Official extracted Gophish executable missing")
if os.name != "nt":
    engine.chmod(0o700)

key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
now = datetime.datetime.now(datetime.timezone.utc)
cert = (
    x509.CertificateBuilder()
    .subject_name(name)
    .issuer_name(name)
    .public_key(key.public_key())
    .serial_number(x509.random_serial_number())
    .not_valid_before(now - datetime.timedelta(minutes=1))
    .not_valid_after(now + datetime.timedelta(days=30))
    .add_extension(
        x509.SubjectAlternativeName(
            [
                x509.DNSName("localhost"),
                x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
            ]
        ),
        False,
    )
    .add_extension(x509.BasicConstraints(ca=True, path_length=None), True)
    .sign(key, hashes.SHA256())
)
certpath = scratch / "admin.crt"
keypath = scratch / "admin.key"
certpath.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
keypath.write_bytes(
    key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    )
)
config = json.loads((lab / "config.json").read_text())
config["admin_server"].update(
    listen_url=f"127.0.0.1:{ADMIN_PORT}", cert_path=str(certpath), key_path=str(keypath)
)
config["phish_server"]["listen_url"] = f"127.0.0.1:{PHISH_PORT}"
config["db_path"] = str(scratch / "gophish.db")
(lab / "config.json").write_text(json.dumps(config))
processes = []


def spawn(args, cwd=root, env=None):
    p = subprocess.Popen(
        args, cwd=cwd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    processes.append(p)
    return p


def cleanup():
    for process in processes:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
    shutil.rmtree(scratch, ignore_errors=True)


atexit.register(cleanup)
env = dict(os.environ)
env["GOPHISH_INITIAL_ADMIN_PASSWORD"] = secrets.token_urlsafe(18)
spawn([str(engine)], cwd=lab, env=env)
g = httpx.Client(
    base_url=f"https://127.0.0.1:{ADMIN_PORT}",
    verify=ssl.create_default_context(cafile=str(certpath)),
    trust_env=False,
    timeout=10,
)
for _ in range(100):
    try:
        with sqlite3.connect(scratch / "gophish.db") as c:
            api = c.execute("SELECT api_key FROM users LIMIT 1").fetchone()[0]
        if api and g.get("/login").status_code == 200:
            break
    except Exception:
        time.sleep(0.1)
else:
    raise RuntimeError("Gophish did not start")
g.headers["Authorization"] = "Bearer " + api
env = dict(
    os.environ,
    GROQ_API_KEY="",
    GROQ_MODEL="",
    SECURESENSE_DB=str(scratch / "securesense.db"),
    SECURESENSE_CREDENTIALS_PATH=str(scratch / "credentials.txt"),
    GOPHISH_API_KEY=api,
    GOPHISH_ADMIN_URL=f"https://127.0.0.1:{ADMIN_PORT}",
    GOPHISH_CA_BUNDLE=str(certpath),
    GOPHISH_PHISHING_URL=f"http://127.0.0.1:{PHISH_PORT}",
    PROXY_PORT=str(PROXY_PORT),
    RELAY_PORT=str(MAILBOX_SMTP_PORT),
    MAILBOX_SMTP_PORT=str(MAILBOX_SMTP_PORT),
    MAILBOX_WEB_PORT=str(MAILBOX_WEB_PORT),
)
spawn([sys.executable, str(root / "run.py"), "--practice", "--port", str(APP_PORT)], env=env)
spawn([sys.executable, str(root / "Member1/mail_sandbox.py")], env=env)
spawn([sys.executable, str(root / "Member1/smtp_proxy.py")], env=env)
s = httpx.Client(base_url=f"http://127.0.0.1:{APP_PORT}", trust_env=False, timeout=15)
for _ in range(100):
    try:
        if (
            s.get("/health").status_code == 200
            and httpx.get(f"http://127.0.0.1:{MAILBOX_WEB_PORT}", trust_env=False).status_code == 200
        ):
            break
    except Exception:
        time.sleep(0.1)
creds = dict(
    line.split(" : ", 1)
    for line in (scratch / "credentials.txt").read_text().splitlines()
)
s.headers["Authorization"] = (
    "Bearer "
    + s.post(
        "/auth/login",
        json={"email": "admin@example.test", "password": creds["admin@example.test"]},
    ).json()["token"]
)


def gp(path, data):
    r = g.post(path, json=data)
    assert r.is_success, (path, r.status_code, r.text[:200])
    return r.json()


profile = gp(
    "/api/smtp/",
    {
        "name": "Local fixture",
        "interface_type": "SMTP",
        "host": f"127.0.0.1:{PROXY_PORT}",
        "from_address": "ShieldPay <support@shieldpay.example.test>",
        "username": "",
        "password": "",
        "ignore_cert_errors": False,
    },
)
checks = []
for number, (scenario, category, expected_module, trigger) in enumerate(
    [
        (
            "account",
            "Credential Harvesting",
            "Account and Form Verification",
            "test_form_submission",
        ),
        (
            "invoice",
            "Financial Fraud",
            "Invoice and Payroll Verification",
            "test_form_submission",
        ),
        ("click", "Credential Harvesting", "Account and Form Verification", "test_form_submission"),
    ],
    1,
):
    template = gp(
        "/api/templates/",
        {
            "name": "Local " + scenario + " test",
            "subject": "Authorized account review exercise",
            "html": (
                root
                / (
                    "Member1/shieldpay_invoice_email.html"
                    if scenario == "invoice"
                    else "Member1/shieldpay_gophish_email.html"
                )
            ).read_text(),
            "text": "Review {{.URL}}",
            "attachments": [],
        },
    )
    page = gp(
        "/api/pages/",
        {
            "name": "Local " + scenario + " landing",
            "html": (
                root / "Member1/shieldpay_landing_page.html"
            ).read_text(),
            "capture_credentials": True,
            "capture_passwords": False,
            "redirect_url": "",
        },
    )
    group = gp(
        "/api/groups/",
        {
            "name": "Local " + scenario + " Amali",
            "targets": [
                {
                    "first_name": "Amali",
                    "last_name": "Perera",
                    "email": "amali.perera@example.test",
                    "position": "Finance",
                }
            ],
        },
    )
    campaign = gp(
        "/api/campaigns/",
        {
            "name": "Actual local " + scenario + " engine test",
            "template": {"name": template["name"]},
            "page": {"name": page["name"]},
            "smtp": {"name": profile["name"]},
            "url": f"http://127.0.0.1:{PHISH_PORT}",
            "groups": [{"name": group["name"]}],
            "launch_date": now.isoformat(),
        },
    )
    cid = str(campaign["id"])
    rid = campaign["results"][0]["id"]
    meta = {
        "campaign": {
            "id": cid,
            "name": campaign["name"],
            "category": category,
            "objective": (
                "link_interaction" if trigger == "clicked" else "test_form_submission"
            ),
            "source": "live",
            "launched_at": now.isoformat(),
        },
        "departments": {"amali.perera@example.test": "Finance"},
    }
    r = s.post("/admin/gophish/sync", json=meta)
    assert r.is_success, r.text
    r = s.post(
        "/admin/learning/bridge",
        json={
            "campaign_id": cid,
            "public_base": f"http://127.0.0.1:{APP_PORT}",
            "trigger": trigger,
        },
    )
    assert r.is_success, r.text
    html = r.json()["landing_html"]
    page.update(html=html)
    r = g.put("/api/pages/" + str(page["id"]), json=page)
    assert r.is_success, r.text
    link = f"http://127.0.0.1:{PHISH_PORT}/?rid=" + rid
    assert "/learn/entry" in httpx.get(link, trust_env=False).text
    scenario_checks = [
        "Real Gophish API connected with certificate validation",
        "Native campaign and recipient imported",
        "Campaign-specific learning bridge generated",
    ]
    with sync_playwright() as p:
        b = p.chromium.launch(
            executable_path=os.getenv("CHROMIUM_EXECUTABLE") or None,
            args=["--no-sandbox"],
        )
        page = b.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/134.0.0.0 Safari/537.36"
        )
        page.goto(link)
        if trigger == "test_form_submission":
            page.fill("input[name=email]", "amali.perera@example.test")
            page.fill("input[type=password]", "Training-only-password")
            page.on("dialog", lambda dialog: dialog.accept())
            with page.expect_popup() as login_opened:
                page.click("button[type=submit]")
            page = login_opened.value
        page.wait_for_url("**/app/login.html#**")
        scenario_checks.append(
            "Native form submission redirected to authenticated learning handoff"
        )
        # Let the engine persist native events, then synchronize the actual timeline.
        r = s.post("/admin/gophish/sync", json=meta)
        assert r.is_success, r.text
        print("Imported native interactions:", r.json(), flush=True)
        page.fill("#loginEmail", "amali.perera@example.test")
        page.fill("#loginPassword", creds["amali.perera@example.test"])
        page.click("button[type=submit]")
        page.wait_for_selector("#quizDialog[open]", timeout=15000)
        assert expected_module in page.locator("#quizTitle").inner_text()
        scenario_checks.append(
            "Correct participant authenticated and correct lesson opened automatically"
        )
        sys.path.insert(0, str(root / "Member2"))
        from learning_content import CONTENT

        fields = page.locator("#quizForm fieldset")
        for i, q in enumerate(CONTENT[category][1]):
            fields.nth(i).locator("input").nth(q[2]).check()
        page.click("#quizForm button[type=submit]")
        page.wait_for_selector("#quizResult h3")
        assert "100%" in page.locator("#quizResult h3").inner_text()
        scenario_checks.append("Category-specific quiz server graded and passed")
        b.close()
    r = s.get("/metrics?source=live")
    assert r.is_success, r.text
    assert (
        r.json()["submission_rate"]["n"] == number
        and r.json()["training"]["passed"] == number
    )
    scenario_checks.append(
        "Actual imported interaction and verified pass visible in live dashboard"
    )
    checks.extend([scenario + ": " + x for x in scenario_checks])
(root / "evidence").mkdir(exist_ok=True)
(root / "evidence/gophish_results.json").write_text(
    json.dumps(
        {
            "checks": checks,
            "status": "passed",
            "engine": "Gophish v0.12.1",
            "scope": "Loopback local SMTP; fictional recipients; no external mail",
        },
        indent=2,
    )
)
print(json.dumps({"passed": len(checks), "status": "passed"}))
