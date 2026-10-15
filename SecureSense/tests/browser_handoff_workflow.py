"""Local browser integration test using a fixture phishing server, not a real Gophish engine. Uses ports 8186-8189."""
import sys,os,tempfile,threading,time,json,hmac,hashlib,importlib.util,smtplib
from pathlib import Path
from email.message import EmailMessage
from datetime import datetime,timezone,timedelta
import httpx,uvicorn
from flask import Flask,request
from werkzeug.serving import make_server
from playwright.sync_api import sync_playwright
from aiosmtpd.controller import Controller
root=Path(__file__).resolve().parents[1]
os.environ['GOPHISH_WEBHOOK_SECRET']='browser-fixture-secret'
os.environ['GOPHISH_PHISHING_URL']='http://127.0.0.1:8188/'
sys.path.insert(0,str(root/'Member2'))
import main as m
from practice import seed
m.DB_PATH=Path(tempfile.mkdtemp())/'test.db';m.setup_database();creds=seed()
with m.db() as db:db.execute('INSERT INTO users VALUES(?,?,?,?,?)',('admin@example.test','Admin','InfoSec','admin',m.password_hash('browser-admin-password')))
creds['admin@example.test']='browser-admin-password'
spec=importlib.util.spec_from_file_location('sandbox_check',root/'Member1/mail_sandbox.py');box=importlib.util.module_from_spec(spec);spec.loader.exec_module(box)
threading.Thread(target=uvicorn.run,args=(m.app,),kwargs={'host':'127.0.0.1','port':8186,'log_level':'error'},daemon=True).start()
mailserver=make_server('127.0.0.1',8187,box.app);threading.Thread(target=mailserver.serve_forever,daemon=True).start()
smtp=Controller(box.MailSandbox(),hostname='127.0.0.1',port=8189);smtp.start()
c=httpx.Client(base_url='http://127.0.0.1:8186',trust_env=False)
for _ in range(100):
 try:
  if c.get('/health').status_code==200:break
 except Exception:pass
 time.sleep(.05)
h={'Authorization':'Bearer '+c.post('/auth/login',json={'email':'admin@example.test','password':creds['admin@example.test']}).json()['token']}
scenarios=[('Credential Harvesting','SecureHub','Amali','amali.perera@example.test','Amali@920','test_form_submission','credential_harvesting.html'),('Financial Fraud','ApexPay','Kasun','kasun.fernando@example.test','Kasun@940','test_form_submission','financial_fraud.html'),('Social Engineering','PeoplePlus','Nuwan','nuwan.wickramasinghe@example.test','Wickrama@b23','test_form_submission','social_engineering.html'),('Urgent Extortion','CoreGuard','Amaya','amaya.herath@example.test','Amaya@930','test_form_submission','urgent_extortion.html'),('Malware Delivery','WorkSuite','Dilini','dilini.jayasinghe@example.test','Dilini@950','test_form_submission','malware_delivery.html')]
scenarios.append(('Social Engineering','PeoplePlus','Nuwan','nuwan.wickramasinghe@example.test','Wickrama@b23','clicked','social_engineering.html'))
pages={};targets={};reports=[]
def event(i,action):
 cid,email=targets[str(i)];payload={'email':email,'message':action,'time':datetime.now(timezone.utc).isoformat(),'details':json.dumps({'payload':{'rid':[str(i)]}})};body=json.dumps(payload).encode();sig='sha256='+hmac.new(b'browser-fixture-secret',body,hashlib.sha256).hexdigest();r=c.post('/webhook?campaign_id='+cid,content=body,headers={'X-Gophish-Signature':sig,'Content-Type':'application/json'});assert r.status_code==200,r.text
engine=Flask('fixture_phishing_engine')
@engine.route('/',methods=['GET','POST'])
def landing():
 rid=request.args['rid'];
 if request.method=='POST':
  assert 'practice-ONLY-NOT-SENT' not in request.get_data(as_text=True)
  assert 'password' not in request.form
  assert request.form['simulation_submission']=='confirmed'
 event(rid,'Submitted Data' if request.method=='POST' else 'Clicked Link');return pages[rid]
@engine.route('/report')
def report():
 rid=request.args['rid'];reports.append(rid);event(rid,'Email Reported');return '',204
engine_server=make_server('127.0.0.1',8188,engine);threading.Thread(target=engine_server.serve_forever,daemon=True).start()
for i,(category,brand,first,email,pw,trigger,filename) in enumerate(scenarios):
 cid='browser-live-'+str(i);targets[str(i)]=(cid,email)
 r=c.post('/admin/campaigns',headers=h,json={'campaign':{'id':cid,'name':brand+' browser fixture','category':category,'objective':'test_form_submission' if trigger=='test_form_submission' else 'link_interaction','source':'live','launched_at':(datetime.now(timezone.utc)-timedelta(seconds=2)).isoformat()},'recipients':[{'email':email,'rid':str(i)}]});assert r.status_code==200,r.text
 r=c.post('/admin/learning/bridge',headers=h,json={'campaign_id':cid,'trigger':trigger,'public_base':'http://127.0.0.1:8186'});assert r.status_code==200,r.text;pages[str(i)]=r.json()['landing_html']
 html=(root/'Member1/viva_templates'/filename).read_text().replace('{{.URL}}','http://127.0.0.1:8188/?rid='+str(i)).replace('{{.FirstName}}',first).replace('{{.Tracker}}','')
 msg=EmailMessage();msg['From']='practice@training.example.test';msg['To']=email;msg['Subject']=brand+' fixture';msg.set_content('Local browser test');msg.add_alternative(html,subtype='html')
 with smtplib.SMTP('127.0.0.1',8189) as transport:transport.send_message(msg)
 event(i,'Email Sent')
