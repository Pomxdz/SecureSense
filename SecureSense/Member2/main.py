"""SecureSense v3. Automatic AI scoring, reproducible evidence and targeted learning."""

from __future__ import annotations
import csv, hashlib, hmac, io, json, math, os, secrets, sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBearer
from pydantic import BaseModel, Field, ConfigDict

ROOT = Path(__file__).resolve().parent.parent
import sys
sys.path.insert(0, str(ROOT))
from gophish_reporting import report_to_gophish
load_dotenv(ROOT / ".env")
DB_PATH = Path(os.getenv("SECURESENSE_DB", str(Path(__file__).with_name("securesense_v2.db"))))
VERSION = "3.0.0"
SCORING_VERSION = "behaviour-v1"
ACTIONS = {
    "Email Sent": "sent",
    "Email Opened": "opened",
    "Clicked Link": "clicked",
    "Submitted Data": "test_form_submitted",
    "Email Reported": "reported",
    "Error Sending Email": "send_error",
}
CATEGORIES = [
    "Financial Fraud",
    "Credential Harvesting",
    "Urgent Extortion",
    "Social Engineering",
    "Malware Delivery",
    "General",
]
TRAINING = dict(
    zip(
        CATEGORIES,
        [
            "Invoice and Payroll Verification",
            "Account and Form Verification",
            "Handling Urgency and Threats",
            "Recognizing Persuasion and Impersonation",
            "Safe Links and Attachments",
            "Recognize Verify and Report",
        ],
    )
)


def now():
    return datetime.now(timezone.utc).isoformat()


def date(value):
    try:
        d = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if d.tzinfo is None:
            raise ValueError()
        return d.astimezone(timezone.utc)
    except (ValueError, TypeError):
        raise HTTPException(422, "Timezone-aware ISO event time required")


def email(value):
    v = str(value).strip().lower()
    if len(v) > 254 or "@" not in v or any(x in v for x in "\r\n\x00<>\"' "):
        raise HTTPException(422, "Valid email required")
    return v


@contextmanager
def db():
    c = sqlite3.connect(DB_PATH, timeout=15)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    try:
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    return (
        salt
        + ":"
        + hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 240000).hex()
    )


def setup_database():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with db() as c:
        c.executescript("""
CREATE TABLE IF NOT EXISTS users(email TEXT PRIMARY KEY,name TEXT NOT NULL,department TEXT NOT NULL,role TEXT CHECK(role IN ('admin','employee')),password_hash TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY,email TEXT REFERENCES users(email),expires TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS login_attempts(id INTEGER PRIMARY KEY,ip TEXT,at TEXT);
CREATE TABLE IF NOT EXISTS campaigns(id TEXT PRIMARY KEY,name TEXT,category TEXT,theme TEXT,objective TEXT,persuasion TEXT,identity TEXT,warning_signs TEXT,difficulty TEXT,audience_relevance TEXT,source TEXT CHECK(source IN ('practice','live')),launched_at TEXT,scoring_version TEXT);
CREATE TABLE IF NOT EXISTS recipients(campaign_id TEXT REFERENCES campaigns(id),email TEXT REFERENCES users(email),rid TEXT,PRIMARY KEY(campaign_id,email),UNIQUE(campaign_id,rid));
CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,dedup_key TEXT UNIQUE,campaign_id TEXT,email TEXT,action TEXT,occurred_at TEXT,received_at TEXT,quality TEXT CHECK(quality IN ('human','suspected','automated','unknown')),FOREIGN KEY(campaign_id,email) REFERENCES recipients(campaign_id,email));
CREATE TABLE IF NOT EXISTS quarantine(id INTEGER PRIMARY KEY,received_at TEXT,reason TEXT,campaign_id TEXT);
CREATE TABLE IF NOT EXISTS assessments(id INTEGER PRIMARY KEY,email TEXT REFERENCES users(email),assessed_at TEXT,scoring_version TEXT,score REAL,evidence_json TEXT);
CREATE TABLE IF NOT EXISTS assignments(id INTEGER PRIMARY KEY,email TEXT REFERENCES users(email),campaign_id TEXT REFERENCES campaigns(id),category TEXT,module TEXT,status TEXT DEFAULT 'assigned',assigned_at TEXT,started_at TEXT,completed_at TEXT,due_at TEXT,owner TEXT DEFAULT 'InfoSec',source TEXT,UNIQUE(email,campaign_id,category));
CREATE TABLE IF NOT EXISTS quiz_attempts(id INTEGER PRIMARY KEY,assignment_id INTEGER REFERENCES assignments(id),at TEXT,score REAL,passed INTEGER,answers_json TEXT,source TEXT);
CREATE TABLE IF NOT EXISTS reflections(id INTEGER PRIMARY KEY,email TEXT REFERENCES users(email),campaign_id TEXT REFERENCES campaigns(id),reason TEXT,at TEXT,UNIQUE(email,campaign_id));
CREATE TABLE IF NOT EXISTS ai_notes(email TEXT PRIMARY KEY REFERENCES users(email),at TEXT,status TEXT,content TEXT);
CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,at TEXT,actor TEXT,action TEXT,object_id TEXT);
CREATE TABLE IF NOT EXISTS participant_reports(campaign_id TEXT,email TEXT,reason TEXT,reported_at TEXT,PRIMARY KEY(campaign_id,email),FOREIGN KEY(campaign_id,email) REFERENCES recipients(campaign_id,email));
CREATE TABLE IF NOT EXISTS quiz_questions(id INTEGER PRIMARY KEY,category TEXT NOT NULL,prompt TEXT NOT NULL,options_json TEXT NOT NULL,correct_index INTEGER NOT NULL,sort_order INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS quiz_config(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS quiz_questions_category_order ON quiz_questions(category,sort_order,id);
CREATE INDEX IF NOT EXISTS events_recipient ON events(campaign_id,email,occurred_at);
""")
        if "source" not in [row[1] for row in c.execute("PRAGMA table_info(ai_notes)")]:
            c.execute("ALTER TABLE ai_notes ADD COLUMN source TEXT DEFAULT 'all'")
        seeded = c.execute("SELECT value FROM quiz_config WHERE key='default_quizzes_seeded'").fetchone()
        if not seeded:
            from learning_content import CONTENT
            for category, (_lesson, default_questions) in CONTENT.items():
                for order, question in enumerate(default_questions):
                    prompt, options, correct_index = question
                    c.execute(
                        "INSERT INTO quiz_questions(category,prompt,options_json,correct_index,sort_order) VALUES(?,?,?,?,?)",
                        (category, prompt, json.dumps(options), int(correct_index), order),
                    )
            c.execute("INSERT INTO quiz_config(key,value) VALUES('default_quizzes_seeded','1')")

    if "proposal_features" in globals():
        proposal_features.setup_schema(__import__(__name__))


def audit(c, actor, action, obj):
    c.execute(
        "INSERT INTO audit(at,actor,action,object_id) VALUES(?,?,?,?)",
        (now(), actor, action, str(obj)),
    )


setup_database()
app = FastAPI(
    title="SecureSense Behaviour and Learning API",
    version=VERSION,
    docs_url=None,
    redoc_url=None,
)


@app.middleware("http")
async def security_headers(request, call_next):
    r = await call_next(request)
    r.headers.update(
        {
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
            "X-Frame-Options": "DENY",
            "Cache-Control": "no-store",
            "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
        }
    )
    return r


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Login(Strict):
    email: str = Field(max_length=254)
    password: str = Field(min_length=1, max_length=256)


