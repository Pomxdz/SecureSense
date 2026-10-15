from playwright.sync_api import sync_playwright
from pathlib import Path
import json, subprocess, sys, time, atexit, httpx, os, tempfile

root = Path(__file__).resolve().parents[1]
scratch = Path(tempfile.mkdtemp(prefix="securesense-ui-"))
os.environ["SECURESENSE_DB"] = str(scratch / "ui.db")
os.environ["SECURESENSE_CREDENTIALS_PATH"] = str(scratch / "credentials.txt")
out = root / "evidence"
out.mkdir(exist_ok=True)
server = subprocess.Popen(
    [sys.executable, str(root / "run.py"), "--practice", "--port", "8123"],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
atexit.register(server.terminate)
for _ in range(100):
    try:
        if (
            httpx.get("http://127.0.0.1:8123/health", trust_env=False).status_code
            == 200
        ):
            break
    except httpx.HTTPError:
        pass
    time.sleep(0.05)
creds = {}
for line in (scratch / "credentials.txt").read_text().splitlines():
    e, pw = line.split(" : ", 1)
    creds[e] = pw
errors = []
checks = []
with sync_playwright() as p:
    b = p.chromium.launch(
        executable_path=os.getenv("CHROMIUM_EXECUTABLE") or None,
        headless=True,
        args=["--no-sandbox"],
    )
    page = b.new_page(viewport={"width": 1440, "height": 1000})
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto("http://127.0.0.1:8123/app/login.html")
    page.screenshot(path=str(out / "login.png"))
    page.fill("#loginEmail", "admin@example.test")
    page.fill("#loginPassword", creds["admin@example.test"])
    page.click("button[type=submit]")
    page.wait_for_selector("#metrics .metric")
    assert page.locator("#error").is_hidden(), page.locator("#error").inner_text()
    checks.append("Administrator dashboard loaded")
    page.screenshot(path=str(out / "dashboard.png"), full_page=True)
    page.screenshot(path=str(out / "dashboard-overview.png"))
    page.locator('.filter-details > summary').click()
    page.click('#srcPractice')
    page.locator('#sourceNotice').filter(has_text='Practice records').wait_for()
    assert page.get_by_text('Detailed analysis and administration', exact=True).count() == 0
    page.locator('#aiOverview .risk-row .risk-row-top button').first.click()
    assert page.get_by_role('heading', name='Why this score', exact=True).first.is_visible()
    assert page.get_by_text('AI summary', exact=True).count() == 0
    assert page.get_by_role('button', name='Generate AI summary', exact=True).count() == 0
    page.get_by_role('button', name='Full profile', exact=True).first.click()
    page.wait_for_selector("#profileDialog[open]")
    assert "Counts only" in page.locator("#profileContent").inner_text()
    assert "Behavioural indicator" not in page.locator("#profileContent").inner_text()
    assert "Optional AI explanation" not in page.locator("#profileContent").inner_text()
    checks.append("Participant drilldown loaded")
    page.screenshot(path=str(out / "profile.png"))
    page.click("#closeProfile")
    page.click("#srcLive")
    page.locator("#sourceNotice").filter(has_text="Live campaigns").wait_for()
    page.wait_for_timeout(150)
    assert "No delivered simulation emails" in page.locator("#dashboardSummary").inner_text()
    checks.append("Live empty state is unassessed")
    page.click("#srcPractice")
    page.locator("#sourceNotice").filter(has_text="Practice records").wait_for()
    page.select_option("#department", "Finance")
    page.click("#filters button[type=submit]")
    page.wait_for_timeout(300)
    assert "20 delivered simulation emails" in page.locator("#dashboardSummary").inner_text()
    checks.append("Department filter applied")
    with page.expect_download() as download:
        page.click("#export")
    assert download.value.suggested_filename == "securesense_evidence.csv"
    checks.append("Authenticated filtered export downloaded")
    page.goto("http://127.0.0.1:8123/app/settings.html")
    page.wait_for_selector("#integrationStatus .kv")
    checks.append("Integration console loaded")
    page.goto("http://127.0.0.1:8123/app/admin.html")
    page.wait_for_selector("#metrics .metric")
    page.set_viewport_size({"width": 390, "height": 844})
    page.screenshot(path=str(out / "dashboard-mobile.png"), full_page=True)
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth+2")
    checks.append("Mobile dashboard fits viewport")
    page.set_viewport_size({"width": 1440, "height": 1000})
    page.click("#logout")
    page.wait_for_url("**/login.html")
    page.fill("#loginEmail", "dilini.jayasinghe@example.test")
    page.fill("#loginPassword", creds["dilini.jayasinghe@example.test"])
    page.click("button[type=submit]")
    page.wait_for_selector("#assignments .assignment")
    page.screenshot(path=str(out / "employee.png"), full_page=True)
    page.screenshot(path=str(out / "employee-overview.png"))
    page.locator("#assignments button").first.click()
    page.wait_for_selector("#quizDialog[open]")
    checks.append("Employee lesson and quiz opened")
    link = page.locator("#jigsawPractice")
    assert link.get_attribute("href") == "https://phishingquiz.withgoogle.com/?hl=en-GB"
    assert link.get_attribute("target") == "_blank"
    assert "noopener" in link.get_attribute("rel")
    assert "cannot verify its results" in page.locator("#lesson").inner_text()
    checks.append(
        "Jigsaw practice is external and clearly separated from verified completion"
    )
    sys.path.insert(0, str(root / "Member2"))
    from learning_content import CONTENT

    module = page.locator("#quizTitle").inner_text()
    categories = {
        "Invoice and Payroll Verification": "Financial Fraud",
        "Account and Form Verification": "Credential Harvesting",
        "Recognizing Persuasion and Impersonation": "Social Engineering",
    }
    fields = page.locator("#quizForm fieldset")
    for index, question in enumerate(CONTENT[categories[module]][1]):
        fields.nth(index).locator("input[type=radio]").nth(question[2]).check()
    page.click("#quizForm button[type=submit]")
    page.wait_for_selector("#quizResult h3")
    assert "100%" in page.locator("#quizResult h3").inner_text()
    checks.append("Employee quiz server graded and passed")
    page.screenshot(path=str(out / "quiz.png"))
    page.locator("#quizDialog").evaluate("(d)=>d.scrollTop=0")
    page.screenshot(path=str(out / "quiz-overview.png"))
    page.click("#closeQuiz")
    page.wait_for_timeout(100)
    assert page.locator("#completedAssignments .learning-card").count() > 0
    checks.append("Verified pass displayed in employee portal")
    page.goto("http://127.0.0.1:8123/app/admin.html")
    page.wait_for_url("**/employee.html")
    checks.append("Employee redirected away from admin page")
    b.close()
assert not errors, errors
(out / "browser_results.json").write_text(
    json.dumps({"checks": checks, "page_errors": errors}, indent=2)
)
print(json.dumps({"passed": len(checks), "page_errors": errors}, indent=2))
