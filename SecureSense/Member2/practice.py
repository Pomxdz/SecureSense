"""Fixed scenarios, never random risk scores. Idempotent practice creation."""

from datetime import datetime, timedelta, timezone
import json
import main as m

# Public, synthetic local-practice identities. Never use these credentials for live users.
practice_ACCOUNTS = [
    {
        "name": "Amali Perera",
        "email": "amali.perera@example.test",
        "password": "Amali@920",
    },
    {
        "name": "Nuwan Wickramasinghe",
        "email": "nuwan.wickramasinghe@example.test",
        "password": "Wickrama@b23",
    },
    {
        "name": "Amaya Herath",
        "email": "amaya.herath@example.test",
        "password": "Amaya@930",
    },
    {
        "name": "Kasun Fernando",
        "email": "kasun.fernando@example.test",
        "password": "Kasun@940",
    },
    {
        "name": "Dilini Jayasinghe",
        "email": "dilini.jayasinghe@example.test",
        "password": "Dilini@950",
    },
    {
        "name": "Tharindu Silva",
        "email": "tharindu.silva@example.test",
        "password": "Tharindu@960",
    },
    {
        "name": "Kavindi Rathnayake",
        "email": "kavindi.rathnayake@example.test",
        "password": "Kavindi@970",
    },
    {
        "name": "Sachith Bandara",
        "email": "sachith.bandara@example.test",
        "password": "Sachith@980",
    },
    {
        "name": "Ishara Senanayake",
        "email": "ishara.senanayake@example.test",
        "password": "Ishara@990",
    },
    {
        "name": "Dinuka Weerasinghe",
        "email": "dinuka.weerasinghe@example.test",
        "password": "Dinuka@910",
    },
    {
        "name": "Sanduni Wijesinghe",
        "email": "sanduni.wijesinghe@example.test",
        "password": "Sanduni@915",
    },
    {
        "name": "Pasindu Gunawardena",
        "email": "pasindu.gunawardena@example.test",
        "password": "Pasindu@925",
    },
]


def practice_email(i):
    return practice_ACCOUNTS[i - 1]["email"]


