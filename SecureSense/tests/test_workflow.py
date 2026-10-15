"""Regression tests for meaningful behavioural, training and security requirements."""

import hashlib, hmac, json, sys, shutil
from pathlib import Path
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Member2"))
import main as m
from practice import seed


@pytest.fixture(scope="session")
def baseline(tmp_path_factory):
    path = tmp_path_factory.mktemp("baseline") / "data.db"
    m.DB_PATH = path
    m.setup_database()
    seed()
    with m.db() as c:
        c.execute(
            "INSERT INTO users VALUES(?,?,?,?,?)",
            (
                "admin@example.test",
                "Admin",
                "InfoSec",
                "admin",
                m.password_hash("test-password-123"),
            ),
        )
        c.execute(
            "UPDATE users SET password_hash=? WHERE email=?",
            (m.password_hash("test-password-123"), "dilini.jayasinghe@example.test"),
        )
    return path


@pytest.fixture
def client(tmp_path, baseline, monkeypatch):
    m.DB_PATH = tmp_path / "data.db"
    shutil.copyfile(baseline, m.DB_PATH)
    monkeypatch.setenv("GOPHISH_WEBHOOK_SECRET", "test-webhook-secret")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_MODEL", raising=False)
    with TestClient(m.app) as c:
        yield c


def login(client, who="admin@example.test"):
    r = client.post("/auth/login", json={"email": who, "password": "test-password-123"})
    assert r.status_code == 200
    return {"Authorization": "Bearer " + r.json()["token"]}


def webhook(client, p, bound=None):
    body = json.dumps(p, separators=(",", ":")).encode()
    sig = "sha256=" + hmac.new(b"test-webhook-secret", body, hashlib.sha256).hexdigest()
    return client.post(
        "/webhook" + ("?campaign_id=" + bound if bound else ""),
        content=body,
        headers={"X-Gophish-Signature": sig, "Content-Type": "application/json"},
    )


def event(
    action="Clicked Link",
    e="pasindu.gunawardena@example.test",
    campaign="practice-reward",
    seconds=90,
):
    with m.db() as c:
        t = m.date(
            c.execute(
                "SELECT launched_at FROM campaigns WHERE id=?", (campaign,)
            ).fetchone()[0]
        )
    with m.db() as c:
        rid = c.execute(
            "SELECT rid FROM recipients WHERE campaign_id=? AND email=?", (campaign, e)
        ).fetchone()[0]
    return {
        "email": e,
        "message": action,
        "time": (t + timedelta(seconds=seconds)).isoformat(),
        "details": json.dumps({"payload": {"rid": [rid]}}),
    }


def test_access_requires_auth(client):
    assert client.get("/metrics").status_code == 401
    assert client.get("/user/dilini.jayasinghe@example.test").status_code == 401


def test_employee_rbac(client):
    h = login(client, "dilini.jayasinghe@example.test")
    assert client.get("/metrics", headers=h).status_code == 403
    assert client.get("/user/amali.perera@example.test", headers=h).status_code == 403
    assert (
        client.get("/user/dilini.jayasinghe@example.test", headers=h).status_code == 200
    )
    assert client.post("/admin/users", headers=h, json={}).status_code == 403


def test_real_login_and_logout(client):
    assert (
        client.post(
            "/auth/login", json={"email": "admin@example.test", "password": "wrong"}
        ).status_code
        == 401
    )
    h = login(client)
    assert client.post("/auth/logout", headers=h).status_code == 200
    assert client.get("/metrics", headers=h).status_code == 401


def test_login_rate_limit(client):
    for _ in range(20):
        assert (
            client.post(
                "/auth/login",
                json={"email": "missing@example.test", "password": "wrong"},
            ).status_code
            == 401
        )
    assert (
        client.post(
            "/auth/login", json={"email": "missing@example.test", "password": "wrong"}
        ).status_code
        == 429
    )


def test_counts_are_observations_not_rows(client):
    d = client.get("/metrics", headers=login(client)).json()
    assert d["participants"] == 12 and d["sent_observations"] == 60
    assert (
        d["click_rate"]["n"] == 23
        and d["submission_rate"]["n"] == 11
        and d["report_rate"]["n"] == 37
    )
    assert sum(d["journeys"].values()) == 60
    assert d["training_completion"]["n"] == 4
    assert d["quality"]["suspected_events"] == 1


def test_duplicate_webhook_does_not_inflate(client):
    p = event()
    a = webhook(client, p)
    b = webhook(client, p)
    assert a.json()["status"] == "recorded" and b.json()["status"] == "duplicate"
    d = client.get("/metrics", headers=login(client)).json()
    assert d["sent_observations"] == 60 and d["click_rate"]["n"] == 24


def test_multiple_clicks_same_campaign_once(client):
    for seconds in [90, 100, 110]:
        assert webhook(client, event(seconds=seconds)).status_code == 200
    d = client.get("/metrics", headers=login(client)).json()
    assert d["click_rate"]["n"] == 24