bearer = HTTPBearer(auto_error=False)


def current_user(request: Request, credential=Depends(bearer)):
    h = request.headers.get("Authorization", "")
    if not h.startswith("Bearer "):
        raise HTTPException(401, "Sign in required")
    with db() as c:
        u = c.execute(
            "SELECT u.* FROM sessions s JOIN users u ON s.email=u.email WHERE s.token_hash=? AND s.expires>?",
            (hashlib.sha256(h[7:].encode()).hexdigest(), now()),
        ).fetchone()
    if not u:
        raise HTTPException(401, "Session expired or invalid")
    return dict(u)


def admin(u=Depends(current_user)):
    if u["role"] != "admin":
        raise HTTPException(403, "Administrator access required")
    return u


def authorize(u, target):
    if u["role"] != "admin" and u["email"] != target:
        raise HTTPException(403, "You can access only your own profile")


@app.post("/auth/login")
def login(p: Login, request: Request):
    key = request.client.host if request.client else "unknown"
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()
    with db() as c:
        c.execute("DELETE FROM login_attempts WHERE at<?", (cutoff,))
        if (
            c.execute(
                "SELECT COUNT(*) FROM login_attempts WHERE ip=?", (key,)
            ).fetchone()[0]
            >= 20
        ):
            raise HTTPException(429, "Too many attempts. Try again in 15 minutes.")
        c.execute("INSERT INTO login_attempts(ip,at) VALUES(?,?)", (key, now()))
        u = c.execute(
            "SELECT * FROM users WHERE email=?", (p.email.strip().lower(),)
        ).fetchone()
        stored = u["password_hash"] if u else "0" * 32 + ":" + "0" * 64
        ok = hmac.compare_digest(
            password_hash(p.password, stored.split(":")[0]), stored
        )
    if not u or not ok:
        raise HTTPException(401, "Invalid email or password")
    token = secrets.token_urlsafe(32)
    with db() as c:
        c.execute(
            "INSERT INTO sessions VALUES(?,?,?)",
            (
                hashlib.sha256(token.encode()).hexdigest(),
                u["email"],
                (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
            ),
        )
        audit(c, u["email"], "login", u["email"])
    return {
        "token": token,
        "user": {k: u[k] for k in ["email", "name", "department", "role"]},
    }


@app.get("/auth/me")
def me(u=Depends(current_user)):
    return {k: u[k] for k in ["email", "name", "department", "role"]}


@app.post("/auth/logout")
def logout(request: Request, u=Depends(current_user)):
    with db() as c:
        c.execute(
            "DELETE FROM sessions WHERE token_hash=?",
            (
                hashlib.sha256(
                    request.headers["Authorization"][7:].encode()
                ).hexdigest(),
            ),
        )
    return {"status": "signed_out"}


class Campaign(Strict):
    id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=160)
    category: Literal[
        "Financial Fraud",
        "Credential Harvesting",
        "Urgent Extortion",
        "Social Engineering",
        "Malware Delivery",
        "General",
    ] = "General"
    theme: str = Field(default="General", max_length=120)
    objective: Literal["link_interaction", "test_form_submission"] = (
        "test_form_submission"
    )
    persuasion: list[
        Literal["urgency", "authority", "fear", "reward", "familiarity"]
    ] = Field(default_factory=list, max_length=5)
    identity: str = Field(default="Unspecified", max_length=120)
    warning_signs: list[str] = Field(default_factory=list, max_length=10)
    difficulty: Literal["easy", "moderate", "hard"] = "moderate"
    audience_relevance: str = Field(default="Not rated", max_length=200)
    source: Literal["practice", "live"] = "live"
    launched_at: str


class Recipient(Strict):
    email: str = Field(max_length=254)
    name: str = Field(default="Test participant", max_length=100)
    department: str = Field(default="Unassigned", max_length=100)
    rid: str = Field(min_length=1, max_length=100)


class CampaignImport(Strict):
    campaign: Campaign
    recipients: list[Recipient] = Field(min_length=1, max_length=5000)


def add_campaign(c, p):
    if any(len(s) > 200 for s in p.warning_signs):
        raise HTTPException(422, "Warning sign too long")
    c.execute(
        "INSERT INTO campaigns VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            p.id,
            p.name,
            p.category,
            p.theme,
            p.objective,
            json.dumps(p.persuasion),
            p.identity,
            json.dumps(p.warning_signs),
            p.difficulty,
            p.audience_relevance,
            p.source,
            date(p.launched_at).isoformat(),
            SCORING_VERSION,
        ),
    )


@app.post("/admin/campaigns")
def campaign_import(p: CampaignImport, u=Depends(admin)):
    with db() as c:
        if c.execute("SELECT 1 FROM campaigns WHERE id=?", (p.campaign.id,)).fetchone():
            raise HTTPException(
                409, "Campaign exists; metadata is immutable after import"
            )
        add_campaign(c, p.campaign)
        for r in p.recipients:
            e = email(r.email)
            c.execute(
                "INSERT OR IGNORE INTO users VALUES(?,?,?,?,?)",
                (
                    e,
                    r.name,
                    r.department,
                    "employee",
                    password_hash(secrets.token_urlsafe(32)),
                ),
            )
            try:
                c.execute(
                    "INSERT INTO recipients VALUES(?,?,?)", (p.campaign.id, e, r.rid)
                )
            except sqlite3.IntegrityError:
                raise HTTPException(422, "Duplicate recipient or tracking id")
        audit(c, u["email"], "campaign_import", p.campaign.id)
    return {"status": "imported", "participants": len(p.recipients)}


class Account(Strict):
    email: str
    name: str = Field(max_length=100)
    department: str = Field(max_length=100)
    password: str = Field(min_length=12, max_length=256)
    role: Literal["employee", "admin"] = "employee"


@app.post("/admin/users")
def provision(p: Account, u=Depends(admin)):
    e = email(p.email)
    with db() as c:
        c.execute(
            "INSERT INTO users VALUES(?,?,?,?,?) ON CONFLICT(email) DO UPDATE SET name=excluded.name,department=excluded.department,role=excluded.role,password_hash=excluded.password_hash",
            (e, p.name, p.department, p.role, password_hash(p.password)),
        )
        c.execute("DELETE FROM sessions WHERE email=?", (e,))
        audit(c, u["email"], "account_provision", e)
    return {"status": "provisioned"}


