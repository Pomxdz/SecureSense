"""Automatic AI jobs, authenticated learning handoff and audit evidence."""

import hashlib, json, math, os, secrets, threading, re, time
from datetime import timedelta
from typing import Literal
from urllib.parse import urlencode, urlsplit
from fastapi import Depends, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict, Field

M = None
STOP = threading.Event()
WORKER = None


def setup(m):
    global M
    M = m
    setup_schema(m)
    from contextlib import asynccontextmanager

    original = m.app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(app):
        async with original(app):
            start()
            try:
                yield
            finally:
                shutdown()

    m.app.router.lifespan_context = lifespan
    install_routes(m)


def setup_schema(m):
    with m.db() as c:
        c.executescript("""
CREATE TABLE IF NOT EXISTS ai_jobs(id INTEGER PRIMARY KEY,email TEXT REFERENCES users(email),source TEXT,fingerprint TEXT,created_at TEXT,status TEXT,model TEXT,score REAL,explanation TEXT,recommendation TEXT,input_json TEXT,error TEXT,attempts INTEGER DEFAULT 0,next_at TEXT,finished_at TEXT,UNIQUE(email,source,fingerprint,model));
CREATE TABLE IF NOT EXISTS handoff_tokens(token_hash TEXT PRIMARY KEY,campaign_id TEXT REFERENCES campaigns(id),expires TEXT);
CREATE TABLE IF NOT EXISTS grc_controls(id TEXT PRIMARY KEY,requirement TEXT,owner TEXT,review_due TEXT);
""")
        if "trigger" not in [
            row[1] for row in c.execute("PRAGMA table_info(handoff_tokens)")
        ]:
            c.execute(
                "ALTER TABLE handoff_tokens ADD COLUMN trigger TEXT DEFAULT 'test_form_submission'"
            )
        for i, requirement in [
            ("AW-01", "Maintain authorized awareness simulation evidence"),
            ("AW-02", "Deliver and verify relevant awareness learning"),
            ("AW-03", "Review learning effectiveness and follow up"),
            ("AW-04", "Review telemetry privacy and data quality"),
        ]:
            c.execute(
                "INSERT OR IGNORE INTO grc_controls VALUES(?,?,?,?)",
                (
                    i,
                    requirement,
                    "InfoSec",
                    (m.datetime.now(m.timezone.utc) + timedelta(days=30)).isoformat(),
                ),
            )


def evidence(c, email, source):
    observations = [x for x in M.outcomes(c, email) if x["source"] == source]
    assessment = M.profile_assessment(c, email, observations)
    # Per-campaign remedial training status, keyed by campaign_id, so each
    # observation below can say whether the follow-up quiz was passed.
    training = {
        row["campaign_id"]: bool(
            c.execute(
                "SELECT 1 FROM quiz_attempts WHERE assignment_id=? AND passed=1",
                (row["id"],),
            ).fetchone()
        )
        for row in c.execute(
            "SELECT id,campaign_id FROM assignments WHERE email=? AND source=?",
            (email, source),
        )
    }
    # Names, email, tracking IDs, form values, IPs and user agents never leave this service.
    return {
        "source": source,
        "coverage": assessment["coverage"],
        "assessable_outcomes": assessment["assessed_outcomes"],
        "observations": [
            {
                "category": x["category"],
                "difficulty": x["difficulty"],
                "sent": x["sent"],
                "journey": x["journey"],
                "clicked": bool(x["clicked"]),
                "submitted_test_form": bool(x["submitted"]),
                "reported": bool(x["reported"]),
                "time_to_click_seconds": x["time_to_click"],
                "time_to_report_seconds": x["time_to_report"],
                "remedial_training_passed": training.get(x["campaign_id"], False),
            }
            for x in observations
        ],
    }