def test_signed_native_event_and_bound_campaign(client):
    p = event("Email Reported")
    p["details"] = ""
    assert webhook(client, p, "practice-reward").status_code == 200


def test_ambiguous_mapping_is_quarantined(client):
    p = event("Email Sent")
    p["details"] = ""
    assert webhook(client, p).status_code == 422
    with m.db() as c:
        assert c.execute("SELECT COUNT(*) FROM quarantine").fetchone()[0] == 2


def test_bad_signature_rejected(client):
    assert client.post("/webhook", json=event()).status_code == 401


def test_unknown_event_does_not_become_failure(client):
    p = event("Something Else")
    assert webhook(client, p).status_code == 422
    d = client.get("/metrics", headers=login(client)).json()
    assert d["click_rate"]["n"] == 23


def test_invalid_dates_and_form_values_not_stored(client):
    p = event()
    p["time"] = "not-time"
    assert webhook(client, p).status_code == 422
    p = event()
    details = json.loads(p["details"])
    details["payload"]["password"] = ["NEVER_STORE_THIS"]
    p["details"] = details
    assert webhook(client, p).status_code == 200
    assert b"NEVER_STORE_THIS" not in m.DB_PATH.read_bytes()


def test_scanner_review_reconciles_assignment(client):
    h = login(client)
    with m.db() as c:
        i = c.execute("SELECT id FROM events WHERE quality='suspected'").fetchone()[0]
    assert (
        client.post(
            f"/admin/events/{i}/quality",
            headers=h,
            json={
                "quality": "human",
                "reason": "Browser activity independently verified",
            },
        ).status_code
        == 200
    )
    assert client.get("/metrics", headers=h).json()["click_rate"]["n"] == 24
    assert (
        client.post(
            f"/admin/events/{i}/quality",
            headers=h,
            json={"quality": "automated", "reason": "Confirmed mail scanner activity"},
        ).status_code
        == 200
    )
    assert client.get("/metrics", headers=h).json()["click_rate"]["n"] == 23
    with m.db() as c:
        assert (
            c.execute(
                "SELECT status FROM assignments WHERE email='pasindu.gunawardena@example.test' AND campaign_id='practice-reward'"
            ).fetchone()[0]
            == "cancelled"
        )


def test_no_history_is_unassessed(client):
    h = login(client)
    assert (
        client.post(
            "/admin/users",
            headers=h,
            json={
                "email": "new@example.test",
                "name": "New",
                "department": "IT",
                "password": "long-password-123",
                "role": "employee",
            },
        ).status_code
        == 200
    )
    d = client.get("/user/new@example.test", headers=h).json()
    assert d["assessments"]["live"]["assessed_outcomes"] == 0 and not d["history"]


def test_rules_are_repeatable_and_sources_separate(client):
    h = login(client)
    a = client.get("/metrics", headers=h).json()
    b = client.get("/metrics", headers=h).json()
    assert a["assessed_people"] == b["assessed_people"]
    live = client.get("/metrics?source=live", headers=h).json()
    assert live["sent_observations"] == 0 and live["assessed_people"] == 0


def test_report_first_does_not_erase_later_exposure(client):
    assert webhook(client, event("Email Reported", seconds=70)).status_code == 200
    assert webhook(client, event("Submitted Data", seconds=90)).status_code == 200
    with m.db() as c:
        o = next(
            x
            for x in m.outcomes(c, "pasindu.gunawardena@example.test")
            if x["campaign_id"] == "practice-reward"
        )
        assert o["severity"] == 80 and o["journey"] == "reported_before_then_interacted"


def test_submission_without_click_still_interaction(client):
    assert webhook(client, event("Submitted Data")).status_code == 200
    d = client.get("/metrics", headers=login(client)).json()
    assert (
        d["click_rate"]["n"] == 24
        and d["submission_rate"]["n"] == 12
        and d["quality"]["missing_click_events"] == 1
    )


def test_training_verified_per_assignment(client):
    h = login(client, "dilini.jayasinghe@example.test")
    p = client.get("/user/dilini.jayasinghe@example.test", headers=h).json()
    i = p["assignments"][0]["id"]
    q = client.get(f"/training/{i}", headers=h).json()
    assert all("correct" not in z for z in q["questions"])
    assert (
        client.post(
            f"/training/{i}/submit", headers=h, json={"answers": [0, 1, 2, 1, 0]}
        ).status_code
        == 409
    )
    assert client.post(f"/training/{i}/start", headers=h).status_code == 200
    with m.db() as c:
        assert (
            c.execute("SELECT status FROM assignments WHERE id=?", (i,)).fetchone()[0]
            == "started"
        )
    fail = client.post(
        f"/training/{i}/submit", headers=h, json={"answers": [2, 0, 0, 0, 2]}
    ).json()
    assert fail["passed"] is False
    with m.db() as c:
        a = c.execute("SELECT * FROM assignments WHERE id=?", (i,)).fetchone()
        correct = [q[2] for q in m.questions(a)]
        other = c.execute(
            "SELECT id,status FROM assignments WHERE email=? AND id!=?",
            ("dilini.jayasinghe@example.test", i),
        ).fetchall()
    passed = client.post(
        f"/training/{i}/submit", headers=h, json={"answers": correct}
    ).json()
    assert passed["score"] == 100 and passed["passed"]
    with m.db() as c:
        assert (
            c.execute("SELECT status FROM assignments WHERE id=?", (i,)).fetchone()[0]
            == "passed"
        )
        assert [
            (x["id"], x["status"])
            for x in c.execute(
                "SELECT id,status FROM assignments WHERE email=? AND id!=?",
                ("dilini.jayasinghe@example.test", i),
            )
        ] == [(x["id"], x["status"]) for x in other]