def seed():
    credentials = {}
    with m.db() as c:
        if c.execute("SELECT 1 FROM campaigns WHERE source='practice'").fetchone():
            return None
        departments = ["Finance", "IT", "Operations"]
        for i in range(1, 13):
            e = practice_email(i)
            pw = practice_ACCOUNTS[i - 1]["password"]
            credentials[e] = pw
            c.execute(
                "INSERT OR IGNORE INTO users VALUES(?,?,?,?,?)",
                (
                    e,
                    practice_ACCOUNTS[i - 1]["name"],
                    departments[(i - 1) % 3],
                    "employee",
                    m.password_hash(pw),
                ),
            )
        base = datetime.now(timezone.utc).replace(
            hour=9, minute=0, second=0, microsecond=0
        ) - timedelta(days=60)
        specs = [
            (
                "practice-baseline",
                "Account review baseline",
                "Credential Harvesting",
                "moderate",
                0,
                ["urgency", "authority"],
            ),
            (
                "practice-retest",
                "Account review retest",
                "Credential Harvesting",
                "moderate",
                20,
                ["urgency", "authority"],
            ),
            (
                "practice-followup",
                "Account review follow up",
                "Credential Harvesting",
                "moderate",
                40,
                ["urgency", "authority"],
            ),
            (
                "practice-invoice",
                "Invoice change exercise",
                "Financial Fraud",
                "hard",
                50,
                ["authority", "familiarity"],
            ),
            (
                "practice-reward",
                "Reward message exercise",
                "Social Engineering",
                "easy",
                55,
                ["reward"],
            ),
        ]
        for cid, name, category, difficulty, offset, tags in specs:
            launch = base + timedelta(days=offset)
            p = m.Campaign(
                id=cid,
                name=name,
                category=category,
                theme=(
                    "Account security"
                    if category == "Credential Harvesting"
                    else "Invoice" if category == "Financial Fraud" else "Reward"
                ),
                persuasion=tags,
                identity=(
                    "IT support"
                    if category == "Credential Harvesting"
                    else "Supplier" if category == "Financial Fraud" else "Rewards team"
                ),
                warning_signs=["Unexpected request", "Unfamiliar destination domain"],
                difficulty=difficulty,
                audience_relevance="Role relevance reviewed using the documented assignment rubric",
                source="practice",
                launched_at=launch.isoformat(),
            )
            m.add_campaign(c, p)
            for i in range(1, 13):
                e = practice_email(i)
                rid = f"{cid}-r{i}"
                c.execute("INSERT INTO recipients VALUES(?,?,?)", (cid, e, rid))
                events = [("Email Sent", 0)]
                if cid == "practice-baseline":
                    if i <= 4:
                        events += [
                            ("Clicked Link", 60 + i),
                            ("Submitted Data", 100 + i),
                        ]
                    elif i <= 7:
                        events += [("Clicked Link", 200 + i)]
                    elif i <= 10:
                        events += [("Email Reported", 240 + i)]
                elif cid in ["practice-retest", "practice-followup"]:
                    if i in [1, 2, 3, 8, 9, 10]:
                        events += [("Email Reported", 140 + i)]
                    elif i == 4:
                        events += [
                            ("Clicked Link", 80),
                            ("Submitted Data", 120),
                            ("Email Reported", 200),
                        ]
                    elif i in [5, 6]:
                        events += [("Clicked Link", 180), ("Email Reported", 260)]
                    elif i == 7 and cid == "practice-retest":
                        events += [("Clicked Link", 180)]
                    elif i == 7:
                        events += [("Email Reported", 210)]
                elif cid == "practice-invoice":
                    if i <= 5:
                        events += [
                            ("Clicked Link", 70 + i),
                            ("Submitted Data", 110 + i),
                        ]
                    elif i <= 8:
                        events += [
                            ("Clicked Link", 160 + i),
                            ("Email Reported", 250 + i),
                        ]
                    elif i <= 10:
                        events += [("Email Reported", 300 + i)]
                else:
                    if i == 1:
                        events += [("Clicked Link", 100), ("Email Reported", 160)]
                    elif i <= 10:
                        events += [("Email Reported", 200 + i)]
                for action, seconds in events:
                    m.record_event(
                        c,
                        {
                            "email": e,
                            "rid": rid,
                            "message": action,
                            "time": (launch + timedelta(seconds=seconds)).isoformat(),
                        },
                        cid,
                    )
                if cid == "practice-baseline" and i <= 4:
                    a = c.execute(
                        "SELECT * FROM assignments WHERE email=? AND campaign_id=?",
                        (e, cid),
                    ).fetchone()
                    completed = (launch + timedelta(days=2)).isoformat()
                    answers = [q[2] for q in m.questions(a)]
                    c.execute(
                        "UPDATE assignments SET status='passed',started_at=?,completed_at=? WHERE id=?",
                        (completed, completed, a["id"]),
                    )
                    c.execute(
                        "INSERT INTO quiz_attempts(assignment_id,at,score,passed,answers_json,source) VALUES(?,?,?,?,?,?)",
                        (a["id"], completed, 100, 1, json.dumps(answers), "practice"),
                    )
        # Scanner-like interaction held for human review; never counted as a confirmed human click.
        launch = base + timedelta(days=55)
        m.record_event(
            c,
            {
                "email": practice_email(12),
                "rid": "practice-reward-r12",
                "message": "Clicked Link",
                "time": (launch + timedelta(seconds=1)).isoformat(),
                "details": {"browser": {"user-agent": "Security Scanner Bot"}},
            },
            "practice-reward",
        )
        c.execute(
            "INSERT INTO quarantine(received_at,reason,campaign_id) VALUES(?,?,?)",
            (
                m.now(),
                "Synthetic example: unmapped native webhook; excluded from outcomes",
                "practice-reward",
            ),
        )
        for i in [1, 4, 5]:
            c.execute(
                "INSERT INTO reflections VALUES(NULL,?,?,?,?)",
                (practice_email(i), "practice-baseline", "urgency", m.now()),
            )
        # Historical assignment dates and due dates align with the campaign chronology.
        for a in c.execute(
            "SELECT a.id,ca.launched_at FROM assignments a JOIN campaigns ca ON ca.id=a.campaign_id"
        ).fetchall():
            assigned = m.date(a["launched_at"]) + timedelta(minutes=5)
            c.execute(
                "UPDATE assignments SET assigned_at=?,due_at=? WHERE id=?",
                (
                    assigned.isoformat(),
                    (assigned + timedelta(days=7)).isoformat(),
                    a["id"],
                ),
            )
    return credentials