def enqueue(c, email, source, retry=False):
    payload = evidence(c, email, source)
    raw = json.dumps(payload, sort_keys=True)
    digest = hashlib.sha256(raw.encode()).hexdigest()
    model = os.getenv("GROQ_MODEL", "")
    ready = bool(model and os.getenv("GROQ_API_KEY"))
    status = (
        "pending"
        if ready and payload["assessable_outcomes"]
        else "unassessed" if not payload["assessable_outcomes"] else "unavailable"
    )
    c.execute(
        "UPDATE ai_jobs SET status='superseded' WHERE email=? AND source=? AND status='pending' AND (fingerprint!=? OR model!=?)",
        (email, source, digest, model),
    )
    c.execute(
        "INSERT OR IGNORE INTO ai_jobs(email,source,fingerprint,created_at,status,model,input_json,next_at,error) VALUES(?,?,?,?,?,?,?,?,?)",
        (
            email,
            source,
            digest,
            M.now(),
            status,
            model,
            raw,
            M.now(),
            None if ready else "Configure GROQ_API_KEY and GROQ_MODEL",
        ),
    )
    if ready and payload["assessable_outcomes"]:
        states = ("unavailable", "failed") if retry else ("unavailable",)
        for state in states:
            c.execute(
                "UPDATE ai_jobs SET status='pending',error=NULL,next_at=? WHERE email=? AND source=? AND fingerprint=? AND model=? AND status=?",
                (M.now(), email, source, digest, model, state),
            )
    return digest


def _client():
    from groq import Groq

    return Groq(
        api_key=os.environ["GROQ_API_KEY"],
        timeout=15.0,
    )


class _TextResult:
    """Thin wrapper so callers can keep reading `result.text`, as they did
    with the provider response object."""

    def __init__(self, text):
        self.text = text


def generate_text(model, contents, config=None):
    """Single gateway for every Groq request made by SecureSense.

    There is no application-side throttle: calls are made as soon as they are
    needed. Any quota that still applies is enforced by the Groq API key itself.

    `config` is an optional dict of extra kwargs for the chat completion call
    (e.g. {"temperature": 0, "response_format": {"type": "json_object"}}).
    """
    client = _client()
    kwargs = {
        "model": model,
        "messages": [{"role": "user", "content": contents}],
    }
    if config:
        kwargs.update(config)
    response = client.chat.completions.create(**kwargs)
    return _TextResult(response.choices[0].message.content)


def generate(payload, model):
    r = generate_text(
        model,
        "Evaluate only this anonymized simulation history. Return a JSON object with score (number 0..100 where 0 is the lowest and 100 the highest human phishing risk), explanation (plain text <=1000 characters), and recommendation (one of "
        + ", ".join(M.CATEGORIES)
        + "). You are the only source of this score; no rule-based score is supplied. The score is an AI risk estimate, never a compromise probability, personality inference or diagnosis. Missing observations are uncertain. Consider the type of interaction (a test-form submission is more serious than a click), repeated interaction, reporting chronology, context and timing without assuming fast actions prove intent. Do not claim causation. An observation's remedial_training_passed field means the person has since completed and passed the follow-up training quiz for that specific simulation; treat that as a genuine protective, risk-lowering factor for that observation, weighed alongside everything else, without assuming it guarantees future behavior or erases the original interaction entirely. Evidence: "
        + json.dumps(payload),
        {"response_format": {"type": "json_object"}, "temperature": 0},
    )
    return json.loads(r.text)


def _safe_ai_error(exc):
    """Return a useful provider error without exposing configured secrets."""
    text = str(exc).strip() or exc.__class__.__name__
    key = os.getenv("GROQ_API_KEY", "")
    if key:
        text = text.replace(key, "[redacted]")
    text = re.sub(r"key=[^&\s]+", "key=[redacted]", text, flags=re.I)
    text = re.sub(r"api[_-]?key[=: ]+[^,;\s]+", "api_key=[redacted]", text, flags=re.I)
    return f"{exc.__class__.__name__}: {text}"[:500]