def test_quiz_pass_requeues_ai_assessment_with_training_evidence(client, monkeypatch):
    import proposal_features as pf

    monkeypatch.setenv("GROQ_API_KEY", "fixture-key")
    monkeypatch.setenv("GROQ_MODEL", "fixture-model")
    h = login(client, "dilini.jayasinghe@example.test")
    p = client.get("/user/dilini.jayasinghe@example.test", headers=h).json()
    i = p["assignments"][0]["id"]
    with m.db() as c:
        a = c.execute("SELECT * FROM assignments WHERE id=?", (i,)).fetchone()
        source = a["source"]
        correct = [q[2] for q in m.questions(a)]
    assert client.post(f"/training/{i}/start", headers=h).status_code == 200

    with m.db() as c:
        before = pf.evidence(c, "dilini.jayasinghe@example.test", source)
    assert all(not o["remedial_training_passed"] for o in before["observations"])

    passed = client.post(
        f"/training/{i}/submit", headers=h, json={"answers": correct}
    ).json()
    assert passed["passed"]

    with m.db() as c:
        after = pf.evidence(c, "dilini.jayasinghe@example.test", source)
    assert any(o["remedial_training_passed"] for o in after["observations"])

    with m.db() as c:
        job = c.execute(
            "SELECT * FROM ai_jobs WHERE email=? AND source=? ORDER BY id DESC LIMIT 1",
            ("dilini.jayasinghe@example.test", source),
        ).fetchone()
    assert job["status"] == "pending"
    assert json.loads(job["input_json"]) == after


def test_training_other_user_forbidden(client):
    h = login(client, "dilini.jayasinghe@example.test")
    with m.db() as c:
        i = c.execute(
            "SELECT id FROM assignments WHERE email='amali.perera@example.test'"
        ).fetchone()[0]
    assert client.get(f"/training/{i}", headers=h).status_code == 403


def test_comparable_retest_progress(client):
    d = client.get("/metrics", headers=login(client)).json()
    p = next(x for x in d["progress"] if x["email"] == "amali.perera@example.test")
    assert (
        p["baseline"] == "test_form_submitted"
        and p["retest"] == "reported_before_interaction"
        and p["interpretation"] == "Observed outcome improved"
    )


def test_filters_and_export(client):
    h = login(client)
    d = client.get("/metrics?department=Finance&difficulty=moderate", headers=h).json()
    assert d["sent_observations"] == 12
    assert (
        client.get("/metrics?start=2030-01-01&end=2020-01-01", headers=h).status_code
        == 422
    )
    r = client.get("/admin/export.csv?source=live", headers=h)
    assert r.status_code == 200 and len(r.text.splitlines()) == 1


def test_csv_formula_escape(client):
    h = login(client)
    with m.db() as c:
        c.execute("UPDATE campaigns SET name='=HYPERLINK(1)' WHERE id='practice-baseline'")
    assert "'=HYPERLINK(1)" in client.get("/admin/export.csv", headers=h).text


def test_optional_ai_failure_does_not_zero_score(client):
    h = login(client)
    before = client.get("/user/dilini.jayasinghe@example.test", headers=h).json()[
        "assessments"
    ]
    r = client.post("/admin/ai/dilini.jayasinghe@example.test", headers=h).json()
    assert r["status"] == "unavailable"
    assert (
        client.get("/user/dilini.jayasinghe@example.test", headers=h).json()[
            "assessments"
        ]
        == before
    )


def test_provision_invalidates_existing_sessions(client):
    h = login(client)
    employee = login(client, "dilini.jayasinghe@example.test")
    r = client.post(
        "/admin/users",
        headers=h,
        json={
            "email": "dilini.jayasinghe@example.test",
            "name": "Updated",
            "department": "Finance",
            "password": "updated-password-123",
            "role": "employee",
        },
    )
    assert (
        r.status_code == 200
        and client.get("/auth/me", headers=employee).status_code == 401
    )


def test_reflections_are_explicit_and_source_filtered(client):
    h = login(client, "dilini.jayasinghe@example.test")
    assert (
        client.post(
            "/reflections",
            headers=h,
            json={"campaign_id": "practice-baseline", "reason": "urgency"},
        ).status_code
        == 200
    )
    assert (
        client.get("/admin/reflections?source=live", headers=login(client)).json()[
            "items"
        ]
        == []
    )


