"""Single-process app launcher. Default binds only to loopback."""

import argparse, os, secrets, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "Member2"))
from dotenv import load_dotenv

load_dotenv(ROOT / ".env")
import main


def bootstrap(practice=False):
    output = []
    with main.db() as c:
        if not c.execute("SELECT 1 FROM users WHERE role='admin'").fetchone():
            e = "admin@example.test"
            pw = secrets.token_urlsafe(18)
            c.execute(
                "INSERT INTO users VALUES(?,?,?,?,?)",
                (
                    e,
                    "InfoSec Administrator",
                    "InfoSec",
                    "admin",
                    main.password_hash(pw),
                ),
            )
            output.append((e, pw))
    if practice:
        from practice import seed

        created = seed()
        if created:
            output.extend(created.items())
    if output:
        p = Path(
            os.getenv("SECURESENSE_CREDENTIALS_PATH", str(ROOT / "local_credentials.txt"))
        )
        with p.open("a", encoding="utf-8") as f:
            for e, pw in output:
                f.write(f"{e} : {pw}\n")
        try:
            p.chmod(0o600)
        except OSError:
            pass
        print(
            "New local accounts saved in local_credentials.txt. Use admin@example.test for dashboard or dilini.jayasinghe@example.test for training."
        )
    else:
        print(
            "Existing accounts retained. Credentials remain in local_credentials.txt."
        )
    return output


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--practice", action="store_true")
    p.add_argument("--setup-only", action="store_true")
    p.add_argument("--port", type=int, default=8000)
    args = p.parse_args()
    bootstrap(args.practice)
    if not args.setup_only:
        import uvicorn

        print(f"Open http://127.0.0.1:{args.port}/app/login.html")
        uvicorn.run(main.app, host="127.0.0.1", port=args.port)