def process_one():
    with M.db() as c:
        job = c.execute(
            "SELECT * FROM ai_jobs WHERE status='pending' AND next_at<=? ORDER BY next_at,id LIMIT 1",
            (M.now(),),
        ).fetchone()
        if not job:
            return False
        c.execute(
            "UPDATE ai_jobs SET status='running',attempts=attempts+1,error=NULL WHERE id=?",
            (job["id"],),
        )
    try:
        result = generate(json.loads(job["input_json"]), job["model"])
        if not isinstance(result, dict):
            raise ValueError("object expected")
        score = result.get("score")
        explanation = result.get("explanation")
        recommendation = result.get("recommendation")
        if (
            isinstance(score, bool)
            or not isinstance(score, (int, float))
            or not math.isfinite(score)
            or not 0 <= score <= 100
        ):
            raise ValueError("score invalid")
        if (
            not isinstance(explanation, str)
            or not explanation.strip()
            or len(explanation) > 1000
            or recommendation not in M.CATEGORIES
        ):
            raise ValueError("explanation invalid")
        with M.db() as c:
            c.execute(
                "UPDATE ai_jobs SET status='available',score=?,explanation=?,recommendation=?,finished_at=?,error=NULL,next_at=? WHERE id=?",
                (round(score, 1), explanation, recommendation, M.now(), M.now(), job["id"]),
            )
            M.audit(c, "system", "ai_assessment_available", job["id"])
    except Exception as exc:
        attempt = job["attempts"] + 1
        diagnostic = "AI service unavailable or response invalid. " + _safe_ai_error(exc)
        retry = attempt < 3
        next_at = (M.datetime.now(M.timezone.utc) + timedelta(seconds=10 * attempt)).isoformat()
        with M.db() as c:
            c.execute(
                "UPDATE ai_jobs SET status=?,error=?,next_at=?,finished_at=? WHERE id=?",
                ("pending" if retry else "failed", diagnostic, next_at, None if retry else M.now(), job["id"]),
            )
            M.audit(c, "system", "ai_assessment_retry" if retry else "ai_assessment_failed", job["id"])
    return True


def worker_loop():
    while not STOP.is_set():
        busy = False
        try:
            busy = process_one()
        except Exception:
            pass
        if not busy:
            STOP.wait(2)


def start():
    global WORKER
    with M.db() as c:
        c.execute("UPDATE ai_jobs SET status='pending' WHERE status='running'")
        # Jobs parked by the old throttled version run again straight away.
        c.execute(
            "UPDATE ai_jobs SET status='pending',error=NULL,next_at=?,finished_at=NULL WHERE status='rate_limited' OR (status='failed' AND (error LIKE '%429%' OR error LIKE '%RESOURCE_EXHAUSTED%'))",
            (M.now(),),
        )
        for row in c.execute(
            "SELECT DISTINCT email,source FROM recipients JOIN campaigns ON campaigns.id=recipients.campaign_id"
        ).fetchall():
            enqueue(c, row["email"], row["source"])
    STOP.clear()
    WORKER = threading.Thread(target=worker_loop, daemon=True)
    WORKER.start()


def shutdown():
    STOP.set()
    if WORKER:
        WORKER.join(timeout=1)


def latest(c, email, source):
    current = evidence(c, email, source)
    digest = hashlib.sha256(json.dumps(current, sort_keys=True).encode()).hexdigest()
    row = c.execute(
        "SELECT id,source,status,model,score,explanation,recommendation,created_at,finished_at,next_at,fingerprint,error,attempts FROM ai_jobs WHERE email=? AND source=? ORDER BY id DESC LIMIT 1",
        (email, source),
    ).fetchone()
    if not row:
        return {"source": source, "status": "not_requested", "score": None}
    data = dict(row)
    data["stale"] = data["fingerprint"] != digest
    if data["stale"]:
        data["score"] = None
    return data


class BridgeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    campaign_id: str = Field(min_length=1, max_length=100)
    public_base: str = Field(default="http://127.0.0.1:8000", max_length=200)
    trigger: Literal["clicked", "test_form_submission"] = "test_form_submission"


class HandoffRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ticket: str = Field(min_length=20, max_length=200)
    rid: str = Field(min_length=1, max_length=200)


class ControlUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    owner: str = Field(min_length=1, max_length=100)
    review_due: str


def validate_ticket(c, ticket):
    row = c.execute(
        "SELECT * FROM handoff_tokens WHERE token_hash=?",
        (hashlib.sha256(ticket.encode()).hexdigest(),),
    ).fetchone()
    if not row or M.date(row["expires"]) <= M.datetime.now(M.timezone.utc):
        raise HTTPException(
            410, "Learning link expired or invalid; request a new campaign bridge"
        )
    return row


