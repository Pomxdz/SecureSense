"""Submission-ready local practice supervisor.

Starts the local SecureSense backend, mail sandbox and SMTP proxy from one command.
If an official Gophish executable is configured or found in a common local path, it
can also be started. Gophish is intentionally not bundled in the submission archive.
"""

from __future__ import annotations

import argparse
import os
import shutil
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")


def env_int(name: str, default: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise SystemExit(f"{name} must be an integer, not {raw!r}") from exc
    if not 1 <= value <= 65535:
        raise SystemExit(f"{name} must be between 1 and 65535")
    return value


def env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


APP_HOST = "127.0.0.1"
APP_PORT = env_int("SECURESENSE_PORT", 8000)
MAILBOX_HOST = "127.0.0.1"
MAILBOX_SMTP_PORT = env_int("MAILBOX_SMTP_PORT", 1028)
MAILBOX_WEB_PORT = env_int("MAILBOX_WEB_PORT", 8025)
PROXY_HOST = "127.0.0.1"
PROXY_PORT = env_int("PROXY_PORT", 1027)
RELAY_PORT = env_int("RELAY_PORT", MAILBOX_SMTP_PORT)
GOPHISH_ADMIN_URL = os.getenv("GOPHISH_ADMIN_URL", "https://127.0.0.1:3333").strip()
AUTO_OPEN_BROWSER = env_bool("AUTO_OPEN_BROWSER", True)
GOPHISH_AUTO_START = env_bool("GOPHISH_AUTO_START", True)
VIVA_AUTO_SEED_GOPHISH = env_bool("VIVA_AUTO_SEED_GOPHISH", True)


class ServiceError(RuntimeError):
    pass


def port_open(host: str, port: int, timeout: float = 0.25) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def wait_for_port(host: str, port: int, seconds: float, label: str) -> None:
    deadline = time.time() + seconds
    while time.time() < deadline:
        if port_open(host, port):
            return
        time.sleep(0.15)
    raise ServiceError(f"{label} did not become ready on {host}:{port}")


def ensure_free(host: str, port: int, label: str) -> None:
    if port_open(host, port):
        raise ServiceError(
            f"{label} cannot start because {host}:{port} is already in use. "
            f"Stop the existing process or change the matching value in .env."
        )


def detect_gophish() -> Path | None:
    configured = os.getenv("GOPHISH_EXE", "").strip().strip('"')
    candidates: list[Path] = []
    if configured:
        candidates.append(Path(configured).expanduser())
    if os.name == "nt":
        candidates.extend(
            [
                ROOT / "gophish.exe",
                ROOT.parent / "Gophish" / "gophish.exe",
                Path("C:/Gophish/gophish.exe"),
                Path("C:/gophish/gophish.exe"),
            ]
        )
    else:
        which = shutil.which("gophish")
        if which:
            candidates.append(Path(which))
        candidates.extend([ROOT / "gophish", ROOT.parent / "gophish" / "gophish"])
    for candidate in candidates:
        try:
            candidate = candidate.resolve()
        except OSError:
            continue
        if candidate.is_file():
            return candidate
    return None


def gophish_admin_endpoint() -> tuple[str, int]:
    parsed = urlsplit(GOPHISH_ADMIN_URL)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise SystemExit("GOPHISH_ADMIN_URL must be a valid local HTTP/HTTPS URL")
    return parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80)


def child_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("SECURESENSE_PORT", str(APP_PORT))
    env.setdefault("MAILBOX_SMTP_PORT", str(MAILBOX_SMTP_PORT))
    env.setdefault("MAILBOX_WEB_PORT", str(MAILBOX_WEB_PORT))
    env.setdefault("PROXY_HOST", PROXY_HOST)
    env.setdefault("PROXY_PORT", str(PROXY_PORT))
    env.setdefault("RELAY_HOST", MAILBOX_HOST)
    env.setdefault("RELAY_PORT", str(RELAY_PORT))
    env.setdefault("GOPHISH_PHISHING_URL", "http://127.0.0.1/")
    return env


def spawn_python(label: str, relative_script: str, *args: str) -> subprocess.Popen:
    print(f"[start] {label}")
    return subprocess.Popen(
        [sys.executable, str(ROOT / relative_script), *args],
        cwd=ROOT,
        env=child_env(),
    )


def spawn_gophish(executable: Path) -> subprocess.Popen:
    print(f"[start] Gophish: {executable}")
    return subprocess.Popen([str(executable)], cwd=executable.parent, env=child_env())


def terminate(children: list[tuple[str, subprocess.Popen]]) -> None:
    for _, process in reversed(children):
        if process.poll() is None:
            process.terminate()
    for _, process in reversed(children):
        if process.poll() is None:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