def test_campaign_import_validates_and_never_overwrites(client):
    h = login(client)
    p = {
        "campaign": {
            "id": "live1",
            "name": "Account campaign",
            "launched_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
        },
        "recipients": [{"email": "dilini.jayasinghe@example.test", "rid": "newrid"}],
    }
    assert client.post("/admin/campaigns", headers=h, json=p).status_code == 200
    assert client.post("/admin/campaigns", headers=h, json=p).status_code == 409
    assert (
        webhook(
            client,
            {
                "email": "dilini.jayasinghe@example.test",
                "message": "Email Sent",
                "time": p["campaign"]["launched_at"],
            },
            "live1",
        ).status_code
        == 200
    )
    assert (
        client.get("/metrics?source=live", headers=h).json()["sent_observations"] == 1
    )


def test_security_headers_and_no_inline_scripts(client):
    r = client.get("/app/admin.html")
    assert "frame-ancestors" in r.headers["Content-Security-Policy"]
    assert "onclick=" not in r.text


def test_seed_is_idempotent(client):
    with m.db() as c:
        before = c.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    assert seed() is None
    with m.db() as c:
        assert c.execute("SELECT COUNT(*) FROM events").fetchone()[0] == before


def test_gophish_sync_with_native_fixture(client, monkeypatch):
    monkeypatch.setenv("GOPHISH_API_KEY", "fixture-key")
    monkeypatch.setenv("GOPHISH_ADMIN_URL", "https://127.0.0.1:3333")
    native = {
        "id": 99,
        "results": [
            {
                "id": "RID99",
                "email": "dilini.jayasinghe@example.test",
                "first_name": "Test",
                "last_name": "User",
            }
        ],
        "timeline": [
            {
                "email": "dilini.jayasinghe@example.test",
                "message": "Email Sent",
                "time": "2026-01-01T00:00:00Z",
                "details": "",
            },
            {
                "email": "dilini.jayasinghe@example.test",
                "message": "Clicked Link",
                "time": "2026-01-01T00:01:00Z",
                "details": "",
            },
        ],
    }

    class MockClient:
        def __init__(self, **kw):
            assert kw["verify"] is True

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def get(self, url, headers):
            assert (
                url.endswith("/99") and headers["Authorization"] == "Bearer fixture-key"
            )
            return m.httpx.Response(
                200, json=native, request=m.httpx.Request("GET", url)
            )

    monkeypatch.setattr(m.httpx, "Client", MockClient)
    h = login(client)
    payload = {
        "campaign": {
            "id": "99",
            "name": "Imported live test",
            "launched_at": "2026-01-01T00:00:00Z",
        }
    }
    a = client.post("/admin/gophish/sync", headers=h, json=payload).json()
    b = client.post("/admin/gophish/sync", headers=h, json=payload).json()
    assert a["recorded"] == 2 and b["duplicates"] == 2
    assert client.get("/metrics?source=live", headers=h).json()["click_rate"]["n"] == 1


@pytest.mark.parametrize(
    "change",
    [
        {"message": []},
        {"email": {}},
        {"details": "not-json"},
        {"time": "2026-01-01T01:00:00"},
        {"details": {"payload": []}},
        {"message": "Clicked Link", "time": "2099-01-01T00:00:00Z"},
    ],
)
def test_malformed_native_event_rejected(client, change):
    p = event()
    p.update(change)
    assert webhook(client, p).status_code == 422


def test_passed_assignment_withdrawn_by_event_review(client):
    h = login(client)
    # Seeded pass remains as quiz evidence, but a withdrawn triggering event cancels its active assignment.
    with m.db() as c:
        rows = c.execute(
            "SELECT id FROM events WHERE campaign_id='practice-baseline' AND email='amali.perera@example.test' AND action IN ('clicked','test_form_submitted')"
        ).fetchall()
    for row in rows:
        assert (
            client.post(
                f"/admin/events/{row[0]}/quality",
                headers=h,
                json={
                    "quality": "automated",
                    "reason": "Synthetic review withdrawal test",
                },
            ).status_code
            == 200
        )
    with m.db() as c:
        a = c.execute(
            "SELECT * FROM assignments WHERE campaign_id='practice-baseline' AND email='amali.perera@example.test'"
        ).fetchone()
        assert (
            a["status"] == "cancelled"
            and c.execute(
                "SELECT COUNT(*) FROM quiz_attempts WHERE assignment_id=?", (a["id"],)
            ).fetchone()[0]
            == 1
        )


def test_send_retry_success_restores_denominator(client):
    p = event("Error Sending Email", seconds=3)
    assert webhook(client, p).status_code == 200
    h = login(client)
    assert client.get("/metrics", headers=h).json()["sent_observations"] == 59
    p = event("Email Sent", seconds=10)
    assert webhook(client, p).status_code == 200
    assert client.get("/metrics", headers=h).json()["sent_observations"] == 60


def test_expired_session_is_rejected(client):
    h = login(client)
    with m.db() as c:
        c.execute("UPDATE sessions SET expires='2000-01-01T00:00:00+00:00'")
    assert client.get("/metrics", headers=h).status_code == 401