def normalize_event(c, p, bound_campaign=None):
    if not isinstance(p.get("email"), str):
        raise HTTPException(422, "Event email must be a string")
    message = p.get("message")
    explicit = p.get("action")
    if (message is not None and not isinstance(message, str)) or (
        explicit is not None and not isinstance(explicit, str)
    ):
        raise HTTPException(422, "Event action must be a string")
    e = email(p.get("email", ""))
    action = ACTIONS.get(message, explicit)
    if action not in set(ACTIONS.values()):
        raise HTTPException(422, "Unsupported action; unknown events are not failures")
    occurred = date(p.get("time", p.get("occurred_at"))).isoformat()
    if date(occurred) > datetime.now(timezone.utc) + timedelta(minutes=5):
        raise HTTPException(422, "Event is in the future")
    details = p.get("details", {})
    if details is None or details == "":
        details = {}
    if isinstance(details, str):
        try:
            details = json.loads(details)
        except ValueError:
            raise HTTPException(422, "Invalid event details JSON")
    if not isinstance(details, dict):
        raise HTTPException(422, "Event details must be an object")
    payload = details.get("payload", {})
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        raise HTTPException(422, "Invalid event payload")
    rid = p.get("rid") or payload.get("rid")
    if isinstance(rid, list):
        rid = rid[0] if rid else None
    campaign = bound_campaign or p.get("campaign_id")
    if campaign:
        rows = c.execute(
            "SELECT * FROM recipients WHERE campaign_id=? AND email=?",
            (str(campaign), e),
        ).fetchall()
        if rid and rows and str(rid) != rows[0]["rid"]:
            rows = []
    elif rid:
        rows = c.execute(
            "SELECT * FROM recipients WHERE rid=? AND email=?", (str(rid), e)
        ).fetchall()
    else:
        rows = []
    if len(rows) != 1:
        raise HTTPException(
            422,
            "Campaign mapping missing or ambiguous; bind campaign_id or import rid mapping",
        )
    browser = details.get("browser") or payload.get("browser") or {}
    ua = str(browser.get("user-agent", "")) if isinstance(browser, dict) else ""
    suspected = any(
        t in ua.lower()
        for t in ["bot", "scanner", "safe links", "proofpoint", "headless"]
    )
    quality = (
        "suspected"
        if suspected and action in ["opened", "clicked", "test_form_submitted"]
        else "human"
    )
    return rows[0]["campaign_id"], e, action, occurred, quality


def record_event(c, p, bound_campaign=None):
    campaign, e, action, occurred, quality = normalize_event(c, p, bound_campaign)
    digest = hashlib.sha256(
        json.dumps([campaign, e, action, occurred], separators=(",", ":")).encode()
    ).hexdigest()
    cur = c.execute(
        "INSERT OR IGNORE INTO events(dedup_key,campaign_id,email,action,occurred_at,received_at,quality) VALUES(?,?,?,?,?,?,?)",
        (digest, campaign, e, action, occurred, now(), quality),
    )
    if cur.rowcount:
        reconcile_assignment(c, campaign, e)
        source = c.execute(
            "SELECT source FROM campaigns WHERE id=?", (campaign,)
        ).fetchone()[0]
        a = profile_assessment(
            c, e, [x for x in outcomes(c, e) if x["source"] == source]
        )
        a["source"] = source
        proposal_features.enqueue(c, e, source)
        c.execute(
            "INSERT INTO assessments(email,assessed_at,scoring_version,score,evidence_json) VALUES(?,?,?,?,?)",
            (e, now(), SCORING_VERSION, None, json.dumps(a)),
        )
    return {
        "status": "recorded" if cur.rowcount else "duplicate",
        "campaign_id": campaign,
    }


@app.post("/webhook")
async def webhook(request: Request, campaign_id: str | None = None):
    secret = os.getenv("GOPHISH_WEBHOOK_SECRET", "")
    if not secret:
        raise HTTPException(503, "Webhook secret is not configured")
    chunks = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > 65536:
            raise HTTPException(413, "Event body too large")
        chunks.append(chunk)
    raw = b"".join(chunks)
    expected = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(
        expected, request.headers.get("X-Gophish-Signature", "")
    ):
        raise HTTPException(401, "Invalid webhook signature")
    try:
        p = json.loads(raw)
    except ValueError:
        raise HTTPException(422, "Invalid JSON")
    if not isinstance(p, dict):
        raise HTTPException(422, "Event must be an object")
    try:
        with db() as c:
            return record_event(c, p, campaign_id)
    except HTTPException as exc:
        with db() as c:
            c.execute(
                "INSERT INTO quarantine(received_at,reason,campaign_id) VALUES(?,?,?)",
                (now(), str(exc.detail), campaign_id),
            )
        raise


class QualityReview(Strict):
    quality: Literal["human", "automated"]
    reason: str = Field(min_length=5, max_length=300)


@app.post("/admin/events/{event_id}/quality")
def review_quality(event_id: int, p: QualityReview, u=Depends(admin)):
    with db() as c:
        row = c.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Event not found")
        c.execute("UPDATE events SET quality=? WHERE id=?", (p.quality, event_id))
        reconcile_assignment(c, row["campaign_id"], row["email"])
        source = c.execute(
            "SELECT source FROM campaigns WHERE id=?", (row["campaign_id"],)
        ).fetchone()[0]
        proposal_features.enqueue(c, row["email"], source)
        audit(c, u["email"], "event_quality_" + p.quality + ": " + p.reason, event_id)
    return {"status": "reviewed"}


def outcomes(c, e=None):
    sql = "SELECT r.campaign_id,r.email,u.name AS user_name,u.department,ca.* FROM recipients r JOIN campaigns ca ON ca.id=r.campaign_id JOIN users u ON u.email=r.email"
    records = c.execute(
        sql + (" WHERE r.email=?" if e else "") + " ORDER BY ca.launched_at,r.email",
        (e,) if e else (),
    ).fetchall()
    result = []
    for row in records:
        x = dict(row)
        ev = [
            dict(z)
            for z in c.execute(
                "SELECT * FROM events WHERE campaign_id=? AND email=? ORDER BY occurred_at,id",
                (x["campaign_id"], x["email"]),
            )
        ]
        times = {}
        for z in ev:
            if z["quality"] == "human":
                times.setdefault(z["action"], z["occurred_at"])
        sent = times.get("sent")
        send_events = [
            z
            for z in ev
            if z["quality"] == "human" and z["action"] in ["sent", "send_error"]
        ]
        sending_succeeded = bool(send_events and send_events[-1]["action"] == "sent")
        click = times.get("clicked")
        submit = times.get("test_form_submitted")
        report = times.get("reported")
        interaction = min([t for t in [click, submit] if t], default=None)
        if report and interaction and date(report) < date(interaction):
            journey = "reported_before_then_interacted"
        elif report and not interaction:
            journey = "reported_before_interaction"
        elif report and submit:
            journey = "submitted_then_reported"
        elif report and click:
            journey = "clicked_then_reported"
        elif submit:
            journey = "test_form_submitted"
        elif click:
            journey = "clicked_only"
        else:
            journey = "no_observed_interaction"
        timing = lambda t: (
            round((date(t) - date(sent)).total_seconds())
            if sent and t and date(t) >= date(sent)
            else None
        )
        x.update(
            sent=sending_succeeded,
            clicked=bool(interaction),
            submitted=bool(submit),
            reported=bool(report),
            journey=journey,
            time_to_click=timing(click),
            time_to_report=timing(report),
            events=ev,
            severity=80 if submit else 40 if click else 0 if report else None,
            suspected=sum(z["quality"] == "suspected" for z in ev),
            missing_click=bool(submit and not click),
        )
        result.append(x)
    return result