def install_routes(m):
    @m.app.get("/ai/assessments/{target}")
    def assessments(target: str, u=Depends(m.current_user)):
        target = m.email(target)
        m.authorize(u, target)
        with m.db() as c:
            return {s: latest(c, target, s) for s in ["practice", "live"]}

    @m.app.post("/admin/ai/assessments/{target}")
    def request_assessment(target: str, source: str = "", u=Depends(m.admin)):
        target = m.email(target)
        if source and source not in ("practice", "live"):
            raise HTTPException(422, "Invalid source")
        requested_sources = [source] if source else ["practice", "live"]
        with m.db() as c:
            if not c.execute("SELECT 1 FROM users WHERE email=?", (target,)).fetchone():
                raise HTTPException(404, "Participant missing")
            for requested_source in requested_sources:
                enqueue(c, target, requested_source, retry=True)
            m.audit(c, u["email"], "ai_assessment_requested", f"{target}:{source or 'all'}")
            return {s: latest(c, target, s) for s in requested_sources}

    @m.app.get("/admin/ai/overview")
    def overview(source: str = "practice", u=Depends(m.admin)):
        if source not in ("practice", "live"):
            raise HTTPException(422, "Invalid source")
        with m.db() as c:
            participants = c.execute(
                """SELECT DISTINCT u.email,u.name
                   FROM users u
                   JOIN recipients r ON r.email=u.email
                   JOIN campaigns ca ON ca.id=r.campaign_id
                   WHERE u.role='employee' AND ca.source=?
                   ORDER BY u.name""",
                (source,),
            ).fetchall()
            rows = []
            for r in participants:
                assessment = latest(c, r["email"], source)
                facts = m.profile_assessment(
                    c, r["email"],
                    [x for x in m.outcomes(c, r["email"]) if x["source"] == source],
                )
                note = c.execute(
                    "SELECT at,status,content,source FROM ai_notes WHERE email=?",
                    (r["email"],),
                ).fetchone()
                if note and note["source"] not in (source, "all"):
                    note = None
                rows.append({
                    "email": r["email"],
                    "name": r["name"],
                    **assessment,
                    "assessable_outcomes": facts["assessed_outcomes"],
                    "campaigns": facts["campaigns"],
                    "interactions": facts["interactions"],
                    "submissions": facts["submissions"],
                    "reports": facts["protective_reports"] + facts["recovery_reports"],
                    "ai_summary": note["content"] if note else None,
                    "ai_summary_status": note["status"] if note else "not_requested",
                    "ai_summary_at": note["at"] if note else None,
                })
        scores = [
            r["score"]
            for r in rows
            if r["status"] == "available" and r["score"] is not None
        ]
        return {
            "source": source,
            "configured": bool(os.getenv("GROQ_API_KEY") and os.getenv("GROQ_MODEL")),
            "configured_model": os.getenv("GROQ_MODEL", ""),
            "scope": "Participants with recipient records in the selected source; independent of the other dashboard filters",
            "mean": round(sum(scores) / len(scores), 1) if scores else None,
            "assessed": len(scores),
            "people": rows,
            "notice": "Risk scores are generated by AI only (0 = lowest risk, 100 = highest). They are experimental estimates, not calibrated compromise probabilities. A score is produced once a person has at least one assessable observed outcome: a verified click, test-form submission or report.",
        }

    @m.app.post("/admin/learning/bridge")
    def bridge(p: BridgeRequest, u=Depends(m.admin)):
        parsed = urlsplit(p.public_base)
        if (
            parsed.scheme not in ("http", "https")
            or not parsed.netloc
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.path not in ("", "/")
            or (
                parsed.scheme == "http"
                and parsed.hostname not in ("127.0.0.1", "localhost")
            )
        ):
            raise HTTPException(
                422, "Use HTTPS or local loopback HTTP application origin"
            )
        with m.db() as c:
            ca = c.execute(
                "SELECT * FROM campaigns WHERE id=?", (p.campaign_id,)
            ).fetchone()
            if not ca:
                raise HTTPException(
                    404, "Synchronize campaign first to establish recipient mappings"
                )
            ticket = secrets.token_urlsafe(32)
            expires = (m.datetime.now(m.timezone.utc) + timedelta(days=7)).isoformat()
            c.execute(
                "INSERT INTO handoff_tokens(token_hash,campaign_id,expires,trigger) VALUES(?,?,?,?)",
                (
                    hashlib.sha256(ticket.encode()).hexdigest(),
                    ca["id"],
                    expires,
                    p.trigger,
                ),
            )
            m.audit(c, u["email"], "learning_bridge_created", ca["id"])
        from pathlib import Path

        landing_files = {
            "Credential Harvesting": "credential-harvesting",
            "Financial Fraud": "financial-fraud",
            "Social Engineering": "social-engineering",
            "Urgent Extortion": "urgent-extortion",
            "Malware Delivery": "malware-delivery",
        }
        slug = landing_files.get(ca["category"])
        root = Path(__file__).resolve().parent.parent / "Member1"
        page_path = root / "viva_landings" / (slug + ".html") if slug else root / "shieldpay_landing_page.html"
        template = page_path.read_text(encoding="utf-8")
        banner = """<style>
#learningBanner{position:fixed;inset:0;z-index:2147483000;display:flex;align-items:center;justify-content:center;padding:20px;background:rgba(58,79,100,.72);-webkit-backdrop-filter:blur(7px);backdrop-filter:blur(7px);font:15px/1.55 Inter,system-ui,-apple-system,'Segoe UI',Roboto,Arial,sans-serif;animation:ssFade .25s ease-out}
#learningBanner[hidden]{display:none}
#learningBanner .ss-card{position:relative;overflow:hidden;width:100%;max-width:420px;color:#0f213d;border-radius:22px;padding:34px 32px 26px;text-align:center;background:#f7fbff;box-shadow:0 30px 80px rgba(20,35,55,.45)}
#learningBanner .ss-card:before,#learningBanner .ss-card:after{content:"";position:absolute;border-radius:50%;pointer-events:none}
#learningBanner .ss-card:before{right:-120px;top:-150px;width:270px;height:270px;background:rgba(190,228,252,.55)}
#learningBanner .ss-card:after{right:-150px;top:-185px;width:270px;height:270px;background:rgba(150,208,250,.75)}
#learningBanner .ss-card>*{position:relative;z-index:1}
#learningBanner .ss-icon{display:block;width:84px;height:84px;margin:0 auto 6px}
#learningBanner .ss-warning{margin:0 0 2px;color:#cc2a26;font-size:34px;font-weight:800;letter-spacing:-1px;line-height:1.15}
#learningBanner .ss-title{margin:0 0 10px;color:#0e2240;font-size:19px;font-weight:800;letter-spacing:-.4px}
#learningBanner .ss-message{margin:0 0 22px;color:#4d6285;font-size:15px;line-height:1.6}
#learningBanner .ss-cta{display:block;width:100%;padding:14px 18px;border-radius:12px;background:#c3e5fc;color:#0b4a70;font-size:16px;font-weight:800;text-decoration:none;text-align:center;box-sizing:border-box;border:2px solid #fff;box-shadow:0 0 0 2px #9fd0f2,0 8px 22px rgba(80,160,225,.28)}
#learningBanner .ss-cta:hover{background:#b4dcf8}
#learningBanner .ss-cta:focus-visible{outline:3px solid #0e2240;outline-offset:4px}
#learningBanner .ss-note{margin:12px 0 0;color:#5b7088;font-size:12.5px}
@keyframes ssFade{from{opacity:0}to{opacity:1}}
@media(prefers-reduced-motion:reduce){#learningBanner{animation:none}}
@media(max-width:480px){#learningBanner .ss-card{padding:28px 20px 22px}#learningBanner .ss-warning{font-size:30px}#learningBanner .ss-title{font-size:18px}#learningBanner .ss-message{font-size:14.5px}}
</style><div id="learningBanner" role="alertdialog" aria-modal="true" aria-labelledby="learningWarning" aria-describedby="learningMessage" hidden>
<div class="ss-card">
<svg class="ss-icon" viewBox="0 0 120 120" role="img" aria-label="Warning: email alert" xmlns="http://www.w3.org/2000/svg"><defs><radialGradient id="ssGlow" cx="50%" cy="50%" r="50%"><stop offset="0" stop-color="#fbc8c5"/><stop offset="1" stop-color="#fde3e1"/></radialGradient></defs><circle cx="58" cy="66" r="48" fill="url(#ssGlow)"/><path d="M14 30l-8-5M22 20l-4-8" stroke="#d92d20" stroke-width="3.5" stroke-linecap="round"/><rect x="30" y="38" width="56" height="34" rx="3" fill="#fff"/><path d="M38 47h40M38 54h40M38 61h24" stroke="#c9d3dd" stroke-width="3" stroke-linecap="round"/><path d="M25 52l33 22 33-22v28a7 7 0 0 1-7 7H32a7 7 0 0 1-7-7z" fill="#f3a42e"/><path d="M25 52l33 22 33-22" fill="none" stroke="#fbc767" stroke-width="2.5" stroke-linejoin="round"/><circle cx="92" cy="30" r="15" fill="#d92d20"/><rect x="89.5" y="20.5" width="5" height="12" rx="2.5" fill="#fff"/><circle cx="92" cy="38" r="3" fill="#fff"/></svg>
<p class="ss-warning" id="learningWarning">Warning</p>
<p class="ss-title">This was a phishing simulation</p>
<p class="ss-message" id="learningMessage">A suspicious link can put your account and company data at risk. Complete a short awareness quiz to build your confidence.</p>
<a class="ss-cta" id="learningContinue" href="#" target="_blank" rel="noopener">Take the Quiz</a>
<p class="ss-note">The quiz opens in a new tab.</p>
</div></div>"""
        template = template.replace('<body>', '<body>' + banner)
        if p.trigger == "clicked":
            template = re.sub(r"<form\b[^>]*>.*?</form>", '', template, flags=re.S)
        script = """<script>
const bridgeBase=BASE;
const bridgeTicket=TICKET;
const bridgeTrigger=TRIGGER;
const rid=new URLSearchParams(location.search).get('rid');
const banner=document.getElementById('learningBanner');
const quizLink=document.getElementById('learningContinue');
const form=document.querySelector('form');
function showLearning(message){
 document.getElementById('learningMessage').textContent=message;
 if(rid)quizLink.href=bridgeBase+'/learn/entry?'+new URLSearchParams({ticket:bridgeTicket,rid:rid});
 banner.hidden=false;document.documentElement.style.overflow='hidden';quizLink.focus();
}
quizLink.addEventListener('click',(event)=>{
 if(!rid){event.preventDefault();document.getElementById('learningMessage').textContent='Missing tracking ID. Open the link from your simulation email.';}
});
banner.addEventListener('keydown',(event)=>{if(event.key==='Tab'){event.preventDefault();quizLink.focus();}});
if(bridgeTrigger==='clicked')showLearning('You opened a simulated phishing link. In a real attack, this could expose company information. Take the quiz to learn how to spot it.');
if(form)form.addEventListener('submit',async(event)=>{
 event.preventDefault();const button=form.querySelector('button');button.disabled=true;
 try {
  if(!rid)throw new Error('Missing recipient tracking ID');
  const payload=new URLSearchParams();
  payload.set('email',form.querySelector('[name=email]').value);
  payload.set('simulation_submission','confirmed');
  const passwordField=form.querySelector('input[type=password]');
  if(passwordField)passwordField.value='';
  const response=await fetch(location.href,{method:'POST',body:payload,credentials:'same-origin',redirect:'error'});
  if(!response.ok)throw new Error('Simulation submission did not complete');
  form.hidden=true;
  document.getElementById('bridgeStatus').textContent='Simulation submission recorded.';
  showLearning('You submitted a simulation form. A real phishing form could steal your login details or company data. Take the quiz to learn how to spot it.');
 } catch(error){button.disabled=false;document.getElementById('bridgeStatus').textContent='Unable to record the simulation. Check the server and try again.';}
});
</script>""".replace("BASE", json.dumps(p.public_base.rstrip("/"))).replace("TICKET", json.dumps(ticket)).replace("TRIGGER", json.dumps(p.trigger))
        template = template.replace("</body>", script + "</body>")
        return {
            "campaign_id": ca["id"],
            "expires": expires,
            "trigger": p.trigger,
            "landing_html": template,
            "instructions": "Paste this HTML into the same Gophish campaign landing page; enable Capture Submitted Data only for the fictional test-email field. Keep Capture Passwords off. Use signed webhooks or campaign polling. Leave the Gophish Redirect URL empty. The configured click or submission trigger displays a banner; only Take the quiz starts the learning handoff. Ticket scopes a campaign and never signs in a participant.",
        }

    @m.app.get("/learn/entry")
    def entry(ticket: str, rid: str):
        with m.db() as c:
            validate_ticket(c, ticket)
        # No event is created from a GET or by possessing a handoff ticket.
        return RedirectResponse(
            "/app/login.html#" + urlencode({"ticket": ticket, "rid": rid}),
            status_code=303,
        )

    @m.app.post("/learning/handoff/resolve")
    def resolve(p: HandoffRequest, u=Depends(m.current_user)):
        with m.db() as c:
            token = validate_ticket(c, p.ticket)
            recipient = c.execute(
                "SELECT email FROM recipients WHERE campaign_id=? AND rid=?",
                (token["campaign_id"], p.rid),
            ).fetchone()
            if not recipient or recipient["email"] != u["email"]:
                raise HTTPException(
                    403, "Sign in with the account assigned to this simulation link"
                )
            outcome = next(
                x
                for x in m.outcomes(c, u["email"])
                if x["campaign_id"] == token["campaign_id"]
            )
            observed = (
                outcome["clicked"]
                if token["trigger"] == "clicked"
                else outcome["submitted"]
            )
            if not observed:
                return {
                    "status": "pending",
                    "message": "Waiting for verified simulation interaction matching this learning trigger. The campaign must be synchronized or webhook telemetry delivered.",
                }
            assignment = c.execute(
                "SELECT id,status FROM assignments WHERE campaign_id=? AND email=? AND status!='cancelled'",
                (token["campaign_id"], u["email"]),
            ).fetchone()
            if not assignment:
                return {
                    "status": "pending",
                    "message": "Assignment is not available yet.",
                }
            m.audit(c, u["email"], "learning_handoff_resolved", assignment["id"])
            return {"status": "ready", "assignment_id": assignment["id"]}

    @m.app.get("/admin/grc")
    def grc(source: str = "practice", u=Depends(m.admin)):
        if source not in ("practice", "live"):
            raise HTTPException(422, "Invalid source")
        with m.db() as c:
            campaigns = c.execute(
                "SELECT COUNT(*) FROM campaigns WHERE source=?", (source,)
            ).fetchone()[0]
            attempts = c.execute(
                "SELECT COUNT(*) FROM quiz_attempts WHERE source=?", (source,)
            ).fetchone()[0]
            active = c.execute(
                "SELECT COUNT(*) FROM assignments WHERE source=? AND status!='cancelled'",
                (source,),
            ).fetchone()[0]
            passed = c.execute(
                "SELECT COUNT(*) FROM assignments WHERE source=? AND status='passed'",
                (source,),
            ).fetchone()[0]
            issues = c.execute(
                "SELECT COUNT(*) FROM events JOIN campaigns ON campaigns.id=events.campaign_id WHERE source=? AND quality='suspected'",
                (source,),
            ).fetchone()[0]
            controls = [
                dict(r) for r in c.execute("SELECT * FROM grc_controls ORDER BY id")
            ]
            summaries = {
                "AW-01": f"{campaigns} campaign profiles; authorization must be confirmed outside this prototype",
                "AW-02": f"{passed}/{active} active assignments passed; {attempts} recorded quiz attempts",
                "AW-03": "Review dashboard baseline, comparable retest and follow-up evidence; missing retests remain pending",
                "AW-04": f"{issues} suspected events awaiting review; metadata-only ingestion and signed webhook controls",
            }
            for r in controls:
                r.update(
                    evidence=summaries[r["id"]], status="Review required", source=source
                )
            return {
                "controls": controls,
                "notice": "Internal awareness requirements and evidence support. This is not certification or a claim of complete ISO compliance. All records use the selected source; owner and review dates apply organization-wide.",
            }

    @m.app.patch("/admin/grc/{control_id}")
    def update_control(control_id: str, p: ControlUpdate, u=Depends(m.admin)):
        due = m.date(p.review_due).isoformat()
        with m.db() as c:
            if not c.execute(
                "SELECT 1 FROM grc_controls WHERE id=?", (control_id,)
            ).fetchone():
                raise HTTPException(404, "Control missing")
            c.execute(
                "UPDATE grc_controls SET owner=?,review_due=? WHERE id=?",
                (p.owner, due, control_id),
            )
            m.audit(c, u["email"], "grc_review_updated", control_id)
        return {"status": "saved"}

    @m.app.get("/admin/grc/export")
    def export(source: str = "practice", u=Depends(m.admin)):
        import csv, io

        result = grc(source, u)
        out = io.StringIO()
        w = csv.writer(out)
        w.writerow(
            [
                "Requirement ID",
                "Requirement",
                "Owner",
                "Review due",
                "Source",
                "Evidence",
                "Status",
            ]
        )
        for row in result["controls"]:
            w.writerow(
                [
                    (
                        m.safe_csv(row[k])
                        if hasattr(m, "safe_csv")
                        else (
                            "'" + str(row[k])
                            if str(row[k]).lstrip().startswith(("=", "+", "-", "@"))
                            else row[k]
                        )
                    )
                    for k in [
                        "id",
                        "requirement",
                        "owner",
                        "review_due",
                        "source",
                        "evidence",
                        "status",
                    ]
                ]
            )
        return m.Response(
            out.getvalue(),
            media_type="text/csv",
            headers={
                "Content-Disposition": 'attachment; filename="securesense_grc_evidence.csv"'
            },
        )