def test_oversized_signed_body_rejected(client):
    p = event()
    p["details"] = "x" * 70000
    assert webhook(client, p).status_code == 413


def test_targeted_content_all_categories(client):
    from learning_content import CONTENT

    assert len({tuple(v[0]) for v in CONTENT.values()}) == 6
    for lessons, questions in CONTENT.values():
        assert len(lessons) == 4 and len(questions) == 5
        assert all(len(q[1]) == 3 and q[2] in (0, 1, 2) for q in questions)


def test_ai_jobs_auto_created_and_unavailable(client):
    import proposal_features as pf

    h = login(client)
    webhook(client, event())
    result = client.get(
        "/ai/assessments/pasindu.gunawardena@example.test", headers=h
    ).json()
    assert result["practice"]["status"] == "unavailable" and result["practice"]["score"] is None
    with m.db() as c:
        payload = json.loads(
            c.execute(
                "SELECT input_json FROM ai_jobs ORDER BY id DESC LIMIT 1"
            ).fetchone()[0]
        )
    assert "pasindu" not in json.dumps(payload) and "rid" not in json.dumps(payload)
    assert "time_to_click_seconds" in payload["observations"][0]


def queued_job(monkeypatch):
    import proposal_features as pf

    monkeypatch.setenv("GROQ_API_KEY", "fixture-key")
    monkeypatch.setenv("GROQ_MODEL", "fixture-model")
    with m.db() as c:
        c.execute("DELETE FROM ai_jobs")
        pf.enqueue(c, "amali.perera@example.test", "practice")
    return pf


def test_ai_validated_model_score_and_lineage(client, monkeypatch):
    pf = queued_job(monkeypatch)
    monkeypatch.setattr(
        pf,
        "generate",
        lambda payload, model: {
            "score": 63.5,
            "explanation": "Repeated observed interaction; later protective reporting.",
            "recommendation": "Credential Harvesting",
        },
    )
    assert pf.process_one()
    with m.db() as c:
        row = dict(c.execute("SELECT * FROM ai_jobs").fetchone())
    assert (
        row["score"] == 63.5
        and row["status"] == "available"
        and row["model"] == "fixture-model"
        and row["finished_at"]
    )
    assert len(row["fingerprint"]) == 64


@pytest.mark.parametrize("score", [101, -1, True, float("nan")])
def test_ai_invalid_score_retries_without_fake_zero(client, monkeypatch, score):
    pf = queued_job(monkeypatch)
    monkeypatch.setattr(
        pf,
        "generate",
        lambda *args: {
            "score": score,
            "explanation": "fixture",
            "recommendation": "General",
        },
    )
    for _ in range(3):
        with m.db() as c:
            c.execute("UPDATE ai_jobs SET next_at=?", (m.now(),))
        pf.process_one()
    with m.db() as c:
        r = c.execute("SELECT * FROM ai_jobs").fetchone()
    assert r["status"] == "failed" and r["score"] is None and r["attempts"] == 3


def test_ai_employee_isolation(client):
    h = login(client, "dilini.jayasinghe@example.test")
    assert (
        client.get("/ai/assessments/amali.perera@example.test", headers=h).status_code
        == 403
    )
    assert client.get("/admin/ai/overview", headers=h).status_code == 403


def make_bridge(client):
    h = login(client)
    result = client.post(
        "/admin/learning/bridge",
        headers=h,
        json={"campaign_id": "practice-baseline", "public_base": "http://127.0.0.1:8000"},
    )
    assert result.status_code == 200
    import re

    ticket = re.search(
        r'const bridgeTicket="([^"]+)"', result.json()["landing_html"]
    ).group(1)
    return ticket


def test_handoff_requires_matching_account_and_verified_submission(client):
    ticket = make_bridge(client)
    h = login(client)
    r = client.post(
        "/learning/handoff/resolve",
        headers=h,
        json={"ticket": ticket, "rid": "practice-baseline-r1"},
    )
    assert r.status_code == 403
    # Provision a test password for Amali without changing evidence.
    with m.db() as c:
        c.execute(
            "UPDATE users SET password_hash=? WHERE email=?",
            (m.password_hash("test-password-123"), "amali.perera@example.test"),
        )
    h = login(client, "amali.perera@example.test")
    r = client.post(
        "/learning/handoff/resolve",
        headers=h,
        json={"ticket": ticket, "rid": "practice-baseline-r1"},
    )
    assert r.json()["status"] == "ready"
    with m.db() as c:
        assert (
            c.execute(
                "SELECT email FROM assignments WHERE id=?", (r.json()["assignment_id"],)
            ).fetchone()[0]
            == "amali.perera@example.test"
        )


