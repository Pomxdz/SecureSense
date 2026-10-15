"""Optional local polling adapter. Campaign profiles live in a JSON list.
python sync_gophish.py examples/gophish_profiles.json --once
Supply SECURESENSE_SYNC_EMAIL and SECURESENSE_SYNC_PASSWORD in environment or enter at prompt.
The script never sends email or prints credentials. Native timeline events are deduplicated.
"""

import argparse, getpass, json, os, time
from pathlib import Path
import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")


def run():
    p = argparse.ArgumentParser()
    p.add_argument("profiles", type=Path)
    p.add_argument("--once", action="store_true")
    p.add_argument("--interval", type=int, default=30)
    p.add_argument("--url", default="http://127.0.0.1:8000")
    a = p.parse_args()
    if a.interval < 10:
        p.error("Interval must be at least 10 seconds")
    profiles = json.loads(a.profiles.read_text())
    if not isinstance(profiles, list):
        p.error("Profiles file must contain a JSON list of sync requests")
    e = os.getenv("SECURESENSE_SYNC_EMAIL") or input("SecureSense admin email: ")
    password = os.getenv("SECURESENSE_SYNC_PASSWORD") or getpass.getpass(
        "SecureSense admin password: "
    )
    with httpx.Client(base_url=a.url, timeout=30, trust_env=False) as c:

        def authenticate():
            r = c.post("/auth/login", json={"email": e, "password": password})
            r.raise_for_status()
            c.headers["Authorization"] = "Bearer " + r.json()["token"]

        authenticate()
        while True:
            for profile in profiles:
                r = c.post("/admin/gophish/sync", json=profile)
                if r.status_code == 401:
                    authenticate()
                    r = c.post("/admin/gophish/sync", json=profile)
                if r.is_success:
                    print(json.dumps(r.json()))
                else:
                    print(
                        "Sync failed:",
                        r.status_code,
                        "Check integration setup and campaign profile.",
                    )
            if a.once:
                return
            time.sleep(a.interval)


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        print("Polling stopped.")
