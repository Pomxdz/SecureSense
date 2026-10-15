'use strict';
const $=id=>document.getElementById(id);
let user=null, data=null, activeQuiz=null, activeQuizQuestionCount=0, refreshTimer=null, editingQuizQuestionId=null;
const names={reported_before_interaction:'Reported before interaction',reported_before_then_interacted:'Reported first, later interacted',clicked_then_reported:'Clicked then reported',submitted_then_reported:'Submitted then reported',test_form_submitted:'Test-form submission',clicked_only:'Clicked without observed report',no_observed_interaction:'No observed interaction',pending:'Pending'};
function el(tag,text='',cls=''){const n=document.createElement(tag);if(text!==null)n.textContent=String(text);if(cls)n.className=cls;return n;}
function replace(id,...nodes){$(id).replaceChildren(...nodes);}
function button(text,action,cls='secondary small-btn'){const n=el('button',text,cls);n.type='button';n.addEventListener('click',action);return n;}
function badge(text){return el('span',text,'badge '+(text==='practice'?'practice':text==='passed'?'green':''));}
function chip(text,cls=''){return el('span',text,'chip'+(cls?' '+cls:''));}
function riskLevel(score){return score>=67?'high':score>=34?'mid':'low';}
const RISK_LABEL={low:'Low risk',mid:'Medium risk',high:'High risk'};
function scorePill(score){const lvl=score===null||score===undefined?'none':riskLevel(score);return el('span',lvl==='none'?'No score':String(Math.round(score)),'score-pill '+lvl);}
function empty(text='No evidence available for this selection.'){return el('p',text,'empty');}
function fmtRate(r){return r&&r.percent!==null?`${r.percent}%`:'Not assessed';}
function rateCell(r){const n=el('div',fmtRate(r));if(r)n.append(el('small',`${r.n} / ${r.denominator} observations`));if(r?.interval)n.append(el('small',`95% interval ${r.interval[0]}–${r.interval[1]}%`));return n;}
function when(s){return s?new Date(s).toLocaleString():'Not recorded';}
function label(s){return names[s]||s;}
function table(headers,rows){if(!rows.length)return empty();const wrap=el('div',null,'table-wrap'),t=el('table'),head=el('thead'),tr=el('tr');headers.forEach(x=>tr.append(el('th',x)));head.append(tr);t.append(head);const body=el('tbody');const extras=[];rows.forEach((row,index)=>{const tr=el('tr');if(rows.length>8&&index>=6){tr.classList.add('hidden');extras.push(tr);}row.forEach(v=>{const td=el('td');td.append(v instanceof Node?v:el('span',v));tr.append(td);});body.append(tr);});t.append(body);wrap.append(t);if(extras.length){let expanded=false;wrap.append(button(`Show all ${rows.length} records`,e=>{expanded=!expanded;extras.forEach(tr=>tr.classList.toggle('hidden',!expanded));e.currentTarget.textContent=expanded?'Show first 6 records':`Show all ${rows.length} records`;}));}return wrap;}
async function api(path,options={}){const headers={...(options.headers||{})};const token=sessionStorage.getItem('securesenseToken');if(token)headers.Authorization=`Bearer ${token}`;if(options.body)headers['Content-Type']='application/json';const r=await fetch(path,{...options,headers});if(r.status===401&&document.body.dataset.page!=='login'){sessionStorage.removeItem('securesenseToken');location.href='login.html';throw new Error('Please sign in again.');}if(!r.ok){let msg=`Request failed (${r.status})`;try{const d=await r.json();msg=typeof d.detail==='string'?d.detail:msg;}catch(_){}throw new Error(msg);}return r;}
async function json(path,options){return (await api(path,options)).json();}
function showError(e){const box=$('error');if(box){box.textContent=e.message;box.classList.remove('hidden');}}
function clearError(){if($('error'))$('error').classList.add('hidden');}
function filters(){const p=new URLSearchParams();['source','department','campaign','category','difficulty','start','end'].forEach(k=>{if($(k)?.value)p.set(k,$(k).value);});return p.toString();}
function select(id,items,first){const node=$(id),old=node.value;node.replaceChildren(new Option(first,''));items.forEach(x=>node.add(new Option(typeof x==='string'?x:x.name,typeof x==='string'?x:x.id)));node.value=old;}
function metric(title,value,detail,accent=''){const n=el('div',null,'metric'+(accent?' accent-'+accent:''));n.append(el('div',title,'label'),el('div',value,'value'),el('small',detail));return n;}
function bar(text,count,total,color=''){const n=el('div',null,'bar-row');n.append(el('span',text));const track=el('div',null,'track'),fill=el('div',null,'fill '+color);fill.style.width=`${total?count/total*100:0}%`;track.append(fill);n.append(track,el('strong',count));return n;}
function trend(rows){if(!rows.length)return empty();const ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg');svg.setAttribute('viewBox','0 0 600 250');svg.setAttribute('class','chart');svg.setAttribute('role','img');svg.setAttribute('aria-label','Interaction and reporting rates by campaign');const mk=(tag,attrs,text)=>{const n=document.createElementNS(ns,tag);for(const[k,v]of Object.entries(attrs))n.setAttribute(k,v);if(text!==undefined)n.textContent=text;svg.append(n);return n;};for(let y=0;y<=100;y+=25){const py=205-y*1.7;mk('line',{x1:40,y1:py,x2:570,y2:py,stroke:'#e4edf5'});mk('text',{x:3,y:py+4},`${y}%`);}const step=500/Math.max(rows.length-1,1);['click_rate','report_rate'].forEach((key,j)=>{const color=j?'#0b9277':'#1672ce';const valid=rows.map((r,i)=>r[key].percent!==null?`${55+i*step},${205-r[key].percent*1.7}`:null).filter(Boolean);if(valid.length)mk('polyline',{points:valid.join(' '),fill:'none',stroke:color,'stroke-width':3});rows.forEach((r,i)=>{if(r[key].percent!==null){const dot=mk('circle',{cx:55+i*step,cy:205-r[key].percent*1.7,r:5,fill:color});const title=document.createElementNS(ns,'title');title.textContent=`${r.name}: ${r[key].percent}%, ${r.difficulty}, n=${r[key].denominator}`;dot.append(title);}});});rows.forEach((r,i)=>mk('text',{x:55+i*step,y:230,'text-anchor':'middle'},r.launched_at.slice(5,10)));return svg;}
async function loadDashboard(){clearError();try{const d=await json('/metrics?'+filters());await loadCampaignResults();data=d;select('department',d.filters.departments,'All departments');select('campaign',d.filters.campaigns,'All campaigns');select('category',d.filters.categories,'All categories');select('difficulty',d.filters.difficulties,'All difficulties');replace('sourceNotice',el('strong',d.source==='practice'?'Practice records: ':'Live campaigns: '),el('span',d.source==='practice'?'sample data for demonstration.':'based on synchronised simulation results.'));
const pct=r=>r&&r.percent!==null?`${r.percent}% of delivered emails`:'No delivered emails yet';
replace('metrics',
 metric('People included',d.participants,'In the selected campaigns','info'),
 metric('Emails delivered',d.sent_observations,'Simulation emails sent','info'),
 metric('Clicked a link',d.click_rate.n,pct(d.click_rate),'warn'),
 metric('Entered credentials',d.submission_rate.n,pct(d.submission_rate),'danger'),
 metric('Reported phishing',d.report_rate.n,pct(d.report_rate),'good'),
 metric('Quizzes passed',`${d.training_completion.n}/${d.training_completion.denominator}`,'Assigned quizzes completed','good'));
replace('dashboardSummary',d.sent_observations?`${d.click_rate.n} of ${d.sent_observations} delivered simulation emails led to a click and ${d.submission_rate.n} led to a form submission. ${Math.max(0,d.training_completion.denominator-d.training_completion.n)} quizzes are still to be passed.`:'No delivered simulation emails match these filters. Choose another campaign or data source.');

await loadProposalPanels();await loadQuizManager();
}catch(e){showError(e);}}
function assessmentNodes(assessments){return Object.entries(assessments).map(([source,a])=>{const box=el('section',null,'panel');box.append(badge(source),el('h3',a.assessed_outcomes?`${a.interactions} interaction${a.interactions===1?'':'s'} in ${a.campaigns} campaign${a.campaigns===1?'':'s'}`:'No assessed outcomes yet'));a.explanation.forEach(x=>box.append(el('p',x)));box.append(el('small',`${a.coverage} evidence coverage. Counts only: the risk score comes from the AI section.`));return box;});}
function historyNodes(history,reflection=false){if(!history.length)return[empty('No simulation data available.')];return history.map(h=>{const box=el('article',null,'assignment');box.append(badge(h.source),el('h3',h.campaign),el('p',`${h.category} · ${h.difficulty} · ${label(h.journey)}`));const timeline=el('div',null,'timeline');h.events.forEach(e=>timeline.append(el('p',`${e.action.replaceAll('_',' ')} · ${when(e.time)} · ${e.quality}`)));box.append(timeline);box.append(el('small',`Time since send: click ${h.time_to_click??'unknown'} seconds; report ${h.time_to_report??'unknown'} seconds.`));if(reflection){const pick=el('select');pick.setAttribute('aria-label','Optional reason the message seemed believable');pick.add(new Option('Optional: what made this seem believable?',''));['urgency','familiar_sender','work_relevance','reward','uncertainty','other'].forEach(r=>pick.add(new Option(r.replaceAll('_',' '),r)));box.append(pick,button('Save reflection',async()=>{if(!pick.value)return;try{await json('/reflections',{method:'POST',body:JSON.stringify({campaign_id:h.campaign_id,reason:pick.value})});pick.disabled=true;}catch(e){showError(e);}}));}return box;});}
async function openProfile(email){try{const p=await json('/user/'+encodeURIComponent(email));const n=el('div');n.append(el('h3',`${p.user.name} · ${p.user.department}`));assessmentNodes(p.assessments).forEach(x=>n.append(x));const aiScores=await json('/ai/assessments/'+encodeURIComponent(email));Object.entries(aiScores).forEach(([source,a])=>{n.append(el('h3',`${source}: AI risk score ${a.score===null||a.score===undefined?'not available':Math.round(a.score)+'/100 ('+RISK_LABEL[riskLevel(a.score)]+')'}`),el('p',`Status: ${String(a.status).replaceAll('_',' ')}${a.stale?' (evidence changed)':''}. Model: ${a.model||'not configured'}`),el('p',a.explanation||'No verified model response.'),el('small',`Generated ${when(a.finished_at)}. Experimental estimate, not a compromise probability.`));});n.append(button('Run AI risk score',async()=>{const selectedSource=$('source')?.value||'live';await json('/admin/ai/assessments/'+encodeURIComponent(email)+'?source='+encodeURIComponent(selectedSource),{method:'POST'});await openProfile(email);}));n.append(el('h3','Event timeline'));historyNodes(p.history).forEach(x=>n.append(x));replace('profileContent',n);$('profileDialog').showModal();}catch(e){showError(e);}}
let highlightedAssignment=null;
async function loadEmployee(){
 clearError();
 try {
  const p=await json('/user/'+encodeURIComponent(user.email));
  $('welcome').textContent=`Hello, ${p.user.name.split(' ')[0]}`;
  const pending=p.assignments.filter(a=>a.status!=='passed').sort((a,b)=>new Date(b.assigned_at)-new Date(a.assigned_at));
  const completed=p.assignments.filter(a=>a.status==='passed');
  $('pendingCount').textContent=pending.length; $('completedCount').textContent=completed.length;
  replace('learningSummary',metric('To complete',pending.length,pending.length?'Your next quiz is ready below':'You’re all caught up'),metric('Completed',completed.length,'Quizzes passed'),metric('Your progress',`${p.assignments.length?Math.round(completed.length/p.assignments.length*100):0}%`,p.assignments.length?'Of assigned quizzes passed':'No quizzes assigned yet'));
  function card(a){
   const isDone=a.status==='passed', isNew=a.status==='assigned';
   const highlighted=a.id===highlightedAssignment || (!highlightedAssignment&&a.id===pending[0]?.id);
   const n=el('article',null,'assignment learning-card'+(isDone?' completed':highlighted?' featured':''));
   n.dataset.assignmentId=a.id;
   const tags=el('div',null,'card-tags');
   tags.append(badge(isDone?'Completed':isNew?'New assignment':a.status==='completed'?'Retry needed':'In progress'));
   if(a.source==='practice')tags.append(badge('practice'));
   if(!isDone&&a.due_at&&new Date(a.due_at)<new Date())tags.append(el('span','Overdue','badge overdue'));
   n.append(tags,el('h3',a.module));
   n.append(el('p',isDone?'Well done. Keep these skills fresh.':`Due ${new Date(a.due_at).toLocaleDateString(undefined,{day:'numeric',month:'short',year:'numeric'})}`));
   if(a.latest_result)n.append(el('p',`Latest score: ${a.latest_result.score}%${!a.latest_result.passed?' · Try again to reach 80%':''}`,'score-note'));
   n.append(button(isDone?'Review quiz':a.status==='completed'?'Try again':isNew?'Take the quiz':'Continue quiz',()=>openQuiz(a.id),isDone?'secondary':'primary'));
   return n;
  }
  replace('assignments',...(pending.length?pending.map(card):[empty('All caught up! No pending quizzes.')]));
  replace('completedAssignments',...(completed.length?completed.map(card):[empty('Your passed quizzes will appear here.')]));
  await loadReporting();await resolveLearningHandoff();
 }catch(e){showError(e);}
}
async function openQuiz(id){try{await json(`/training/${id}/start`,{method:'POST'});const q=await json(`/training/${id}`);activeQuiz=id;activeQuizQuestionCount=q.questions.length;$('quizTitle').textContent=q.module;replace('lesson',...q.lesson.map(x=>el('p',x)));const practice=el('section',null,'study-note');practice.append(el('h3','Optional Google Jigsaw practice'),el('p','Practice general phishing recognition with Google Jigsaw. This external exercise supplements your category-specific lesson.'));const practiceLink=el('a','Practice with Google Jigsaw');practiceLink.id='jigsawPractice';practiceLink.href='https://phishingquiz.withgoogle.com/?hl=en-GB';practiceLink.target='_blank';practiceLink.rel='noopener noreferrer';practiceLink.className='button';practice.append(practiceLink,el('p','Opens an external website and requires internet access. SecureSense cannot verify its results. Complete the quiz below to pass this assignment.'));$('lesson').append(practice);replace('quizForm');replace('quizResult');q.questions.forEach((question,i)=>{const field=el('fieldset');field.append(el('legend',`${i+1}. ${question.prompt}`));question.options.forEach((option,j)=>{const lab=el('label');const radio=el('input');radio.type='radio';radio.name=`q${i}`;radio.value=j;radio.required=true;lab.append(radio,document.createTextNode(option));field.append(lab);});$('quizForm').append(field);});const submit=el('button','Submit quiz');submit.type='submit';$('quizForm').append(submit);$('quizDialog').showModal();}catch(e){showError(e);}}
async function init(){const page=document.body.dataset.page;if(page==='login'){$('loginForm').addEventListener('submit',async e=>{e.preventDefault();const b=e.target.querySelector('button');b.disabled=true;try{const d=await json('/auth/login',{method:'POST',body:JSON.stringify({email:$('loginEmail').value,password:$('loginPassword').value})});sessionStorage.setItem('securesenseToken',d.token);const handoff=new URLSearchParams(location.hash.slice(1));if(handoff.has('ticket')&&handoff.has('rid'))sessionStorage.setItem('learningHandoff',JSON.stringify({ticket:handoff.get('ticket'),rid:handoff.get('rid')}));const reportUrl=handoff.get('reportUrl');const reportRid=handoff.get('reportRid')||(reportUrl?new URL(reportUrl,location.origin).searchParams.get('rid'):null);if(reportRid)sessionStorage.setItem('reportRid',reportRid);history.replaceState(null,'','login.html');location.href=reportRid?'employee.html#reporting':handoff.has('ticket')?'employee.html':d.user.role==='admin'?'admin.html':'employee.html';}catch(err){$('loginError').textContent=err.message;}finally{b.disabled=false;}});return;}
try{user=await json('/auth/me');if(['admin','settings'].includes(page)&&user.role!=='admin'){location.href='employee.html';return;}if(page==='employee'&&user.role==='admin'){location.href='admin.html';return;}}catch(e){showError(e);return;}
$('logout').addEventListener('click',async()=>{try{await api('/auth/logout',{method:'POST'});}finally{sessionStorage.removeItem('securesenseToken');location.href='login.html';}});
$('refresh').addEventListener('click',()=>page==='admin'?loadDashboard():page==='settings'?loadSettings():loadEmployee());
if(page==='settings'){await loadSettings();fillSample();$('endpoint').addEventListener('change',fillSample);$('requestForm').addEventListener('submit',async e=>{e.preventDefault();try{const path=$('endpoint').value;const payload=JSON.parse($('payload').value);const result=await json(path,{method:'POST',body:JSON.stringify(payload)});replace('requestResult',el('pre',JSON.stringify(result.landing_html?{campaign_id:result.campaign_id,expires:result.expires,trigger:result.trigger,instructions:result.instructions}:result,null,2)));if(result.landing_html)$('requestResult').append(button('Download campaign landing HTML',()=>{const url=URL.createObjectURL(new Blob([result.landing_html],{type:'text/html'}));const a=el('a');a.href=url;a.download='securesense_campaign_landing.html';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}));await loadSettings();}catch(err){replace('requestResult',el('p',err.message,'error-text'));}});return;}
if(page==='admin'){$('filters').addEventListener('submit',e=>{e.preventDefault();loadDashboard();});document.querySelectorAll('.segmented [data-source]').forEach(btn=>btn.addEventListener('click',()=>{if($('source').value===btn.dataset.source)return;$('source').value=btn.dataset.source;document.querySelectorAll('.segmented [data-source]').forEach(x=>x.setAttribute('aria-pressed',String(x===btn)));openRiskRows.clear();['department','campaign','category','difficulty','start','end'].forEach(k=>$(k).value='');loadDashboard();}));$('reset').addEventListener('click',()=>{['department','campaign','category','difficulty','start','end'].forEach(k=>$(k).value='');loadDashboard();});$('closeProfile').addEventListener('click',()=>$('profileDialog').close());$('export').addEventListener('click',async()=>{try{const r=await api('/admin/export.csv?'+filters());const url=URL.createObjectURL(await r.blob());const a=el('a');a.href=url;a.download='securesense_evidence.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}catch(e){showError(e);}});$('quizCategory').addEventListener('change',loadQuizManager);$('addQuizQuestion').addEventListener('click',()=>openQuizEditor());$('clearQuiz').addEventListener('click',clearSelectedQuiz);$('closeQuizEditor').addEventListener('click',()=>$('quizEditorDialog').close());$('cancelQuizEdit').addEventListener('click',()=>$('quizEditorDialog').close());$('quizEditorForm').addEventListener('submit',saveQuizQuestion);await loadDashboard();refreshTimer=setInterval(()=>{if(!document.hidden&&!$('profileDialog').open&&!$('quizEditorDialog').open&&!document.activeElement?.matches('input,select,textarea'))loadDashboard();},60000);}else{$('closeQuiz').addEventListener('click',()=>{$('quizDialog').close();loadEmployee();});$('quizForm').addEventListener('submit',async e=>{e.preventDefault();const b=e.target.querySelector('button');b.disabled=true;try{const f=new FormData(e.target),answers=Array.from({length:activeQuizQuestionCount},(_,i)=>Number(f.get('q'+i)));const d=await json(`/training/${activeQuiz}/submit`,{method:'POST',body:JSON.stringify({answers})});replace('quizResult',el('h3',`${d.score}% — ${d.passed?'Passed':'Review and retry'}`),...d.feedback.map((x,i)=>el('p',`${i+1}. ${x}`)));await loadEmployee();}catch(err){replace('quizResult',el('p',err.message,'error-text'));}finally{b.disabled=false;}});await loadEmployee();}}
document.addEventListener('DOMContentLoaded',init);

async function loadSettings(){try{const s=await json('/admin/status');const kv=el('div',null,'kv');Object.entries(s).forEach(([k,v])=>{const LABELS={webhook_configured:'Webhook',gophish_api_configured:'Gophish API',ai_configured:'AI scoring',database:'Database',schema_version:'Version'};const key=LABELS[k]||k.replaceAll('_',' ');kv.append(el('div',key[0].toUpperCase()+key.slice(1)));const val=el('div');val.append(typeof v==='boolean'?chip(v?'Configured':'Not configured',v?'yes-good':'yes-warn'):el('span',String(v)));kv.append(val);});replace('integrationStatus',kv);}catch(e){showError(e);}}

const REQUEST_SAMPLES={
  "/admin/campaigns": {
    "campaign": {
      "id": "REPLACE_WITH_GOPHISH_CAMPAIGN_ID",
      "name": "ShieldPay account security exercise",
      "category": "Credential Harvesting",
      "theme": "Account security",
      "objective": "test_form_submission",
      "persuasion": [
        "urgency",
        "authority"
      ],
      "identity": "IT support",
      "warning_signs": [
        "Unexpected request",
        "Unfamiliar destination domain"
      ],
      "difficulty": "moderate",
      "audience_relevance": "Reviewed for the fictional test audience",
      "source": "live",
      "launched_at": "REPLACE_WITH_CAMPAIGN_LAUNCH_ISO_TIMESTAMP"
    },
    "recipients": [
      {
        "email": "amali.perera@example.test",
        "name": "Amali Perera",
        "department": "Finance",
        "rid": "REPLACE_WITH_RID"
      }
    ]
  },
  "/admin/gophish/sync": {
    "campaign": {
      "id": "REPLACE_WITH_GOPHISH_CAMPAIGN_ID",
      "name": "ShieldPay account security exercise",
      "category": "Credential Harvesting",
      "theme": "Account security",
      "objective": "test_form_submission",
      "persuasion": [
        "urgency",
        "authority"
      ],
      "identity": "IT support",
      "warning_signs": [
        "Unexpected request",
        "Unfamiliar destination domain"
      ],
      "difficulty": "moderate",
      "audience_relevance": "Reviewed for the fictional test audience",
      "source": "live",
      "launched_at": "REPLACE_WITH_CAMPAIGN_LAUNCH_ISO_TIMESTAMP"
    },
    "departments": {
      "amali.perera@example.test": "Finance"
    }
  },
  "/admin/learning/bridge": {
    "campaign_id": "REPLACE_WITH_GOPHISH_CAMPAIGN_ID",
    "public_base": "http://127.0.0.1:8000",
    "trigger": "test_form_submission"
  },
  "/admin/users": {
    "email": "new.person@example.test",
    "name": "New Person",
    "department": "Finance",
    "password": "Choose-a-strong-password",
    "role": "employee"
  }
};
function fillSample(){const sample=REQUEST_SAMPLES[$('endpoint').value];$('payload').value=sample?JSON.stringify(sample,null,2):'';}
let aiPollTimer=null;const openRiskRows=new Set();
const AI_STATUS={pending:'Scoring with AI…',running:'Scoring with AI…',superseded:'Updating…',unassessed:'Waiting for activity',unavailable:'AI not configured',failed:'Scoring failed',not_requested:'Not scored yet',available:'Updating…'};
async function loadProposalPanels(){
const source=$('source').value;
const a=await json('/admin/ai/overview?source='+source);
clearTimeout(aiPollTimer);
const scored=a.people.filter(p=>p.status==='available'&&p.score!==null&&p.score!==undefined);
const counts={low:0,mid:0,high:0};scored.forEach(p=>counts[riskLevel(p.score)]++);
const average=el('div',null,'risk-average');
average.append(el('div','Average AI risk score','label'));
const big=el('div',a.mean===null?'No scores yet':String(a.mean),'big');if(a.mean!==null)big.append(el('small',' / 100'));average.append(big);
if(a.mean!==null){const scale=el('div',null,'risk-scale');const mark=el('i');mark.style.left=Math.min(100,Math.max(0,a.mean))+'%';scale.append(mark);average.append(scale,(()=>{const l=el('div',null,'risk-scale-labels');l.append(el('span','0 Low'),el('span','100 High'));return l;})());}
average.append(el('small',`${a.assessed} of ${a.people.length} people scored`));
const levels=el('div',null,'risk-levels');
[['high','High risk','67 to 100'],['mid','Medium risk','34 to 66'],['low','Low risk','0 to 33']].forEach(([k,t,range])=>{const c=el('div',null,'risk-level '+k);c.append(el('span',t),el('div',counts[k],'n'),el('small',`Scores ${range}`));levels.append(c);});
const summary=el('div',null,'risk-summary');summary.append(average,levels);
const config=el('p',a.configured?`AI scoring is on (model: ${a.configured_model}). New scores are created automatically after each simulation result.`:'AI scoring is off. Add GROQ_API_KEY and GROQ_MODEL to .env and restart SecureSense.',a.configured?'ai-config muted':'ai-config error-text');
const toolbar=el('div',null,'toolbar risk-toolbar');
toolbar.append(button('Score everyone now',async(e)=>{const b=e.currentTarget;b.disabled=true;try{for(const p of a.people){await json('/admin/ai/assessments/'+encodeURIComponent(p.email)+'?source='+encodeURIComponent(source),{method:'POST'});}await loadProposalPanels();}catch(err){showError(err);}finally{b.disabled=false;}},'secondary small-btn'));
const head=el('div',null,'risk-head');['Person','AI risk score','Risk level and status','Simulation results',''].forEach(t=>head.append(el('span',t)));
const list=el('div',null,'risk-list');list.append(head);
const sorted=[...a.people].sort((x,y)=>{const hx=x.score!==null&&x.score!==undefined&&x.status==='available',hy=y.score!==null&&y.score!==undefined&&y.status==='available';if(hx!==hy)return hx?-1:1;if(hx&&hy&&x.score!==y.score)return y.score-x.score;return x.name.localeCompare(y.name);});
let pending=false;
sorted.forEach(p=>{
 const has=p.status==='available'&&p.score!==null&&p.score!==undefined;
 const lvl=has?riskLevel(p.score):'none';
 if(['pending','running','superseded'].includes(p.status))pending=true;
 const row=el('article',null,'risk-row');
 const top=el('div',null,'risk-row-top');
 const person=el('div',null,'risk-person');person.append(el('strong',p.name),el('small',p.email));
 const score=el('div',null,'risk-score');score.append(scorePill(has?p.score:null));
 if(has){const bar=el('div',null,'score-bar'),fill=el('i',null,lvl);fill.style.width=Math.min(100,p.score)+'%';bar.append(fill);score.append(bar);}
 const state=el('div');
 if(has)state.append(el('div',RISK_LABEL[lvl],'risk-level-label '+lvl));
 else{state.append(el('div',AI_STATUS[p.status]||String(p.status).replaceAll('_',' '),'risk-level-label'));}
 if(p.status==='failed'&&p.error)state.append(el('small',p.error,'error-text'));
 const facts=el('div',null,'risk-facts');
 facts.append(el('span',`${p.interactions} clicked, ${p.submissions} submitted form, ${p.reports} reported`));
 const toggle=button(openRiskRows.has(p.email)?'Hide':'Details',()=>{const hidden=detail.hidden;detail.hidden=!hidden;toggle.textContent=hidden?'Hide':'Details';hidden?openRiskRows.add(p.email):openRiskRows.delete(p.email);},'secondary small-btn');
 top.append(person,score,state,facts,toggle);
 const detail=el('div',null,'risk-detail');detail.hidden=!openRiskRows.has(p.email);
 const grid=el('div',null,'risk-detail-grid');
 const why=el('div');why.append(el('h4','Why this score'),el('p',p.explanation||'No AI assessment yet.'));
 if(p.recommendation)why.append(el('h4','Recommended learning'),el('p',p.recommendation));
 if(p.status==='available'&&p.finished_at)why.append(el('small',`Scored ${when(p.finished_at)} by ${p.model||a.configured_model}`));
 grid.append(why);
 const actions=el('div',null,'ai-actions');
 actions.append(button(p.status==='failed'?'Retry AI score':has?'Re-run AI score':'Run AI score',async()=>{try{await json('/admin/ai/assessments/'+encodeURIComponent(p.email)+'?source='+encodeURIComponent(source),{method:'POST'});await loadProposalPanels();}catch(e){showError(e);}},'small-btn'));
 actions.append(button('Full profile',()=>openProfile(p.email),'secondary small-btn'));
 detail.append(grid,actions);
 row.append(top,detail);list.append(row);
});
replace('aiOverview',config,summary,toolbar,a.people.length?list:empty('No participants have recipient records in this data source yet.'),el('p',a.notice,'footnote'));
if(pending&&!document.hidden)aiPollTimer=setTimeout(()=>{if(document.body.dataset.page==='admin')loadProposalPanels().catch(()=>{});},5000);
}
async function loadQuizManager(){
 if(!$('quizManager'))return;
 try{
  const d=await json('/admin/quizzes');
  const current=$('quizCategory').value||d.selected_category;
  if(!$('quizCategory').options.length){d.categories.forEach(category=>$('quizCategory').add(new Option(category,category)));}
  if(!$('quizEditCategory').options.length){d.categories.forEach(category=>$('quizEditCategory').add(new Option(category,category)));}
  $('quizCategory').value=d.categories.includes(current)?current:d.selected_category;
  const category=$('quizCategory').value;
  const items=d.questions.filter(q=>q.category===category);
  $('quizManagerNotice').textContent=`${items.length} question${items.length===1?'':'s'} in ${category}. Pass mark: ${d.pass_percent}%. ${d.notice}`;
  if(!items.length){replace('quizManager',empty('This quiz has no questions. Add a question before employees can complete this category.'));return;}
  const cards=items.map((q,index)=>{
   const card=el('article',null,'quiz-admin-card');
   const heading=el('div',null,'quiz-admin-heading');heading.append(el('strong',`${index+1}. ${q.prompt}`));
   const actions=el('div',null,'ai-actions');
   actions.append(button('Edit',()=>openQuizEditor(q)));
   actions.append(button('Delete',async()=>{if(!confirm('Delete this quiz question? Historical attempt scores will remain unchanged.'))return;try{await json('/admin/quizzes/questions/'+q.id,{method:'DELETE'});await loadQuizManager();}catch(e){showError(e);}},'danger small-btn'));
   heading.append(actions);card.append(heading);
   const list=el('ol');q.options.forEach((option,i)=>{const item=el('li',option);if(i===q.correct_index)item.append(el('span',' Correct answer','badge green'));list.append(item);});card.append(list);
   return card;
  });
  replace('quizManager',...cards);
 }catch(e){showError(e);}
}
function openQuizEditor(question=null){
 editingQuizQuestionId=question?.id??null;
 $('quizEditorTitle').textContent=question?'Edit quiz question':'Add quiz question';
 $('quizEditCategory').value=question?.category||$('quizCategory').value;
 $('quizPrompt').value=question?.prompt||'';
 for(let i=0;i<4;i++)$('quizOption'+i).value=question?.options?.[i]||'';
 $('quizCorrect').value=String(question?.correct_index??0);
 $('quizEditorDialog').showModal();
 $('quizPrompt').focus();
}
async function saveQuizQuestion(event){
 event.preventDefault();clearError();
 const raw=[0,1,2,3].map(i=>$('quizOption'+i).value.trim());
 if(!raw[0]||!raw[1]){showError(new Error('Options A and B are required.'));return;}
 const firstBlank=raw.findIndex(x=>!x);if(firstBlank>=0&&raw.slice(firstBlank+1).some(Boolean)){showError(new Error('Quiz options must be consecutive from A onward.'));return;}
 const options=raw.filter(Boolean),correct_index=Number($('quizCorrect').value);
 if(correct_index>=options.length){showError(new Error('Choose a correct answer from the options you entered.'));return;}
 const payload={category:$('quizEditCategory').value,prompt:$('quizPrompt').value.trim(),options,correct_index};
 const submit=event.target.querySelector('button[type=submit]');submit.disabled=true;
 try{
  const path=editingQuizQuestionId?'/admin/quizzes/questions/'+editingQuizQuestionId:'/admin/quizzes/questions';
  await json(path,{method:editingQuizQuestionId?'PATCH':'POST',body:JSON.stringify(payload)});
  $('quizEditorDialog').close();$('quizCategory').value=payload.category;await loadQuizManager();
 }catch(e){showError(e);}finally{submit.disabled=false;}
}
async function clearSelectedQuiz(){
 const category=$('quizCategory').value;if(!category)return;
 if(!confirm(`Delete every question in the ${category} quiz? Employees assigned to this category will be unable to submit it until you add new questions.`))return;
 try{await json('/admin/quizzes/'+encodeURIComponent(category),{method:'DELETE'});await loadQuizManager();}catch(e){showError(e);}
}

async function resolveLearningHandoff(){
const raw=sessionStorage.getItem('learningHandoff');if(!raw)return;
try{const result=await json('/learning/handoff/resolve',{method:'POST',body:raw});
if(result.status==='ready'){$('learningStatus').classList.add('hidden');clearError();sessionStorage.removeItem('learningHandoff');highlightedAssignment=result.assignment_id;await loadEmployee();await openQuiz(result.assignment_id);}
else{$('learningStatus').textContent='Your quiz is being prepared. It will open automatically when ready. If this takes more than a minute, contact your training administrator.';$('learningStatus').classList.remove('hidden');setTimeout(()=>{if(document.body.dataset.page==='employee')resolveLearningHandoff();},5000);}
}catch(e){showError(e);}
}


async function loadReporting(){
 if(!document.getElementById('reportForm'))return;
 const options=await json('/reports/options');const pick=$('reportMessage');
 const old=pick.value;pick.replaceChildren(new Option('Select suspicious email',''));
 options.messages.forEach(m=>pick.add(new Option(m.name,m.rid)));
 pick.value=sessionStorage.getItem('reportRid')||old;
 if(sessionStorage.getItem('reportRid')){$('reporting').open=true;$('reporting').scrollIntoView();}
 if(pick.dataset.ready)return;pick.dataset.ready='true';
 $('reportForm').addEventListener('submit',async e=>{e.preventDefault();const b=e.target.querySelector('button');b.disabled=true;
 try{const result=await json('/reports/phishing',{method:'POST',body:JSON.stringify({rid:pick.value,reason:$('reportReason').value})});$('reportStatus').textContent=result.status==='already_reported'?'This email was already reported.':'Thank you. Your phishing report has been recorded.';sessionStorage.removeItem('reportRid');await loadEmployee();}
 catch(err){$('reportStatus').textContent=err.message;}finally{b.disabled=false;}});
}
async function loadCampaignResults(){
 const d=await json('/admin/campaign-results?'+filters());$('resultsNotice').textContent='Counts are per delivered simulation email. One person may receive several emails.';
 replace('resultDepartments',table(['Department','People','Clicked','Entered credentials','Reported','Quiz completed','Passed','Failed'],d.departments.map(x=>[x.department,x.participants,x.clicked,x.submitted,x.reported,x.completed,x.passed,x.failed])));
 replace('resultPeople',table(['Participant','Department','Campaign','Clicked link','Entered credentials','Reported','Quiz result'],d.results.map(x=>{const who=el('div');who.append(el('strong',x.name),el('small',x.email));const quiz=el('div');quiz.append(chip(x.quiz_result,x.quiz_result==='Passed'?'yes-good':x.quiz_result==='Failed'?'yes-bad':''));if(x.quiz_completed)quiz.append(el('small',`Latest ${x.quiz_score}%, ${x.attempts} attempt${x.attempts===1?'':'s'}`));return[who,x.department,x.campaign,x.clicked?chip('Clicked','yes-warn'):chip('No click'),x.submitted?chip('Yes','yes-bad'):chip('No'),x.reported?chip('Reported','yes-good'):chip('Not reported'),quiz];})));
 const graph=el('div',null,'department-grid');
 d.departments.forEach(x=>{const box=el('section',null,'department-card');box.append(el('h3',x.department),el('p',`${x.participants} ${x.participants===1?'person':'people'}, ${x.observations} delivered ${x.observations===1?'email':'emails'}`));box.append(bar('Clicked a link',x.clicked,x.observations,'orange'),bar('Entered credentials',x.submitted,x.observations,'red'),bar('Reported phishing',x.reported,x.observations,'green'),bar('Quizzes passed',x.passed,x.observations,''));graph.append(box);});
 replace('resultGraph',d.departments.length?graph:empty('No campaign records for this selection.'));
}

/* Sidebar: the clicked link becomes the highlighted one (same blue as the first item). */
(function(){
  const links=[...document.querySelectorAll('.sidebar nav a')];
  if(!links.length)return;
  const setActive=a=>links.forEach(x=>x.classList.toggle('active',x===a));
  links.forEach(a=>a.addEventListener('click',()=>setActive(a)));
  function fromHash(){
    if(!location.hash)return;
    const match=links.find(a=>(a.getAttribute('href')||'').endsWith(location.hash));
    if(match)setActive(match);
  }
  window.addEventListener('hashchange',fromHash);
  fromHash();
})();