def test_handoff_get_never_creates_evidence_and_expiry(client):
    ticket = make_bridge(client)
    with m.db() as c:
        before = c.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    r = client.get(
        "/learn/entry",
        params={"ticket": ticket, "rid": "practice-baseline-r12"},
        follow_redirects=False,
    )
    assert r.status_code == 303 and "#ticket=" in r.headers["location"]
    with m.db() as c:
        assert c.execute("SELECT COUNT(*) FROM events").fetchone()[0] == before
        c.execute("UPDATE handoff_tokens SET expires='2000-01-01T00:00:00+00:00'")
    assert (
        client.get(
            "/learn/entry", params={"ticket": ticket, "rid": "practice-baseline-r12"}
        ).status_code
        == 410
    )


def test_handoff_pending_does_not_pass_training(client):
    ticket = make_bridge(client)
    h = login(client, "dilini.jayasinghe@example.test")
    r = client.post(
        "/learning/handoff/resolve",
        headers=h,
        json={"ticket": ticket, "rid": "practice-baseline-r5"},
    )
    assert r.json()["status"] == "pending"
    with m.db() as c:
        assert (
            c.execute(
                "SELECT status FROM assignments WHERE email='dilini.jayasinghe@example.test' AND campaign_id='practice-baseline'"
            ).fetchone()[0]
            == "assigned"
        )


def test_bridge_rejects_external_http_and_unmapped_campaign(client):
    h = login(client)
    assert (
        client.post(
            "/admin/learning/bridge",
            headers=h,
            json={
                "campaign_id": "practice-baseline",
                "public_base": "http://external.example",
            },
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/admin/learning/bridge", headers=h, json={"campaign_id": "missing"}
        ).status_code
        == 404
    )


def test_grc_evidence_export_review_and_permissions(client):
    h = login(client)
    r = client.get("/admin/grc?source=live", headers=h).json()
    assert len(r["controls"]) == 4 and r["controls"][0]["evidence"].startswith(
        "0 campaign"
    )
    assert (
        client.patch(
            "/admin/grc/AW-02",
            headers=h,
            json={"owner": "=SUM(1,2)", "review_due": "2026-12-01T00:00:00Z"},
        ).status_code
        == 200
    )
    export = client.get("/admin/grc/export?source=practice", headers=h)
    assert export.status_code == 200 and "'=SUM" in export.text
    assert (
        client.get(
            "/admin/grc", headers=login(client, "dilini.jayasinghe@example.test")
        ).status_code
        == 403
    )


def test_click_bridge_and_ai_configuration_recovery(client, monkeypatch):
    h = login(client)
    r = client.post(
        "/admin/learning/bridge",
        headers=h,
        json={"campaign_id": "practice-baseline", "trigger": "clicked"},
    )
    assert r.status_code == 200 and "learningContinue" in r.json()["landing_html"] and "location.replace" not in r.json()["landing_html"]
    import proposal_features as pf

    monkeypatch.setenv("GROQ_MODEL", "fixture-late-model")
    with m.db() as c:
        pf.enqueue(c, "amali.perera@example.test", "practice")
    monkeypatch.setenv("GROQ_API_KEY", "fixture-late-key")
    with m.db() as c:
        pf.enqueue(c, "amali.perera@example.test", "practice")
        r = c.execute(
            "SELECT status FROM ai_jobs WHERE email=? AND model=? ORDER BY id DESC LIMIT 1",
            ("amali.perera@example.test", "fixture-late-model"),
        ).fetchone()
    assert r["status"] == "pending"


@pytest.mark.parametrize("category,brand,trigger", [
    ("Credential Harvesting", "SecureHub", "test_form_submission"),
    ("Financial Fraud", "ApexPay", "test_form_submission"),
    ("Social Engineering", "PeoplePlus", "test_form_submission"),
    ("Urgent Extortion", "CoreGuard", "test_form_submission"),
    ("Malware Delivery", "WorkSuite", "test_form_submission"),
])
def test_distinct_category_landings(client, category, brand, trigger):
    with m.db() as c:
        c.execute("UPDATE campaigns SET category=? WHERE id=?", (category, "practice-baseline"))
    response = client.post("/admin/learning/bridge", headers=login(client), json={"campaign_id": "practice-baseline", "trigger": trigger})
    assert response.status_code == 200
    html = response.json()["landing_html"]
    assert brand in html and "location.replace" not in html
    assert 'name="password"' not in html
    if trigger == 'test_form_submission':
        assert 'type="password"' in html
        assert "payload.set('simulation_submission','confirmed')" in html
    if trigger == "clicked":
        assert 'id="learningContinue"' in html and "addEventListener('click'" in html
    else:
        assert 'name="email"' in html and "method:'POST'" in html


def test_authenticated_phishing_report_is_owned_and_idempotent(client):
    h=login(client,'dilini.jayasinghe@example.test')
    opts=client.get('/reports/options',headers=h).json()['messages']
    assert opts
    rid=opts[0]['rid']
    payload={'rid':rid,'reason':'Unexpected sender and suspicious request.'}
    assert client.post('/reports/phishing',json=payload).status_code==401
    assert client.post('/reports/phishing',headers=h,json={**payload,'rid':'not-my-message'}).status_code==422
    first=client.post('/reports/phishing',headers=h,json=payload)
    assert first.status_code==200,first.text
    second=client.post('/reports/phishing',headers=h,json=payload)
    assert second.status_code==200 and second.json()['status']=='already_reported'
    overview=client.get('/admin/campaign-results?source=practice',headers=login(client))
    assert overview.status_code==200
    assert any(x['reported'] and x['email']=='dilini.jayasinghe@example.test' for x in overview.json()['results'])
    assert overview.json()['departments']
    assert 'password' not in str(overview.json()['results']).lower()


