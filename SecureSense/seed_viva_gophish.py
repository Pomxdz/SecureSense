"""Create a localhost-only Gophish viva showcase for every SecureSense category.

The script is intentionally constrained to loopback services and fictional .test users.
It creates five colorful email templates, safe landing pages, one local recipient group
per category, a local SMTP profile, and one campaign per category. Campaigns are then
synchronized into SecureSense and receive a category-specific learning bridge when the
local administrator credential is available.

Run after start_practice.bat has started Gophish and the SecureSense stack.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import ssl
import sys
import time
import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

GOPHISH_ADMIN_URL = os.getenv("GOPHISH_ADMIN_URL", "https://127.0.0.1:3333").rstrip("/")
GOPHISH_API_KEY = os.getenv("GOPHISH_API_KEY", "").strip()
GOPHISH_CA_BUNDLE = os.getenv("GOPHISH_CA_BUNDLE", "").strip()
GOPHISH_PHISHING_URL = os.getenv("GOPHISH_PHISHING_URL", "http://127.0.0.1/").rstrip("/")
SECURESENSE_PORT = int(os.getenv("SECURESENSE_PORT", "8000"))
SECURESENSE_URL = f"http://127.0.0.1:{SECURESENSE_PORT}"
PROXY_PORT = int(os.getenv("PROXY_PORT", "1027"))
MAILBOX_WEB_PORT = int(os.getenv("MAILBOX_WEB_PORT", "8025"))
TEMPLATE_DIR = ROOT / "Member1" / "viva_templates"
LANDING_TEMPLATE = ROOT / "Member1" / "shieldpay_landing_page.html"
CREDENTIALS_PATH = Path(os.getenv("SECURESENSE_CREDENTIALS_PATH", str(ROOT / "local_credentials.txt")))

SCENARIOS = [
    {
        "slug": "credential-harvesting",
        "category": "Credential Harvesting",
        "campaign": "VIVA 01 - Credential Harvesting",
        "template": "VIVA - SecureHub Account Protection",
        "subject": "Action requested: review unusual account activity",
        "template_file": "credential_harvesting.html",
        "landing": "VIVA - Credential Harvesting Learning Bridge",
        "theme": "Account security",
        "identity": "SecureHub account protection team",
        "persuasion": ["urgency", "authority"],
        "difficulty": "moderate",
        "trigger": "test_form_submission",
        "objective": "test_form_submission",
        "target": ("Amali", "Perera", "amali.perera@example.test", "Finance"),
        "warning_signs": ["Unexpected sign-in review", "Unfamiliar destination", "Urgent access warning"],
    },
    {
        "slug": "financial-fraud",
        "category": "Financial Fraud",
        "campaign": "VIVA 02 - Financial Fraud",
        "template": "VIVA - ApexPay Invoice Verification",
        "subject": "Supplier invoice update awaiting verification",
        "template_file": "financial_fraud.html",
        "landing": "VIVA - Financial Fraud Learning Bridge",
        "theme": "Supplier invoice change",
        "identity": "ApexPay supplier payments team",
        "persuasion": ["authority", "familiarity", "urgency"],
        "difficulty": "hard",
        "trigger": "test_form_submission",
        "objective": "test_form_submission",
        "target": ("Kasun", "Fernando", "kasun.fernando@example.test", "Finance"),
        "warning_signs": ["Changed payment details", "Accelerated deadline", "Request outside normal approval flow"],
    },
    {
        "slug": "social-engineering",
        "category": "Social Engineering",
        "campaign": "VIVA 03 - Social Engineering",
        "template": "VIVA - PeoplePlus Recognition Reward",
        "subject": "You were selected for an employee recognition reward",
        "template_file": "social_engineering.html",
        "landing": "VIVA - Social Engineering Learning Bridge",
        "theme": "Employee recognition reward",
        "identity": "PeoplePlus recognition team",
        "persuasion": ["reward", "familiarity"],
        "difficulty": "easy",
        "trigger": "test_form_submission",
        "objective": "test_form_submission",
        "target": ("Nuwan", "Wickramasinghe", "nuwan.wickramasinghe@example.test", "IT"),
        "warning_signs": ["Unexpected reward", "Short expiry window", "Identity not independently verified"],
    },
    {
        "slug": "urgent-extortion",
        "category": "Urgent Extortion",
        "campaign": "VIVA 04 - Urgent Extortion",
        "template": "VIVA - CoreGuard Incident Notice",
        "subject": "Urgent: security incident notice requires review",
        "template_file": "urgent_extortion.html",
        "landing": "VIVA - Urgent Extortion Learning Bridge",
        "theme": "Threatening security notice",
        "identity": "CoreGuard incident desk",
        "persuasion": ["fear", "urgency"],
        "difficulty": "hard",
        "trigger": "test_form_submission",
        "objective": "test_form_submission",
        "target": ("Amaya", "Herath", "amaya.herath@example.test", "Operations"),
        "warning_signs": ["Threatening language", "Artificial deadline", "Pressure to bypass incident procedure"],
    },
    {
        "slug": "malware-delivery",
        "category": "Malware Delivery",
        "campaign": "VIVA 05 - Malware Delivery",
        "template": "VIVA - WorkSuite Update Notice",
        "subject": "WorkSuite desktop update is ready",
        "template_file": "malware_delivery.html",
        "landing": "VIVA - Malware Delivery Learning Bridge",
        "theme": "Software update notice",
        "identity": "WorkSuite update center",
        "persuasion": ["authority", "familiarity"],
        "difficulty": "moderate",
        "trigger": "test_form_submission",
        "objective": "test_form_submission",
        "target": ("Dilini", "Jayasinghe", "dilini.jayasinghe@example.test", "IT"),
        "warning_signs": ["Unexpected update message", "Unverified software link", "Request outside approved update channel"],
    },
]


def loopback_only(url: str, label: str, require_https: bool = False) -> None:
    parsed = urlsplit(url)
    if require_https and parsed.scheme != "https":
        raise SystemExit(f"{label} must use HTTPS")
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise SystemExit(f"{label} must be a valid HTTP/HTTPS URL")
    host = parsed.hostname.lower()
    if host == "localhost":
        return
    try:
        if ipaddress.ip_address(host).is_loopback:
            return
    except ValueError:
        pass
    raise SystemExit(f"{label} must stay on localhost/loopback for this viva showcase")


def ssl_verify():
    if not GOPHISH_CA_BUNDLE:
        return True
    path = Path(GOPHISH_CA_BUNDLE).expanduser()
    if not path.is_file():
        raise SystemExit(f"GOPHISH_CA_BUNDLE does not exist: {path}")
    return ssl.create_default_context(cafile=str(path))


def credentials_from_local_file() -> tuple[str, str] | None:
    email = os.getenv("SECURESENSE_SYNC_EMAIL", "").strip()
    password = os.getenv("SECURESENSE_SYNC_PASSWORD", "")
    if email and password:
        return email, password
    if not CREDENTIALS_PATH.is_file():
        return None
    found = None
    for line in CREDENTIALS_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
        if " : " not in line:
            continue
        e, pw = line.split(" : ", 1)
        if e.strip().lower() == "admin@example.test":
            found = (e.strip(), pw.strip())
    return found


class Gophish:
    def __init__(self):
        if not GOPHISH_API_KEY:
            raise SystemExit(
                "GOPHISH_API_KEY is empty. Sign in to local Gophish, copy the API key into .env, then rerun."
            )
        self.client = httpx.Client(
            base_url=GOPHISH_ADMIN_URL,
            headers={"Authorization": "Bearer " + GOPHISH_API_KEY},
            verify=ssl_verify(),
            timeout=20,
            trust_env=False,
        )

    def close(self):
        self.client.close()

    def request(self, method: str, path: str, **kwargs):
        response = self.client.request(method, path, **kwargs)
        if not response.is_success:
            detail = response.text.replace("\n", " ")[:350]
            raise RuntimeError(f"Gophish {method} {path} failed ({response.status_code}): {detail}")
        if response.content:
            return response.json()
        return None

    def get(self, path: str):
        return self.request("GET", path)

    def post(self, path: str, data: dict):
        return self.request("POST", path, json=data)

    def put(self, path: str, data: dict):
        return self.request("PUT", path, json=data)

    def by_name(self, path: str, name: str):
        rows = self.get(path)
        if isinstance(rows, dict):
            rows = rows.get("data", [])
        for row in rows or []:
            if row.get("name") == name:
                return row
        return None


def safe_landing_html(category: str) -> str:
    slug = next(item["slug"] for item in SCENARIOS if item["category"] == category)
    return (ROOT / "Member1" / "viva_landings" / (slug + ".html")).read_text(encoding="utf-8")


def ensure_resources(g: Gophish, dry_run: bool = False):
    profile_name = "SecureSense Viva Local SMTP"
    profile = g.by_name("/api/smtp/", profile_name)
    if not profile and not dry_run:
        profile = g.post(
            "/api/smtp/",
            {
                "name": profile_name,
                "interface_type": "SMTP",
                "host": f"127.0.0.1:{PROXY_PORT}",
                "from_address": "SecureSense <notifications@securesense.example.test>",
                "username": "",
                "password": "",
                "ignore_cert_errors": False,
            },
        )
    elif not profile:
        profile = {"name": profile_name, "id": "dry-run"}

    if profile and not dry_run:
        profile.update(host=f"127.0.0.1:{PROXY_PORT}", username="", password="")
        profile = g.put(f"/api/smtp/{profile['id']}", profile)
    prepared = []
    for scenario in SCENARIOS:
        brand = scenario['identity'].split()[0]
        brand_profile_name = f"{brand} Local SMTP"
        brand_profile = g.by_name('/api/smtp/', brand_profile_name)
        brand_payload = {'name': brand_profile_name, 'interface_type': 'SMTP', 'host': f'127.0.0.1:{PROXY_PORT}', 'from_address': f'{brand} <notifications@{brand.lower()}.example.test>', 'username': '', 'password': '', 'ignore_cert_errors': False}
        if not dry_run:
            if brand_profile:
                brand_profile.update(brand_payload)
                profile = g.put(f"/api/smtp/{brand_profile['id']}", brand_profile)
            else:
                profile = g.post('/api/smtp/', brand_payload)
        else:
            profile = brand_payload
        template = g.by_name("/api/templates/", scenario["template"])
        if not template and not dry_run:
            template = g.post(
                "/api/templates/",
                {
                    "name": scenario["template"],
                    "subject": scenario["subject"],
                    "html": (TEMPLATE_DIR / scenario["template_file"]).read_text(encoding="utf-8").replace("http://127.0.0.1:8000", SECURESENSE_URL),
                    "text": f"Authorized SecureSense simulation. Review the fictional message at {{{{.URL}}}}",
                    "attachments": [],
                },
            )
        elif not template:
            template = {"name": scenario["template"], "id": "dry-run"}

        if template and not dry_run:
            template.update(
                subject=scenario["subject"],
                html=(TEMPLATE_DIR / scenario["template_file"]).read_text(encoding="utf-8").replace("http://127.0.0.1:8000", SECURESENSE_URL),
                text="Authorized SecureSense local simulation. Open {{{{.URL}}}}".replace("{{{{", "{{").replace("}}}}", "}}"),
            )
            template = g.put(f"/api/templates/{template['id']}", template)

        page = g.by_name("/api/pages/", scenario["landing"])
        if not page and not dry_run:
            page = g.post(
                "/api/pages/",
                {
                    "name": scenario["landing"],
                    "html": safe_landing_html(scenario["category"]),
                    "capture_credentials": scenario["trigger"] == "test_form_submission",
                    "capture_passwords": False,
                    "redirect_url": "",
                },
            )
        elif not page:
            page = {"name": scenario["landing"], "id": "dry-run"}

        first, last, target_email, department = scenario["target"]
        group_name = f"VIVA - {scenario['category']} - {first} {last}"
        group = g.by_name("/api/groups/", group_name)
        if not group and not dry_run:
            group = g.post(
                "/api/groups/",
                {
                    "name": group_name,
                    "targets": [
                        {
                            "first_name": first,
                            "last_name": last,
                            "email": target_email,
                            "position": department,
                        }
                    ],
                },
            )
        elif not group:
            group = {"name": group_name, "id": "dry-run"}

        prepared.append((scenario, profile, template, page, group))
    return prepared


def create_campaigns(g: Gophish, prepared, dry_run: bool = False):
    campaigns = []
    now = datetime.now(timezone.utc).isoformat()
    for scenario, profile, template, page, group in prepared:
        campaign = g.by_name("/api/campaigns/", scenario["campaign"])
        created = False
        if not campaign and not dry_run:
            campaign = g.post(
                "/api/campaigns/",
                {
                    "name": scenario["campaign"],
                    "template": {"name": template["name"]},
                    "page": {"name": page["name"]},
                    "smtp": {"name": profile["name"]},
                    "url": GOPHISH_PHISHING_URL,
                    "groups": [{"name": group["name"]}],
                    "launch_date": now,
                },
            )
            created = True
        elif not campaign:
            campaign = {"id": "dry-run", "name": scenario["campaign"], "launch_date": now}
        campaigns.append((scenario, page, campaign, created))
        print(f"[{'create' if created else 'reuse'}] {scenario['category']}: {scenario['campaign']}")
    return campaigns


def securesense_client() -> httpx.Client | None:
    creds = credentials_from_local_file()
    if not creds:
        print("[warn] SecureSense admin credential not found; Gophish campaigns were still created.")
        return None
    c = httpx.Client(base_url=SECURESENSE_URL, timeout=20, trust_env=False)
    response = c.post("/auth/login", json={"email": creds[0], "password": creds[1]})
    if not response.is_success:
        c.close()
        print("[warn] Could not authenticate to SecureSense; Gophish campaigns were still created.")
        return None
    c.headers["Authorization"] = "Bearer " + response.json()["token"]
    return c


def sync_and_bridge(g: Gophish, campaigns, dry_run: bool = False):
    if dry_run:
        return
    s = securesense_client()
    if not s:
        return
    profiles = []
    try:
        # Give the local SMTP chain a moment to persist native Email Sent events.
        time.sleep(1.5)
        for scenario, page, campaign, _ in campaigns:
            campaign_id = str(campaign["id"])
            launched_at = campaign.get("launch_date") or datetime.now(timezone.utc).isoformat()
            _, _, target_email, department = scenario["target"]
            metadata = {
                "campaign": {
                    "id": campaign_id,
                    "name": campaign["name"],
                    "category": scenario["category"],
                    "theme": scenario["theme"],
                    "objective": scenario["objective"],
                    "persuasion": scenario["persuasion"],
                    "identity": scenario["identity"],
                    "warning_signs": scenario["warning_signs"],
                    "difficulty": scenario["difficulty"],
                    "audience_relevance": "Fictional localhost viva showcase",
                    "source": "live",
                    "launched_at": launched_at,
                },
                "departments": {target_email: department},
            }
            profiles.append(metadata)
            response = s.post("/admin/gophish/sync", json=metadata)
            if not response.is_success:
                raise RuntimeError(
                    f"SecureSense sync failed for {scenario['category']} ({response.status_code}): {response.text[:300]}"
                )
            bridge = s.post(
                "/admin/learning/bridge",
                json={
                    "campaign_id": campaign_id,
                    "public_base": SECURESENSE_URL,
                    "trigger": scenario["trigger"],
                },
            )
            if not bridge.is_success:
                raise RuntimeError(
                    f"Learning bridge failed for {scenario['category']} ({bridge.status_code}): {bridge.text[:300]}"
                )
            # Re-fetch the page so the PUT includes all Gophish-managed fields.
            current_page = g.get(f"/api/pages/{page['id']}")
            current_page["html"] = bridge.json()["landing_html"]
            current_page["capture_credentials"] = scenario["trigger"] == "test_form_submission"
            current_page["capture_passwords"] = False
            current_page["redirect_url"] = ""
            g.put(f"/api/pages/{page['id']}", current_page)
            print(f"[sync] {scenario['category']} -> SecureSense + targeted learning bridge")
        (ROOT / "viva_profiles.json").write_text(json.dumps(profiles, indent=2))
    finally:
        s.close()


def print_summary(campaigns):
    print("\nSecureSense viva showcase is ready")
    print("=" * 72)
    for scenario, _, campaign, created in campaigns:
        first, last, email, department = scenario["target"]
        print(
            f"{scenario['category']:<22} campaign #{campaign['id']!s:<4}  {first} {last} <{email}>  [{department}]"
        )
    print("=" * 72)
    print(f"Local inbox:      http://127.0.0.1:{MAILBOX_WEB_PORT}")
    print(f"Gophish admin:    {GOPHISH_ADMIN_URL}")
    print(f"SecureSense:      {SECURESENSE_URL}/app/login.html")
    print("All recipients use the fictional example.test domain; SMTP remains on localhost.")
    print("Rerun this script before the viva to refresh the 7-day learning handoff tickets.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed five localhost-only Gophish viva campaigns")
    parser.add_argument("--dry-run", action="store_true", help="Validate configuration without creating resources")
    parser.add_argument("--open", action="store_true", help="Open the local inbox and Gophish admin after seeding")
    parser.add_argument("--fresh", action="store_true", help="Create a fresh five-campaign session and send its local emails")
    args = parser.parse_args()
    session_file = ROOT / "viva_session.json"
    if not args.dry_run:
        if args.fresh or not session_file.exists():
            session = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
            session_file.write_text(json.dumps({"session": session}))
        else:
            session = json.loads(session_file.read_text())["session"]
        for scenario in SCENARIOS:
            scenario["campaign"] += " - " + session
            scenario["landing"] += " - " + session


    loopback_only(GOPHISH_ADMIN_URL, "GOPHISH_ADMIN_URL", require_https=True)
    loopback_only(GOPHISH_PHISHING_URL, "GOPHISH_PHISHING_URL")
    if not TEMPLATE_DIR.is_dir() or not LANDING_TEMPLATE.is_file():
        raise SystemExit("Viva templates are missing from the project package")
    if args.dry_run and not GOPHISH_API_KEY:
        print("Configuration is localhost-only. GOPHISH_API_KEY is still required for an API connectivity dry-run.")

    g = Gophish()
    try:
        # Connectivity + credential validation.
        g.get("/api/campaigns/")
        prepared = ensure_resources(g, args.dry_run)
        campaigns = create_campaigns(g, prepared, args.dry_run)
        sync_and_bridge(g, campaigns, args.dry_run)
        print_summary(campaigns)
    finally:
        g.close()

    if args.open and not args.dry_run:
        webbrowser.open(f"http://127.0.0.1:{MAILBOX_WEB_PORT}")
        webbrowser.open(GOPHISH_ADMIN_URL)
        webbrowser.open(f"{SECURESENSE_URL}/app/login.html")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (httpx.HTTPError, RuntimeError) as exc:
        print(f"[error] {exc}", file=sys.stderr)
        print(
            "Check that start_practice.bat is running, GOPHISH_API_KEY and GOPHISH_CA_BUNDLE are correct, "
            "and the local SMTP proxy is available on 127.0.0.1:%d." % PROXY_PORT,
            file=sys.stderr,
        )
        raise SystemExit(1)