def reconcile_assignment(c, campaign, e):
    o = next(x for x in outcomes(c, e) if x["campaign_id"] == campaign)
    a = c.execute(
        "SELECT * FROM assignments WHERE email=? AND campaign_id=?", (e, campaign)
    ).fetchone()
    if o["clicked"]:
        if a and a["status"] == "cancelled":
            passed = c.execute(
                "SELECT 1 FROM quiz_attempts WHERE assignment_id=? AND passed=1",
                (a["id"],),
            ).fetchone()
            c.execute(
                "UPDATE assignments SET status=? WHERE id=?",
                ("passed" if passed else "assigned", a["id"]),
            )
        c.execute(
            "INSERT OR IGNORE INTO assignments(email,campaign_id,category,module,status,assigned_at,due_at,source) VALUES(?,?,?,?,?,?,?,?)",
            (
                e,
                campaign,
                o["category"],
                TRAINING[o["category"]],
                "assigned",
                now(),
                (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
                o["source"],
            ),
        )
    elif a:
        c.execute("UPDATE assignments SET status='cancelled' WHERE id=?", (a["id"],))


def profile_assessment(c, e, observations=None):
    oo = observations if observations is not None else outcomes(c, e)
    eligible = [x for x in oo if x["sent"]]
    seen = [x for x in eligible if x["severity"] is not None]
    risky = sum(x["clicked"] for x in eligible)
    # No risk score is calculated here. Scoring is done only by the AI service
    # (proposal_features.py); this function only counts observed facts.
    protective = sum(x["journey"] == "reported_before_interaction" for x in eligible)
    recovery = sum(
        x["journey"] in ["submitted_then_reported", "clicked_then_reported"]
        for x in eligible
    )
    return {
        "campaigns": len(eligible),
        "interactions": risky,
        "submissions": sum(x["submitted"] for x in eligible),
        "assessed_outcomes": len(seen),
        "coverage": (
            "limited" if len(seen) < 3 else "moderate" if len(seen) < 6 else "broader"
        ),
        "protective_reports": protective,
        "recovery_reports": recovery,
        "explanation": [
            f"{risky} of {len(eligible)} successfully sent campaign observations recorded interaction.",
            f'{sum(x["submitted"] for x in eligible)} test-form submissions; {protective} reports before interaction; {recovery} reports after interaction.',
            f"{len(seen)} outcomes are assessable. No interaction alone is not proof of safety.",
        ],
        "scoring_version": SCORING_VERSION,
    }


def rate(n, d):
    if not d:
        return {"n": n, "denominator": d, "percent": None, "interval": None}
    p = n / d
    z = 1.96
    mid = (p + z * z / (2 * d)) / (1 + z * z / d)
    half = z * math.sqrt(p * (1 - p) / d + z * z / (4 * d * d)) / (1 + z * z / d)
    return {
        "n": n,
        "denominator": d,
        "percent": round(p * 100, 1),
        "interval": [
            round(max(0, mid - half) * 100, 1),
            round(min(1, mid + half) * 100, 1),
        ],
    }


def summary(oo):
    eligible = [x for x in oo if x["sent"]]
    d = len(eligible)
    return {
        "sent_observations": d,
        "participants": len(set(x["email"] for x in eligible)),
        "click_rate": rate(sum(x["clicked"] for x in eligible), d),
        "submission_rate": rate(sum(x["submitted"] for x in eligible), d),
        "report_rate": rate(sum(x["reported"] for x in eligible), d),
        "protective_report_rate": rate(
            sum(x["journey"] == "reported_before_interaction" for x in eligible), d
        ),
    }


def filtered(c, source, department, campaign, category, difficulty, start, end):
    if source not in ["practice", "live"]:
        raise HTTPException(422, "Choose practice or live source")
    if start and end and start > end:
        raise HTTPException(422, "Start date must not follow end date")
    for s in [start, end]:
        if s:
            try:
                datetime.strptime(s, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(422, "Date filter must be YYYY-MM-DD")
    return [
        x
        for x in outcomes(c)
        if x["source"] == source
        and (not department or x["department"] == department)
        and (not campaign or x["campaign_id"] == campaign)
        and (not category or x["category"] == category)
        and (not difficulty or x["difficulty"] == difficulty)
        and (not start or x["launched_at"][:10] >= start)
        and (not end or x["launched_at"][:10] <= end)
    ]


def learning_progress(c, e, oo):
    pairs = []
    aa = c.execute(
        "SELECT a.*,ca.difficulty,ca.objective FROM assignments a JOIN campaigns ca ON ca.id=a.campaign_id WHERE a.email=? AND a.status='passed' ORDER BY a.completed_at",
        (e,),
    ).fetchall()
    for a in aa:
        baseline = next((x for x in oo if x["campaign_id"] == a["campaign_id"]), None)
        if not baseline:
            continue
        comparable = [
            x
            for x in oo
            if x["sent"]
            and x["source"] == a["source"]
            and x["campaign_id"] != a["campaign_id"]
            and x["category"] == a["category"]
            and x["difficulty"] == a["difficulty"]
            and x["objective"] == a["objective"]
            and date(x["launched_at"]) > date(a["completed_at"])
        ]
        retest = comparable[0] if comparable else None
        follow = comparable[1] if len(comparable) > 1 else None
        pairs.append(
            {
                "assignment_id": a["id"],
                "module": a["module"],
                "baseline": baseline["journey"],
                "retest": retest["journey"] if retest else "pending",
                "follow_up": follow["journey"] if follow else "pending",
                "interpretation": (
                    "Observed outcome improved"
                    if retest
                    and retest["severity"] is not None
                    and baseline["severity"] is not None
                    and retest["severity"] < baseline["severity"]
                    else (
                        "Outcome uncertain"
                        if retest and retest["severity"] is None
                        else (
                            "No measured improvement"
                            if retest
                            else "Awaiting comparable retest"
                        )
                    )
                ),
            }
        )
    return pairs


def legacy_count():
    p = Path(__file__).with_name("legacy_telemetry.db")
    if not p.exists():
        return 0
    with sqlite3.connect(f"file:{p.as_posix()}?mode=ro", uri=True) as c:
        return c.execute("SELECT COUNT(*) FROM user_metrics").fetchone()[0]


@app.get("/metrics")
def metrics(
    source: str = "practice",
    department: str = "",
    campaign: str = "",
    category: str = "",
    difficulty: str = "",
    start: str = "",
    end: str = "",
    u=Depends(admin),
):
    with db() as c:
        oo = filtered(c, source, department, campaign, category, difficulty, start, end)
        pairs = {(x["email"], x["campaign_id"]) for x in oo}
        aa = [
            dict(a)
            for a in c.execute("SELECT * FROM assignments")
            if (a["email"], a["campaign_id"]) in pairs and a["status"] != "cancelled"
        ]
        counts = {
            s: sum(a["status"] == s for a in aa)
            for s in ["assigned", "started", "completed", "passed"]
        }
        counts["overdue"] = sum(
            a["status"] != "passed" and date(a["due_at"]) < datetime.now(timezone.utc)
            for a in aa
        )
        groups = [
            {"category": k, **summary([x for x in oo if x["category"] == k])}
            for k in sorted(set(x["category"] for x in oo))
        ]
        campaign_rows = []
        for k in sorted(
            set(x["campaign_id"] for x in oo),
            key=lambda k: next(x["launched_at"] for x in oo if x["campaign_id"] == k),
        ):
            subset = [x for x in oo if x["campaign_id"] == k]
            f = subset[0]
            campaign_rows.append(
                {
                    "id": k,
                    "name": f["name"],
                    "difficulty": f["difficulty"],
                    "category": f["category"],
                    "theme": f["theme"],
                    "persuasion": json.loads(f["persuasion"]),
                    "launched_at": f["launched_at"],
                    **summary(subset),
                }
            )
        journeys = {
            k: sum(x["journey"] == k for x in oo if x["sent"])
            for k in [
                "reported_before_interaction",
                "reported_before_then_interacted",
                "clicked_then_reported",
                "submitted_then_reported",
                "test_form_submitted",
                "clicked_only",
                "no_observed_interaction",
            ]
        }
        users = []
        progress = []
        for e in sorted(set(x["email"] for x in oo)):
            subset = [x for x in oo if x["email"] == e]
            p = subset[0]
            users.append(
                {
                    "email": e,
                    "name": p["user_name"],
                    "department": p["department"],
                    **profile_assessment(c, e, subset),
                }
            )
            progress.extend({"email": e, **p} for p in learning_progress(c, e, subset))
        assessed = [x for x in users if x["assessed_outcomes"]]
        pending = [
            {
                "id": a["id"],
                "email": a["email"],
                "module": a["module"],
                "owner": a["owner"],
                "due_at": a["due_at"],
                "status": a["status"],
                "evidence": "Human interaction in campaign " + a["campaign_id"],
                "action": "Complete targeted module and comparable retest",
            }
            for a in aa
            if a["status"] != "passed"
        ]
        for pr in progress:
            if pr["retest"] == "pending":
                a = next((a for a in aa if a["id"] == pr["assignment_id"]), None)
                if a:
                    pending.append(
                        {
                            "id": a["id"],
                            "email": a["email"],
                            "module": a["module"],
                            "owner": a["owner"],
                            "due_at": a["due_at"],
                            "status": "retest_pending",
                            "evidence": "Verified pass; no later comparable campaign in this selection",
                            "action": "Schedule or inspect a comparable retest",
                        }
                    )
        suspected = [
            {
                "id": z["id"],
                "email": x["email"],
                "campaign_id": x["campaign_id"],
                "action": z["action"],
                "time": z["occurred_at"],
            }
            for x in oo
            for z in x["events"]
            if z["quality"] == "suspected"
        ]
        timings = sorted(
            x["time_to_report"]
            for x in oo
            if x["sent"] and x["time_to_report"] is not None
        )
        median = (
            (timings[(len(timings) - 1) // 2] + timings[len(timings) // 2]) / 2
            if timings
            else None
        )
        pending.sort(key=lambda a: a["due_at"])
        return {
            "version": VERSION,
            "scoring_version": SCORING_VERSION,
            "source": source,
            "refreshed_at": now(),
            **summary(oo),
            "assessed_people": len(assessed),
            "training": counts,
            "training_completion": rate(counts["passed"], len(aa)),
            "categories": groups,
            "departments": [
                {"department": k, **summary([x for x in oo if x["department"] == k])}
                for k in sorted(set(x["department"] for x in oo))
            ],
            "persuasion": [
                {
                    "technique": tag,
                    **summary([x for x in oo if tag in json.loads(x["persuasion"])]),
                }
                for tag in ["urgency", "authority", "fear", "reward", "familiarity"]
                if any(tag in json.loads(x["persuasion"]) for x in oo)
            ],
            "campaigns": campaign_rows,
            "journeys": journeys,
            "people": users,
            "progress": progress,
            "action_queue": pending,
            "suspected_events": suspected,
            "median_report_seconds": median,
            "quality": {
                "suspected_events": len(suspected),
                "missing_click_events": sum(x["missing_click"] for x in oo),
                "unassessed_observations": sum(
                    x["sent"] and x["severity"] is None for x in oo
                ),
                "quarantined_events_global": c.execute(
                    "SELECT COUNT(*) FROM quarantine"
                ).fetchone()[0],
                "legacy_records_excluded": legacy_count(),
            },
            "filters": {
                "campaigns": [
                    dict(x)
                    for x in c.execute(
                        "SELECT id,name,difficulty,category,source FROM campaigns WHERE source=? ORDER BY launched_at",
                        (source,),
                    )
                ],
                "departments": sorted(
                    set(x["department"] for x in outcomes(c) if x["source"] == source)
                ),
                "categories": CATEGORIES,
                "difficulties": ["easy", "moderate", "hard"],
            },
        }


@app.get("/user/{target}")
def user_data(target: str, u=Depends(current_user)):
    target = email(target)
    authorize(u, target)
    with db() as c:
        person = c.execute(
            "SELECT email,name,department FROM users WHERE email=?", (target,)
        ).fetchone()
        if not person:
            raise HTTPException(404, "Profile not found")
        oo = outcomes(c, target)
        aa = [
            dict(a)
            for a in c.execute(
                "SELECT * FROM assignments WHERE email=? AND status!='cancelled' ORDER BY assigned_at DESC",
                (target,),
            )
        ]
        for a in aa:
            last = c.execute(
                "SELECT score,passed,at FROM quiz_attempts WHERE assignment_id=? ORDER BY id DESC LIMIT 1",
                (a["id"],),
            ).fetchone()
            a["latest_result"] = dict(last) if last else None
        return {
            "user": dict(person),
            "assessments": {
                s: profile_assessment(c, target, [x for x in oo if x["source"] == s])
                for s in ["practice", "live"]
            },
            "assignments": aa,
            "history": [
                {
                    "campaign_id": x["campaign_id"],
                    "campaign": x["name"],
                    "category": x["category"],
                    "difficulty": x["difficulty"],
                    "source": x["source"],
                    "journey": x["journey"],
                    "time_to_click": x["time_to_click"],
                    "time_to_report": x["time_to_report"],
                    "events": [
                        {
                            "action": z["action"],
                            "time": z["occurred_at"],
                            "quality": z["quality"],
                        }
                        for z in x["events"]
                    ],
                }
                for x in reversed(oo)
            ],
            "progress": learning_progress(c, target, oo),
            "ai_note": dict(
                c.execute(
                    "SELECT at,status,content,source FROM ai_notes WHERE email=?", (target,)
                ).fetchone()
                or {}
            ),
        }


QUIZ = [
    (
        "An urgent message asks you to verify your account through a link. What should you do?",
        [
            "Use a known official website or verified contact",
            "Follow the link immediately",
            "Reply with your password",
        ],
        0,
    ),
    (
        "You clicked a suspicious link. What is the best next action?",
        [
            "Keep it secret",
            "Stop interacting and report promptly",
            "Enter information to see what happens",
        ],
        1,
    ),
    (
        "A familiar display name appears above an unusual sender address. What matters?",
        [
            "Only the display name",
            "The message colour",
            "Verify the actual sender and request independently",
        ],
        2,
    ),
    (
        "A message asks for a password or one-time code. What should you do?",
        [
            "Share it if the message is urgent",
            "Never share it; verify and report through the approved channel",
            "Forward the code to a colleague",
        ],
        1,
    ),
    (
        "Why should you report a suspicious message even after interacting?",
        [
            "It helps the security team respond and protect others",
            "It automatically cancels all risk",
            "It guarantees that no harm occurred",
        ],
        0,
    ),
]
CATEGORY_QUESTION = {
    "Financial Fraud": (
        "An unexpected invoice changes the payment account. What should you do?",
        [
            "Verify through a previously known contact and follow payment approval rules",
            "Pay because the invoice has a logo",
            "Use the phone number in that message only",
        ],
        0,
    ),
    "Credential Harvesting": (
        "A link opens a sign-in form you did not expect. What should you do?",
        [
            "Enter a test password",
            "Use the official service independently and report the suspicious form",
            "Trust the padlock alone",
        ],
        1,
    ),
    "Urgent Extortion": (
        "A message threatens consequences unless you act now. What should you do?",
        [
            "Let urgency override verification",
            "Send the requested information",
            "Pause and verify through a trusted independent channel",
        ],
        2,
    ),
    "Social Engineering": (
        "A supposed manager asks you to bypass a normal process. What should you do?",
        [
            "Verify the identity independently and follow the approved process",
            "Do it because of their title",
            "Ask only the same sender to confirm",
        ],
        0,
    ),
    "Malware Delivery": (
        "An unexpected attachment claims to be a required update. What should you do?",
        [
            "Install it immediately",
            "Use approved update channels and report the attachment",
            "Disable protection to open it",
        ],
        1,
    ),
    "General": QUIZ[0],
}


def questions(a, connection=None):
    """Return the current admin-managed quiz for an assignment category."""
    def load(c):
        rows = c.execute(
            "SELECT prompt,options_json,correct_index FROM quiz_questions WHERE category=? ORDER BY sort_order,id",
            (a["category"],),
        ).fetchall()
        result = []
        for row in rows:
            options = json.loads(row["options_json"])
            result.append((row["prompt"], options, row["correct_index"]))
        return result

    if connection is not None:
        return load(connection)
    with db() as c:
        return load(c)


def assignment(c, i, u):
    a = c.execute("SELECT * FROM assignments WHERE id=?", (i,)).fetchone()
    if not a or a["status"] == "cancelled":
        raise HTTPException(404, "Assignment not found")
    authorize(u, a["email"])
    return a


@app.get("/training/{i}")
def training(i: int, u=Depends(current_user)):
    with db() as c:
        a = assignment(c, i, u)
        qq = questions(a, c)
        if not qq:
            raise HTTPException(409, "This quiz currently has no questions. Ask an administrator to configure it.")
        return {
            "id": i,
            "module": a["module"],
            "status": a["status"],
            "pass_percent": 80,
            "lesson": __import__("learning_content").CONTENT[a["category"]][0],
            "questions": [
                {"id": j, "prompt": q[0], "options": q[1]}
                for j, q in enumerate(qq)
            ],
        }


@app.post("/training/{i}/start")
def start_training(i: int, u=Depends(current_user)):
    with db() as c:
        a = assignment(c, i, u)
        if a["status"] == "assigned":
            c.execute(
                "UPDATE assignments SET status='started',started_at=? WHERE id=?",
                (now(), i),
            )
        audit(c, u["email"], "training_start", i)
    return {"status": "started" if a["status"] == "assigned" else a["status"]}


class Answers(Strict):
    answers: list[int] = Field(min_length=1, max_length=20)


@app.post("/training/{i}/submit")
def submit(i: int, p: Answers, u=Depends(current_user)):
    with db() as c:
        a = assignment(c, i, u)
        if not a["started_at"]:
            raise HTTPException(409, "Start the module before submitting")
        qq = questions(a, c)
        if not qq:
            raise HTTPException(409, "This quiz currently has no questions. Ask an administrator to configure it.")
        if len(p.answers) != len(qq):
            raise HTTPException(422, f"Submit exactly {len(qq)} answers")
        if any(v < 0 or v >= len(qq[j][1]) for j, v in enumerate(p.answers)):
            raise HTTPException(422, "Invalid answer index")
        correct_count = sum(p.answers[j] == q[2] for j, q in enumerate(qq))
        score = round(correct_count / len(qq) * 100, 1)
        if float(score).is_integer():
            score = int(score)
        passed = score >= 80
        at = now()
        c.execute(
            "INSERT INTO quiz_attempts(assignment_id,at,score,passed,answers_json,source) VALUES(?,?,?,?,?,?)",
            (i, at, score, int(passed), json.dumps(p.answers), a["source"]),
        )
        if a["status"] != "passed":
            c.execute(
                "UPDATE assignments SET status=?,completed_at=? WHERE id=?",
                ("passed" if passed else "completed", at if passed else None, i),
            )
        proposal_features.enqueue(c, u["email"], a["source"])
        audit(c, u["email"], "quiz_pass" if passed else "quiz_retry", i)
    return {
        "score": score,
        "passed": passed,
        "status": "passed" if passed or a["status"] == "passed" else "completed",
        "feedback": [
            "Correct" if p.answers[j] == q[2] else "Review: " + q[1][q[2]]
            for j, q in enumerate(qq)
        ],
    }


class QuizQuestionInput(Strict):
    category: str = Field(min_length=1, max_length=100)
    prompt: str = Field(min_length=5, max_length=1000)
    options: list[str] = Field(min_length=2, max_length=4)
    correct_index: int = Field(ge=0, le=3)


def _clean_quiz_question(p: QuizQuestionInput):
    category = p.category.strip()
    if category not in CATEGORIES:
        raise HTTPException(422, "Choose a supported quiz category")
    prompt = p.prompt.strip()
    options = [str(x).strip() for x in p.options]
    if any(not x or len(x) > 500 for x in options):
        raise HTTPException(422, "Quiz options must be 1 to 500 characters")
    if len(set(x.casefold() for x in options)) != len(options):
        raise HTTPException(422, "Quiz options must be distinct")
    if p.correct_index >= len(options):
        raise HTTPException(422, "Correct answer does not match an option")
    return category, prompt, options, p.correct_index


@app.get("/admin/quizzes")
def admin_quizzes(category: str = "", u=Depends(admin)):
    if category and category not in CATEGORIES:
        raise HTTPException(422, "Choose a supported quiz category")
    with db() as c:
        rows = c.execute(
            "SELECT id,category,prompt,options_json,correct_index,sort_order FROM quiz_questions "
            + ("WHERE category=? " if category else "")
            + "ORDER BY category,sort_order,id",
            (category,) if category else (),
        ).fetchall()
    items = []
    for row in rows:
        item = dict(row)
        item["options"] = json.loads(item.pop("options_json"))
        items.append(item)
    return {
        "categories": CATEGORIES,
        "selected_category": category or CATEGORIES[0],
        "questions": items,
        "pass_percent": 80,
        "notice": "Quiz questions are server graded. Changes apply to subsequent submissions; saved historical attempt scores are not recalculated.",
    }


@app.post("/admin/quizzes/questions")
def create_quiz_question(p: QuizQuestionInput, u=Depends(admin)):
    category, prompt, options, correct_index = _clean_quiz_question(p)
    with db() as c:
        order = c.execute(
            "SELECT COALESCE(MAX(sort_order),-1)+1 FROM quiz_questions WHERE category=?",
            (category,),
        ).fetchone()[0]
        cur = c.execute(
            "INSERT INTO quiz_questions(category,prompt,options_json,correct_index,sort_order) VALUES(?,?,?,?,?)",
            (category, prompt, json.dumps(options), correct_index, order),
        )
        audit(c, u["email"], "quiz_question_created", cur.lastrowid)
        question_id = cur.lastrowid
    return {"status": "created", "id": question_id}


@app.patch("/admin/quizzes/questions/{question_id}")
def update_quiz_question(question_id: int, p: QuizQuestionInput, u=Depends(admin)):
    category, prompt, options, correct_index = _clean_quiz_question(p)
    with db() as c:
        existing = c.execute("SELECT * FROM quiz_questions WHERE id=?", (question_id,)).fetchone()
        if not existing:
            raise HTTPException(404, "Quiz question not found")
        order = existing["sort_order"]
        if existing["category"] != category:
            order = c.execute(
                "SELECT COALESCE(MAX(sort_order),-1)+1 FROM quiz_questions WHERE category=?",
                (category,),
            ).fetchone()[0]
        c.execute(
            "UPDATE quiz_questions SET category=?,prompt=?,options_json=?,correct_index=?,sort_order=? WHERE id=?",
            (category, prompt, json.dumps(options), correct_index, order, question_id),
        )
        audit(c, u["email"], "quiz_question_updated", question_id)
    return {"status": "updated", "id": question_id}


@app.delete("/admin/quizzes/questions/{question_id}")
def delete_quiz_question(question_id: int, u=Depends(admin)):
    with db() as c:
        row = c.execute("SELECT category FROM quiz_questions WHERE id=?", (question_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Quiz question not found")
        c.execute("DELETE FROM quiz_questions WHERE id=?", (question_id,))
        audit(c, u["email"], "quiz_question_deleted", question_id)
    return {"status": "deleted", "id": question_id}


@app.delete("/admin/quizzes/{category}")
def clear_quiz(category: str, u=Depends(admin)):
    if category not in CATEGORIES:
        raise HTTPException(422, "Choose a supported quiz category")
    with db() as c:
        count = c.execute("SELECT COUNT(*) FROM quiz_questions WHERE category=?", (category,)).fetchone()[0]
        c.execute("DELETE FROM quiz_questions WHERE category=?", (category,))
        audit(c, u["email"], "quiz_cleared", category)
    return {"status": "cleared", "category": category, "deleted": count}


class Reflection(Strict):
    campaign_id: str
    reason: Literal[
        "urgency", "familiar_sender", "work_relevance", "reward", "uncertainty", "other"
    ]


@app.post("/reflections")
def reflect(p: Reflection, u=Depends(current_user)):
    with db() as c:
        if not c.execute(
            "SELECT 1 FROM recipients WHERE campaign_id=? AND email=?",
            (p.campaign_id, u["email"]),
        ).fetchone():
            raise HTTPException(403, "Campaign not assigned to you")
        c.execute(
            "INSERT INTO reflections VALUES(NULL,?,?,?,?) ON CONFLICT(email,campaign_id) DO UPDATE SET reason=excluded.reason,at=excluded.at",
            (u["email"], p.campaign_id, p.reason, now()),
        )
    return {"status": "saved", "kind": "self_reported_reason"}


class QueueUpdate(Strict):
    owner: str = Field(min_length=1, max_length=100)
    due_at: str


@app.post("/admin/assignments/{i}")
def update_queue(i: int, p: QueueUpdate, u=Depends(admin)):
    due = date(p.due_at).isoformat()
    with db() as c:
        if not c.execute("SELECT 1 FROM assignments WHERE id=?", (i,)).fetchone():
            raise HTTPException(404, "Assignment not found")
        c.execute(
            "UPDATE assignments SET owner=?,due_at=? WHERE id=?", (p.owner, due, i)
        )
        audit(c, u["email"], "assignment_owner_due", i)
    return {"status": "updated"}


@app.get("/admin/reflections")
def reflections(
    source: str = "practice",
    department: str = "",
    campaign: str = "",
    category: str = "",
    difficulty: str = "",
    start: str = "",
    end: str = "",
    u=Depends(admin),
):
    with db() as c:
        selected = {
            (x["email"], x["campaign_id"])
            for x in filtered(
                c, source, department, campaign, category, difficulty, start, end
            )
        }
        groups = {}
        for r in c.execute("SELECT email,campaign_id,reason FROM reflections"):
            if (r["email"], r["campaign_id"]) in selected:
                key = (r["campaign_id"], r["reason"])
                groups[key] = groups.get(key, 0) + 1
        return {
            "kind": "Self-reported explanations; not inferred causes",
            "items": [
                {"campaign_id": k[0], "reason": k[1], "responses": v}
                for k, v in sorted(groups.items())
            ],
        }


@app.post("/admin/ai/{target}")
def ai_enrichment(target: str, source: str = "live", u=Depends(admin)):
    target = email(target)
    if source not in ("practice", "live"):
        raise HTTPException(422, "Invalid source")
    key = os.getenv("GROQ_API_KEY", "")
    model = os.getenv("GROQ_MODEL", "")
    with db() as c:
        if not c.execute("SELECT 1 FROM users WHERE email=?", (target,)).fetchone():
            raise HTTPException(404, "Profile not found")
        evidence = {
            source: profile_assessment(
                c, target, [x for x in outcomes(c, target) if x["source"] == source]
            )
        }
    status = "unavailable"
    content = "AI is not configured. Add GROQ_API_KEY and GROQ_MODEL to .env."
    if key and model:
        try:
            response = proposal_features.generate_text(
                model,
                "Summarize ONLY supplied aggregated simulation evidence in simple English in at most 100 words. Do not infer personality, diagnosis, motives, compromise probability or causation. Missing outcomes are uncertain. Suggest one learning action. Do not generate scores. Evidence: "
                + json.dumps(evidence),
            )
            text = (response.text or "").strip()
            if not text or len(text) > 2500:
                raise ValueError("Empty or oversized AI summary")
            content = text
            status = "available"
        except Exception as exc:
            content = "AI summary unavailable. " + proposal_features._safe_ai_error(exc)
    with db() as c:
        c.execute(
            "INSERT INTO ai_notes(email,at,status,content,source) VALUES(?,?,?,?,?) ON CONFLICT(email) DO UPDATE SET at=excluded.at,status=excluded.status,content=excluded.content,source=excluded.source",
            (target, now(), status, content, source),
        )
        audit(c, u["email"], "ai_summary_" + status, target)
    return {"status": status, "content": content, "score_source": "ai"}


@app.get("/admin/export.csv")
def export(
    source: str = "practice",
    department: str = "",
    campaign: str = "",
    category: str = "",
    difficulty: str = "",
    start: str = "",
    end: str = "",
    u=Depends(admin),
):
    with db() as c:
        oo = filtered(c, source, department, campaign, category, difficulty, start, end)
        audit(c, u["email"], "csv_export", source)
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(
        [
            "Source",
            "Campaign",
            "Department",
            "Participant",
            "Difficulty",
            "Sent",
            "Interaction",
            "Test form",
            "Reported",
            "Journey",
        ]
    )

    def safe(v):
        s = str(v)
        return "'" + s if s.lstrip().startswith(("=", "+", "-", "@")) else s

    for x in oo:
        w.writerow(
            [
                safe(v)
                for v in [
                    x["source"],
                    x["name"],
                    x["department"],
                    x["email"],
                    x["difficulty"],
                    x["sent"],
                    x["clicked"],
                    x["submitted"],
                    x["reported"],
                    x["journey"],
                ]
            ]
        )
    return Response(
        out.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="securesense_evidence.csv"'
        },
    )


@app.get("/health")
def health():
    return {"status": "ok", "version": VERSION}


@app.get("/")
def home():
    return RedirectResponse("/app/login.html")


app.mount(
    "/app",
    StaticFiles(directory=ROOT / "Member3" / "frontend", html=True),
    name="app",
)


class GophishSync(Strict):
    campaign: Campaign
    departments: dict[str, str] = Field(default_factory=dict)


@app.post("/admin/gophish/sync")
def gophish_sync(p: GophishSync, u=Depends(admin)):
    """Fetch campaign results and normalize native timeline with explicit campaign context."""
    from urllib.parse import urlsplit, quote

    base = os.getenv("GOPHISH_ADMIN_URL", "https://127.0.0.1:3333").rstrip("/")
    api_key = os.getenv("GOPHISH_API_KEY", "")
    parsed = urlsplit(base)
    if (
        parsed.scheme != "https"
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise HTTPException(
            503, "Configure an HTTPS Gophish admin URL without embedded credentials"
        )
    if not api_key:
        raise HTTPException(503, "Gophish API key is not configured")
    if p.campaign.source != "live":
        raise HTTPException(422, "Gophish imports must use live source")
    ca = os.getenv("GOPHISH_CA_BUNDLE", "")
    try:
        import ssl

        verify = ssl.create_default_context(cafile=ca) if ca else True
        with httpx.Client(
            verify=verify, timeout=15, follow_redirects=False, trust_env=False
        ) as client:
            r = client.get(
                base + "/api/campaigns/" + quote(p.campaign.id, safe=""),
                headers={"Authorization": "Bearer " + api_key},
            )
            r.raise_for_status()
            native = r.json()
    except Exception:
        raise HTTPException(
            502,
            "Gophish fetch failed. Check URL, API key and trusted certificate configuration.",
        )
    if (
        not isinstance(native, dict)
        or str(native.get("id")) != p.campaign.id
        or not isinstance(native.get("results"), list)
        or not isinstance(native.get("timeline"), list)
    ):
        raise HTTPException(422, "Unexpected Gophish campaign format")
    recorded = duplicates = rejected = 0
    with db() as c:
        existing = c.execute(
            "SELECT * FROM campaigns WHERE id=?", (p.campaign.id,)
        ).fetchone()
        if existing and existing["source"] != "live":
            raise HTTPException(409, "Campaign id conflicts with practice source")
        if not existing:
            add_campaign(c, p.campaign)
        for person in native["results"]:
            e = email(person.get("email", ""))
            rid = str(person.get("id", ""))
            if not rid:
                raise HTTPException(422, "Gophish recipient tracking id missing")
            name = (
                " ".join(
                    str(person.get(k, "")).strip() for k in ["first_name", "last_name"]
                ).strip()
                or "Participant"
            )
            department = p.departments.get(e, "Unassigned")
            c.execute(
                "INSERT OR IGNORE INTO users VALUES(?,?,?,?,?)",
                (
                    e,
                    name[:100],
                    department[:100],
                    "employee",
                    password_hash(secrets.token_urlsafe(32)),
                ),
            )
            old = c.execute(
                "SELECT rid FROM recipients WHERE campaign_id=? AND email=?",
                (p.campaign.id, e),
            ).fetchone()
            if old and old["rid"] != rid:
                raise HTTPException(
                    409, "Recipient tracking id changed; review campaign mapping"
                )
            c.execute(
                "INSERT OR IGNORE INTO recipients VALUES(?,?,?)",
                (p.campaign.id, e, rid),
            )
        for event in native["timeline"]:
            if not isinstance(event, dict):
                rejected += 1
                continue
            try:
                result = record_event(c, event, p.campaign.id)
                if result["status"] == "duplicate":
                    duplicates += 1
                else:
                    recorded += 1
            except HTTPException as exc:
                rejected += 1
                c.execute(
                    "INSERT INTO quarantine(received_at,reason,campaign_id) VALUES(?,?,?)",
                    (now(), str(exc.detail), p.campaign.id),
                )
        audit(c, u["email"], "gophish_sync", p.campaign.id)
    return {
        "status": "synced",
        "recorded": recorded,
        "duplicates": duplicates,
        "rejected": rejected,
    }


@app.get("/docs", include_in_schema=False)
def api_console():
    return RedirectResponse("/app/settings.html")


@app.get("/admin/status")
def integration_status(u=Depends(admin)):
    return {
        "webhook_configured": bool(os.getenv("GOPHISH_WEBHOOK_SECRET")),
        "gophish_api_configured": bool(os.getenv("GOPHISH_API_KEY")),
        "ai_configured": bool(
            os.getenv("GROQ_API_KEY") and os.getenv("GROQ_MODEL")
        ),
        "database": "SQLite local prototype",
        "schema_version": VERSION,
    }


import proposal_features

proposal_features.setup(__import__(__name__))

class PhishingReport(Strict):
    rid: str = Field(min_length=1, max_length=256)
    reason: str = Field(min_length=5, max_length=500)


@app.get('/reports/options')
def report_options(u=Depends(current_user)):
    with db() as c:
        return {'messages': [dict(x) for x in c.execute('SELECT r.rid,ca.name,ca.id AS campaign_id FROM recipients r JOIN campaigns ca ON ca.id=r.campaign_id WHERE r.email=? ORDER BY ca.launched_at DESC', (u['email'],))]}


@app.post('/reports/phishing')
def phishing_report(p: PhishingReport, u=Depends(current_user)):
    with db() as c:
        rows=c.execute('SELECT r.campaign_id,ca.source FROM recipients r JOIN campaigns ca ON ca.id=r.campaign_id WHERE r.rid=? AND r.email=?',(p.rid,u['email'])).fetchall()
        if len(rows)!=1:
            raise HTTPException(422,'This email does not belong to the signed-in account or the tracking ID is ambiguous.')
        cid=rows[0]['campaign_id']
        source=rows[0]['source']
    if source == 'live':
        try:
            report_to_gophish(p.rid)
        except (httpx.HTTPError, ValueError):
            raise HTTPException(502, 'Gophish could not record the report. Please try again.')
    with db() as c:
        if c.execute("SELECT 1 FROM events WHERE campaign_id=? AND email=? AND action='reported'",(cid,u['email'])).fetchone():
            return {'status':'already_reported','campaign_id':cid}
        result=record_event(c,{'email':u['email'],'rid':p.rid,'message':'Email Reported','time':now()},cid)
        c.execute('INSERT INTO participant_reports VALUES(?,?,?,?)',(cid,u['email'],p.reason,now()))
        audit(c,u['email'],'participant_phishing_report',cid)
        # Reporting is deliberate authenticated user input; no supplied event timestamps or identity.
        return result


@app.get('/admin/campaign-results')
def campaign_results(source: str='live',department: str='',campaign: str='',category: str='',difficulty: str='',start: str='',end: str='',u=Depends(admin)):
    with db() as c:
        rows=filtered(c,source,department,campaign,category,difficulty,start,end)
        results=[]
        for x in rows:
            a=c.execute('SELECT id,status FROM assignments WHERE email=? AND campaign_id=?',(x['email'],x['campaign_id'])).fetchone()
            attempts=c.execute('SELECT q.score,q.passed,q.at FROM quiz_attempts q JOIN assignments a ON a.id=q.assignment_id WHERE a.email=? AND a.campaign_id=? ORDER BY q.id DESC',(x['email'],x['campaign_id'])).fetchall()
            latest=attempts[0] if attempts else None
            results.append({'name':x['user_name'],'email':x['email'],'department':x['department'],'campaign':x['name'],'category':x['category'],'clicked':x['clicked'],'submitted':x['submitted'],'reported':x['reported'],'quiz_completed':bool(attempts),'quiz_result':('Passed' if latest['passed'] else 'Failed') if latest else 'Not attempted','quiz_score':latest['score'] if latest else None,'ever_passed': bool(a and a['status']=='passed'),'attempts':len(attempts),'events':[{'action':e['action'],'at':e['occurred_at']} for e in x['events'] if e['quality']=='human']})
        departments=[]
        for dep in sorted({x['department'] for x in results}):
            rr=[x for x in results if x['department']==dep]
            departments.append({'department':dep,'participants':len({x['email'] for x in rr}),'observations':len(rr),'clicked':sum(x['clicked'] for x in rr),'submitted':sum(x['submitted'] for x in rr),'reported':sum(x['reported'] for x in rr),'completed':sum(x['quiz_completed'] for x in rr),'passed':sum(x['quiz_result']=='Passed' for x in rr),'failed':sum(x['quiz_result']=='Failed' for x in rr)})
        return {'results':results,'departments':departments,'notice':'Counts represent participant-campaign observations. Quiz results show the latest attempt; earlier passes remain in learning history. Password values are never collected.'}