def test_department_results_access_and_filters(client):
    assert client.get('/admin/campaign-results').status_code==401
    assert client.get('/admin/campaign-results',headers=login(client,'dilini.jayasinghe@example.test')).status_code==403
    h=login(client)
    data=client.get('/admin/campaign-results?source=practice',headers=h).json()
    for dep in data['departments']:
        records=[x for x in data['results'] if x['department']==dep['department']]
        assert dep['passed']==sum(x['quiz_result']=='Passed' for x in records)
        assert dep['failed']==sum(x['quiz_result']=='Failed' for x in records)
        assert dep['completed']==sum(x['quiz_completed'] for x in records)
    data=client.get('/admin/campaign-results?source=practice&department=not-a-department',headers=h).json()
    assert data['results']==[] and data['departments']==[]


def test_bridge_banner_waits_for_quiz_click(client):
    for trigger in ['clicked', 'test_form_submission']:
        html = client.post('/admin/learning/bridge', headers=login(client), json={
            'campaign_id': 'practice-baseline', 'trigger': trigger
        }).json()['landing_html']
        assert 'id="learningBanner"' in html
        assert '>Take the Quiz</a>' in html
        assert 'alert(' not in html and 'confirm(' not in html and 'window.open(' not in html
        assert "redirect:'error'" in html


def test_mailbox_report_records_without_navigation(monkeypatch):
    import importlib.util
    path = Path(__file__).resolve().parents[1] / 'Member1/mail_sandbox.py'
    spec = importlib.util.spec_from_file_location('mailbox_under_test', path)
    box = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(box)
    box.messages.append({'from':'sender@example.test','to':'user@example.test','subject':'Test',
        'html':'<a href="/?rid=abc123">Open</a>','text':'','simulation':''})
    calls=[]
    monkeypatch.setattr(box, 'report_to_gophish', lambda rid:calls.append(rid))
    with box.app.test_client() as c:
        html=c.get('/message/0').get_data(as_text=True)
        assert 'id="reportPhishing"' in html
        headers={'X-Report-Token':box.messages[0]['report_token']}
        assert c.post('/message/0/report').status_code==403
        r=c.post('/message/0/report',headers=headers)
        assert r.status_code==200 and 'Location' not in r.headers
        assert calls==['abc123']
        assert c.post('/message/0/report',headers=headers).json['status']=='already_reported'
        assert calls==['abc123']
        box.messages[0]['reported']=False
        def fail(rid):raise ValueError('offline')
        monkeypatch.setattr(box,'report_to_gophish',fail)
        assert c.post('/message/0/report',headers=headers).status_code==502
        assert not box.messages[0]['reported']
        assert "script-src 'none'" in c.get('/message/0/body').headers['Content-Security-Policy']


def test_gophish_report_uses_only_configured_endpoint(monkeypatch):
    import gophish_reporting as reporting
    import httpx
    calls=[]
    real_client=httpx.Client
    def handler(request):
        calls.append(request)
        return httpx.Response(204)
    monkeypatch.setenv('GOPHISH_PHISHING_URL','http://127.0.0.1:8080')
    monkeypatch.setattr(reporting.httpx,'Client',lambda **kw:real_client(transport=httpx.MockTransport(handler),**kw))
    reporting.report_to_gophish('abc&extra=value')
    assert len(calls)==1 and calls[0].url.path=='/report'
    assert calls[0].url.params['rid']=='abc&extra=value'
    assert list(calls[0].url.params)==['rid']


def test_live_report_failure_does_not_create_local_success(client, monkeypatch):
    h=login(client,'dilini.jayasinghe@example.test')
    with m.db() as c:
        c.execute("UPDATE campaigns SET source='live' WHERE id='practice-baseline'")
        rid=c.execute("SELECT rid FROM recipients WHERE campaign_id='practice-baseline' AND email='dilini.jayasinghe@example.test'").fetchone()[0]
        c.execute("DELETE FROM events WHERE campaign_id='practice-baseline' AND email='dilini.jayasinghe@example.test' AND action='reported'")
    calls=[]
    def unavailable(rid):raise ValueError('offline')
    monkeypatch.setattr(m,'report_to_gophish',unavailable)
    payload={'rid':rid,'reason':'Suspicious sender and request'}
    assert client.post('/reports/phishing',headers=h,json=payload).status_code==502
    with m.db() as c:
        assert not c.execute("SELECT 1 FROM events WHERE campaign_id='practice-baseline' AND email='dilini.jayasinghe@example.test' AND action='reported'").fetchone()
    monkeypatch.setattr(m,'report_to_gophish',lambda rid:calls.append(rid))
    assert client.post('/reports/phishing',headers=h,json=payload).status_code==200
    assert calls==[rid]