def main() -> int:
    parser = argparse.ArgumentParser(description="Start the complete local SecureSense practice stack")
    parser.add_argument("--no-gophish", action="store_true", help="Do not auto-start Gophish")
    parser.add_argument("--no-browser", action="store_true", help="Do not open practice pages")
    args = parser.parse_args()

    children: list[tuple[str, subprocess.Popen]] = []
    gophish_started_here = False
    try:
        # These three services are owned by this project and must be free before startup.
        ensure_free(MAILBOX_HOST, MAILBOX_SMTP_PORT, "Mail sandbox SMTP")
        ensure_free(MAILBOX_HOST, MAILBOX_WEB_PORT, "Mail sandbox web inbox")
        ensure_free(PROXY_HOST, PROXY_PORT, "SMTP proxy")
        ensure_free(APP_HOST, APP_PORT, "SecureSense application")

        admin_host, admin_port = gophish_admin_endpoint()
        gophish_running = port_open(admin_host, admin_port)
        gophish_exe = None if args.no_gophish else detect_gophish()

        if not gophish_running and not args.no_gophish and GOPHISH_AUTO_START and gophish_exe:
            process = spawn_gophish(gophish_exe)
            children.append(("Gophish", process))
            gophish_started_here = True

        sandbox = spawn_python("Mail sandbox", "Member1/mail_sandbox.py")
        children.append(("Mail sandbox", sandbox))
        wait_for_port(MAILBOX_HOST, MAILBOX_SMTP_PORT, 12, "Mail sandbox SMTP")
        wait_for_port(MAILBOX_HOST, MAILBOX_WEB_PORT, 12, "Mail sandbox web inbox")

        proxy = spawn_python("SMTP proxy", "Member1/smtp_proxy.py")
        children.append(("SMTP proxy", proxy))
        wait_for_port(PROXY_HOST, PROXY_PORT, 12, "SMTP proxy")

        app = spawn_python("SecureSense", "run.py", "--practice", "--port", str(APP_PORT))
        children.append(("SecureSense", app))
        wait_for_port(APP_HOST, APP_PORT, 20, "SecureSense")

        # If Gophish was launched here, give it a chance to expose the admin listener.
        if gophish_started_here:
            try:
                wait_for_port(admin_host, admin_port, 15, "Gophish admin")
                gophish_running = True
            except ServiceError as exc:
                print(f"[warn] {exc}")
        else:
            gophish_running = port_open(admin_host, admin_port)

        print("\nSecureSense practice stack is ready")
        print("=" * 62)
        print(f"SecureSense       http://{APP_HOST}:{APP_PORT}/app/login.html")
        print(f"Test inbox      http://{MAILBOX_HOST}:{MAILBOX_WEB_PORT}")
        print(f"SMTP proxy      {PROXY_HOST}:{PROXY_PORT}")
        print(f"Sandbox SMTP    {MAILBOX_HOST}:{MAILBOX_SMTP_PORT}")
        print(f"Gophish admin   {GOPHISH_ADMIN_URL}  ({'running' if gophish_running else 'not started'})")
        print("=" * 62)
        if not gophish_running:
            print(
                "Gophish is an external official download. Set GOPHISH_EXE in .env "
                "(for example C:/Gophish/gophish.exe) or start it manually."
            )
        elif VIVA_AUTO_SEED_GOPHISH:
            if os.getenv("GOPHISH_API_KEY", "").strip():
                print("[setup] Preparing five localhost-only Gophish viva campaigns...")
                from seed_viva_gophish import credentials_from_local_file
                sync_credentials = credentials_from_local_file()
                if sync_credentials:
                    os.environ["SECURESENSE_SYNC_EMAIL"], os.environ["SECURESENSE_SYNC_PASSWORD"] = sync_credentials
                seeded = subprocess.run(
                    [sys.executable, str(ROOT / "seed_viva_gophish.py"), "--fresh"],
                    cwd=ROOT,
                    env=child_env(),
                    check=False,
                )
                if seeded.returncode == 0 and (ROOT / "viva_profiles.json").is_file():
                    poller = spawn_python("Gophish live sync", "sync_gophish.py", str(ROOT / "viva_profiles.json"), "--interval", "10", "--url", f"http://{APP_HOST}:{APP_PORT}")
                    children.append(("Gophish live sync", poller))
                if seeded.returncode != 0:
                    print(
                        "[warn] Viva campaign seeding was skipped/failed. The practice stack is still running; "
                        "review .env or run prepare_viva_campaigns.bat after fixing Gophish access."
                    )
            else:
                print(
                    "[info] Gophish is running, but GOPHISH_API_KEY is blank. Add the local API key to .env "
                    "and rerun start_practice.bat to auto-create the five viva campaigns."
                )
        print("Press CTRL+C once in this window to stop the SecureSense-owned services.\n")

        if AUTO_OPEN_BROWSER and not args.no_browser:
            webbrowser.open(f"http://{APP_HOST}:{APP_PORT}/app/login.html")
            webbrowser.open(f"http://{MAILBOX_HOST}:{MAILBOX_WEB_PORT}")

        warned_optional_exit = False
        while True:
            for label, process in children:
                code = process.poll()
                if code is None:
                    continue
                if label == "Gophish":
                    if not warned_optional_exit:
                        print(f"[warn] Gophish exited with code {code}; SecureSense local services remain available.")
                        warned_optional_exit = True
                    continue
                raise ServiceError(f"{label} exited unexpectedly with code {code}")
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nStopping local practice services...")
        return 0
    except ServiceError as exc:
        print(f"\n[error] {exc}", file=sys.stderr)
        return 1
    finally:
        terminate(children)


if __name__ == "__main__":
    raise SystemExit(main())