with sync_playwright() as playwright:
 browser=playwright.chromium.launch(headless=True,executable_path=os.environ.get('CHROMIUM_EXECUTABLE') or None,args=['--no-sandbox']+os.environ.get('CHROMIUM_ARGS','').split())
 for i,(category,brand,first,email,pw,trigger,filename) in enumerate(scenarios):
  page=browser.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  page.goto('http://127.0.0.1:8187/message/'+str(i));frame=page.frame_locator('iframe');frame.locator('a').first.wait_for();assert brand in frame.locator('body').inner_text()
  frame.locator('a').first.click()
  # The email link opens the landing page in the SAME tab (no new tab is created).
  page.wait_for_url('http://127.0.0.1:8188/**');landing_page=page;assert len(page.context.pages)==1;assert brand in landing_page.title()
  landing_page.on('dialog',lambda dialog:errors.append('Unexpected browser dialog'))
  if trigger=='test_form_submission':
   landing_page.fill('input[name=email]',email);landing_page.fill('input[type=password]','practice-ONLY-NOT-SENT')
   landing_page.click('button[type=submit]')
  landing_page.locator('#learningBanner:visible').wait_for()
  assert landing_page.url.startswith('http://127.0.0.1:8188/')
  assert landing_page.get_by_role('button',name='Cancel').count()==0
  if i==0:landing_page.screenshot(path=str(root.parent/'qa-banner.png'),full_page=True)
  # The banner is an overlay in front of the landing page, not a block above it.
  assert landing_page.evaluate("document.elementFromPoint(innerWidth/2,innerHeight/2).closest('#learningBanner')!==null")
  assert landing_page.locator('#learningWarning').inner_text()=='Warning'
  # 'Take the Quiz' opens the sign-in page in a NEW tab; the landing tab stays where it is.
  with landing_page.context.expect_page() as quiz_tab:landing_page.click('#learningContinue')
  page=quiz_tab.value
  assert landing_page.url.startswith('http://127.0.0.1:8188/') and len(landing_page.context.pages)==2
  page.wait_for_url('**/app/login.html#*');page.fill('#loginEmail',email);page.fill('#loginPassword',pw);page.click('button[type=submit]');page.wait_for_selector('#quizDialog[open]')
  cid='browser-live-'+str(i)
  with m.db() as db:
   assignment=db.execute('SELECT * FROM assignments WHERE campaign_id=? AND email=?',(cid,email)).fetchone();answers=[q[2] for q in m.questions(assignment)]
  for j,answer in enumerate(answers):page.check(f'input[name=q{j}][value="{answer}"]')
  page.locator('#quizForm button[type=submit]').click();page.locator("#quizResult").filter(has_text="100%").wait_for()
  assert not errors,errors
  with m.db() as db:assert db.execute('SELECT status FROM assignments WHERE id=?',(assignment['id'],)).fetchone()[0]=='passed'
  page.click('#closeQuiz');page.locator('#completedAssignments .learning-card').first.wait_for()
  assert page.locator(f'#completedAssignments [data-assignment-id="{assignment["id"]}"]').count()==1
  assert page.locator(f'#assignments [data-assignment-id="{assignment["id"]}"]').count()==0
  if i==0:
   page.screenshot(path=str(root.parent/'qa-employee.png'),full_page=True)
   page.set_viewport_size({'width':390,'height':844});page.screenshot(path=str(root.parent/'qa-mobile.png'),full_page=True)
   assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
  page.goto('http://127.0.0.1:8187/message/'+str(i));before_url=page.url;before_reports=len(reports)
  page.click('#reportPhishing');page.get_by_role('button',name='Phishing reported',exact=True).wait_for()
  assert page.url==before_url and len(reports)==before_reports+1
  assert reports[-1]==str(i)
  if i==0:page.screenshot(path=str(root.parent/'qa-mailbox.png'),full_page=True)
  print('PASS:',category,'SMTP inbox → visible email → landing → verified event → participant login → quiz → saved pass')
  page.close()
 page=browser.new_page(viewport={'width':1440,'height':1000});page.goto('http://127.0.0.1:8186/app/login.html');page.fill('#loginEmail','admin@example.test');page.fill('#loginPassword',creds['admin@example.test']);page.click('button[type=submit]');page.wait_for_selector('#metrics .metric');assert page.locator('#metrics .metric').count()==6
 page.screenshot(path=str(root.parent/'qa-admin.png'),full_page=True)
 page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
 browser.close()
smtp.stop();engine_server.shutdown();mailserver.shutdown()