# ---------------------------------------------------------------------------
# V4: AI is the only source of the risk score; no application-side throttle.
# ---------------------------------------------------------------------------


def test_python_does_not_calculate_a_risk_score(client):
    h = login(client)
    webhook(client, event())
    metrics = client.get("/metrics", headers=h).json()
    assert "average_indicator" not in metrics
    for person in metrics["people"]:
        assert "score" not in person and "severity" not in person
        assert "recurrence_points" not in person
    profile = client.get("/user/pasindu.gunawardena@example.test", headers=h).json()
    for assessment in profile["assessments"].values():
        assert "score" not in assessment and "severity" not in assessment
    with m.db() as c:
        stored = [r[0] for r in c.execute("SELECT score FROM assessments")]
    assert stored and all(v is None for v in stored)


def test_ai_evidence_contains_no_python_score(client):
    h = login(client)
    webhook(client, event())
    with m.db() as c:
        payload = json.loads(
            c.execute("SELECT input_json FROM ai_jobs ORDER BY id DESC LIMIT 1").fetchone()[0]
        )
    assert "rules_score" not in payload and "rubric" not in payload
    assert all("severity" not in o for o in payload["observations"])
    assert {"clicked", "submitted_test_form", "reported"} <= set(payload["observations"][0])


def test_ai_gateway_has_no_throttle(client, monkeypatch):
    import time as _time
    import proposal_features as pf

    assert not hasattr(pf, "_wait_for_provider_slot")
    assert not hasattr(pf, "_provider_spacing_seconds")
    calls = []

    class FakeMessage:
        content = "ok"

    class FakeChoice:
        message = FakeMessage()

    class FakeCompletions:
        def create(self, **kw):
            calls.append(_time.monotonic())
            return type("R", (), {"choices": [FakeChoice()]})()

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        chat = FakeChat()

    monkeypatch.setattr(pf, "_client", lambda: FakeClient())
    monkeypatch.setattr(_time, "sleep", lambda s: (_ for _ in ()).throw(AssertionError("slept")))
    start = _time.monotonic()
    for _ in range(5):
        pf.generate_text("fixture-model", "hello")
    assert len(calls) == 5 and _time.monotonic() - start < 2


def test_ai_provider_quota_error_retries_quickly_without_cooldown(client, monkeypatch):
    pf = queued_job(monkeypatch)

    def boom(*a):
        raise RuntimeError("429 RESOURCE_EXHAUSTED")

    monkeypatch.setattr(pf, "generate", boom)
    assert pf.process_one()
    with m.db() as c:
        r = dict(c.execute("SELECT * FROM ai_jobs").fetchone())
    # An ordinary short retry: never a long cooldown or a special rate_limited state.
    assert r["status"] == "pending" and r["attempts"] == 1
    wait = (m.date(r["next_at"]) - m.datetime.now(m.timezone.utc)).total_seconds()
    assert wait < 60


def test_old_rate_limited_jobs_resume_on_startup(client, monkeypatch):
    pf = queued_job(monkeypatch)
    with m.db() as c:
        c.execute(
            "UPDATE ai_jobs SET status='rate_limited',next_at='2999-01-01T00:00:00+00:00'"
        )
    pf.start()
    try:
        with m.db() as c:
            row = c.execute("SELECT status,next_at FROM ai_jobs").fetchone()
        assert row["status"] != "rate_limited" and row["next_at"] < "2999"
    finally:
        pf.shutdown()


def test_bridge_banner_is_an_overlay_that_opens_the_quiz_in_a_new_tab(client):
    h = login(client)
    html = client.post(
        "/admin/learning/bridge",
        headers=h,
        json={"campaign_id": "practice-baseline", "public_base": "http://127.0.0.1:8000"},
    ).json()["landing_html"]
    # Shown in front of the landing page, not inline above it.
    assert "#learningBanner{position:fixed;inset:0" in html
    assert 'id="learningBanner"' in html and 'aria-modal="true"' in html
    assert ">Warning<" in html and "Take the Quiz" in html
    # "Take the Quiz" is a real link that opens the sign-in flow in a NEW tab.
    assert 'id="learningContinue" href="#" target="_blank" rel="noopener"' in html
    assert "location.href=bridgeBase" not in html
    # Placeholders were filled in; the banner is revealed by the form submission.
    assert 'const bridgeBase="http://127.0.0.1:8000"' in html
    assert 'const bridgeTrigger="test_form_submission"' in html
    assert "showLearning('You submitted a simulation form" in html


def test_email_templates_do_not_open_new_tabs():
    from pathlib import Path

    root = Path(m.__file__).resolve().parent.parent / "Member1"
    files = list(root.glob("*email.html")) + list((root / "viva_templates").glob("*.html"))
    assert len(files) == 7
    assert all("_blank" not in f.read_text(encoding="utf-8") for f in files)
