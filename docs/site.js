(function(){
var D=document,H=D.documentElement,$=function(s){return D.querySelector(s)},$$=function(s){return Array.prototype.slice.call(D.querySelectorAll(s))};
function L(){return H.getAttribute('data-lang')==='fa'?'fa':'en'}
var hooks=[];
function setLang(l){H.setAttribute('data-lang',l);H.lang=l;H.dir=l==='fa'?'rtl':'ltr';try{localStorage.setItem('mrz-lang',l)}catch(e){}
 $$('.lang button').forEach(function(b){b.setAttribute('aria-pressed',b.dataset.set===l?'true':'false')});
 D.title=l==='fa'?'dibs — ویرایش‌هایتان را رزرو کنید':'dibs — call dibs on your edits';hooks.forEach(function(f){f()})}
$$('.lang button').forEach(function(b){b.onclick=function(){setLang(b.dataset.set)}});
function esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}
function copyBtn(b,getText){b.addEventListener('click',function(){var t=getText();var done=function(){b.textContent='✓';b.classList.add('ok');setTimeout(function(){b.textContent='copy';b.classList.remove('ok')},1400)};
 if(navigator.clipboard){navigator.clipboard.writeText(t).then(done,done)}else{var a=D.createElement('textarea');a.value=t;D.body.appendChild(a);a.select();try{D.execCommand('copy')}catch(e){}a.remove();done()}})}
$$('.copy[data-copy]').forEach(function(b){copyBtn(b,function(){return b.dataset.copy})});
var reduce=window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches;

/* ---------- hero demo ---------- */
function hl(t){return esc(t).replace(/(&quot;|"[^"]*")/g,'<span class="st">$1</span>').replace(/\b(import|def|return)\b/g,'<span class="kw">$1</span>').replace(/\b(\d+)\b/g,'<span class="nu">$1</span>').replace(/\b(fetch|get|getLogger|info|json)\b/g,'<span class="fn">$1</span>')}
var V1=[['bot','import requests'],['bot',''],['bot','def fetch(url):'],['bot','    r = requests.get(url, timeout=10)'],['bot','    return r.json()']];
var USER='    r = requests.get(url, timeout=30, verify="ca.pem")';
var steps=[
 {cap:{en:'Claude writes fetch() with a 10 s timeout.',fa:'Claude تابع fetch را با مهلت ۱۰ ثانیه می‌نویسد.'}},
 {cap:{en:'You fix it by hand: 30 s, and your CA bundle.',fa:'شما دستی اصلاحش می‌کنید: ۳۰ ثانیه و فایل CA خودتان.'}},
 {cap:{en:'Next prompt. dibs hands Claude a brief of your edit.',fa:'درخواست بعدی. dibs خلاصهٔ ویرایش شما را به Claude می‌دهد.'}},
 {cap:{en:'Claude rewrites from memory… and dibs stops it.',fa:'Claude از حافظه بازنویسی می‌کند… و dibs جلویش را می‌گیرد.'}},
 {cap:{en:'Second try: logging added, your line kept.',fa:'تلاش دوم: لاگ اضافه شد و خط شما ماند.'}}];
var code=$('#code'),pt=$('#ptext'),brief=$('#brief'),stamp=$('#stamp'),cap=$('#cap'),stepn=$('#stepn'),cur=0,timers=[],typing=null;
function render(lines,extra){code.innerHTML=lines.map(function(l,i){var who=l[0],t=l[1],cls='ln'+(l[2]?' '+l[2]:'');
 var w=who==='you'?'<span class="who you">you</span>':who==='bot'?'<span class="who bot">claude</span>':'<span class="who"></span>';
 return '<div class="'+cls+'">'+w+'<span class="n">'+(i+1)+'</span><span class="t">'+(t?hl(t):' ')+(l[3]?'<span class="caret'+(who==='bot'?' bot':'')+'"></span>':'')+'</span></div>'}).join('')}
function T(f,ms){timers.push(setTimeout(f,ms))}
function clear(){timers.forEach(clearTimeout);timers=[];brief.classList.remove('on');stamp.classList.remove('on')}
function setCap(i){cur=i;stepn.textContent=(i+1)+'/5';cap.textContent=steps[i].cap[L()]}
hooks.push(function(){setCap(cur)});
function typeLine(lines,idx,who,text,ms,done){var n=0;var tick=function(){n++;var c=lines.slice();c[idx]=[who,text.slice(0,n),who==='you'?'hl':'',true];render(c);if(n<text.length)T(tick,ms);else done&&done()};tick()}
function play(){clear();
 setCap(0);pt.textContent='';render([]);
 var acc=[];V1.forEach(function(l,i){T(function(){acc.push([l[0],l[1],'new']);render(acc)},350+i*260)});
 T(function(){setCap(1);var base=V1.map(function(l){return [l[0],l[1]]});
  typeLine(base,3,'you',USER,reduce?0:32,function(){})},2800);
 T(function(){setCap(2);var c=V1.map(function(l){return [l[0],l[1]]});c[3]=['you',USER,'hl'];render(c);
  var p='add logging';var k=0;(function ty(){k++;pt.textContent=p.slice(0,k);if(k<p.length)T(ty,60)})();
  T(function(){brief.innerHTML='<b>[dibs]</b> Since your last turn, edited by the human, by hand:<br>• src/api.py (+1 −1, 12s ago)<br><span class="m">  - r = requests.get(url, timeout=10)</span><br><span class="p">  + r = requests.get(url, timeout=30, verify="ca.pem")</span><br>Build on these. Do not revert them.';brief.classList.add('on')},900)},6600);
 T(function(){setCap(3);brief.classList.remove('on');
  render([['bot','import logging','add'],['bot','import requests'],['bot',''],['bot','def fetch(url):'],['bot','    log.info("GET %s", url)','add'],['you',USER,'ghost'],['bot','    r = requests.get(url, timeout=10)','add'],['bot','    return r.json()']]);
  T(function(){stamp.classList.add('on')},700)},11200);
 T(function(){setCap(4);stamp.classList.remove('on');
  render([['bot','import logging','new'],['bot','import requests'],['bot',''],['bot','def fetch(url):'],['bot','    log.info("GET %s", url)','new'],['you',USER,'hl'],['bot','    return r.json()']]);
  pt.textContent='add logging  ✓'},15600);
 if(!reduce)T(play,22000)}
$('#replay').onclick=play;play();

/* ---------- playground ---------- */
var TRIV=/^[\s{}\[\]();,:.\-*\/#<>"'`|=+!?\\]*$/,TW={'else':1,'else:':1,'end':1,'fi':1,'done':1,'pass':1,'return':1,'break':1,'continue':1,'try:':1,'finally:':1,'}':1,'};':1,']':1,')':1,'});':1,'</div>':1,'<div>':1,'"""':1,"'''":1};
function key(l){return l.trim().split(/\s+/).join(' ')}
function sig(l){var k=key(l);return k.length>=3&&!TRIV.test(k)&&!TW[k]}
function cnt(lines){var m={};lines.forEach(function(l){var k=key(l);m[k]=(m[k]||0)+1});return m}
function delta(a,b){var A=cnt(a),B=cnt(b),add={},rem={};Object.keys(B).forEach(function(k){var d=B[k]-(A[k]||0);if(d>0)add[k]=d});Object.keys(A).forEach(function(k){var d=A[k]-(B[k]||0);if(d>0)rem[k]=d});return{add:add,rem:rem}}
function split(s){return s.replace(/\r\n/g,'\n').replace(/\n$/,'').split('\n')}
var P={
 revert:['import requests\n\ndef fetch(url):\n    r = requests.get(url, timeout=10)\n    return r.json()','import requests\n\ndef fetch(url):\n    r = requests.get(url, timeout=30, verify="ca.pem")\n    return r.json()','import logging\nimport requests\n\nlog = logging.getLogger(__name__)\n\ndef fetch(url):\n    log.info("GET %s", url)\n    r = requests.get(url, timeout=10)\n    return r.json()'],
 build:['import requests\n\ndef fetch(url):\n    r = requests.get(url, timeout=10)\n    return r.json()','import requests\n\ndef fetch(url):\n    r = requests.get(url, timeout=30, verify="ca.pem")\n    return r.json()','import logging\nimport requests\n\nlog = logging.getLogger(__name__)\n\ndef fetch(url):\n    log.info("GET %s", url)\n    r = requests.get(url, timeout=30, verify="ca.pem")\n    return r.json()'],
 resurrect:['DEBUG = True\nPAYMENTS_URL = "https://sandbox.pay.example"\nRETRIES = 3','PAYMENTS_URL = "https://pay.example"\nRETRIES = 3','DEBUG = True\nPAYMENTS_URL = "https://pay.example"\nRETRIES = 5']};
var pA=$('#pA'),pB=$('#pB'),pC=$('#pC'),vd=$('#verdict');
function judge(){var a=split(pA.value),b=split(pB.value),c=split(pC.value);
 var h=delta(a,b),C=cnt(c),B=cnt(b),dropped=[],res=[];
 Object.keys(h.add).forEach(function(k){if(sig(k)&&(C[k]||0)<(B[k]||0))dropped.push(k)});
 Object.keys(h.rem).forEach(function(k){if(sig(k)&&!(B[k])&&(C[k]||0)>0)res.push(k)});
 var fa=L()==='fa',out;
 if(!Object.keys(h.add).length&&!Object.keys(h.rem).length){vd.className='verdict';out='<h4>'+(fa?'شما چیزی تغییر نداده‌اید.':'You haven\'t changed anything yet.')+'</h4>'+(fa?'جعبهٔ دوم را ویرایش کنید تا ببینید نگهبان چه چیزی را حفظ می‌کند.':'Edit box 2 to see what the guard protects.')}
 else if(dropped.length||res.length){vd.className='verdict bad';
  var p='dibs: this edit to api.py would undo changes the human made by hand.\n';
  if(dropped.length)p+='It removes lines the human added or changed:\n'+dropped.map(function(k){return '<span class="p">  + '+esc(k)+'</span>'}).join('\n')+'\n';
  if(res.length)p+='It brings back lines the human deleted:\n'+res.map(function(k){return '<span class="m">  - '+esc(k)+'</span>'}).join('\n')+'\n';
  p+='Keep the human\'s version and make your change around it.\nOnly if the user asked for it: run `dibs allow api.py` and retry.';
  out='<h4>✗ '+(fa?'رد شد (Claude Code از شما می‌پرسد)':'Blocked (Claude Code asks you instead)')+'</h4><pre>'+p+'</pre>'}
 else{vd.className='verdict good';var n=0;Object.keys(delta(b,c).add).forEach(function(){n++});
  out='<h4>✓ '+(fa?'مجاز: ویرایش شما حفظ شده است':'Allowed: your edit survives')+'</h4>'+(fa?'ایجنت روی نسخهٔ شما ساخته است. ':'The agent built on your version. ')+'<span class="mono">'+n+(fa?' خط جدید':' new line(s)')+'</span>'}
 vd.innerHTML=out}
function preset(n){pA.value=P[n][0];pB.value=P[n][1];pC.value=P[n][2];$$('.presets button').forEach(function(b){b.setAttribute('aria-pressed',b.dataset.preset===n?'true':'false')});judge()}
$$('.presets button').forEach(function(b){b.onclick=function(){preset(b.dataset.preset)}});
[pA,pB,pC].forEach(function(t){t.addEventListener('input',judge)});preset('revert');hooks.push(judge);

/* ---------- agents ---------- */
var AG=[
 ['Claude Code','#d97757','.claude/settings.json',{b:['y','UserPromptSubmit'],g:['y',{en:'asks you',fa:'از شما می‌پرسد'}],r:['y','Edit · Write · Bash']}],
 ['Codex CLI','#10a37f','.codex/hooks.json + AGENTS.md',{b:['y','UserPromptSubmit'],g:['y',{en:'denies',fa:'رد می‌کند'}],r:['y','apply_patch · Bash']}],
 ['Cursor','#7c8cff','.cursor/hooks.json + rules/dibs.mdc',{b:['p',{en:'after 1st tool call',fa:'پس از اولین ابزار'}],g:['y',{en:'denies',fa:'رد می‌کند'}],r:['y','afterFileEdit · shell']}],
 ['Gemini CLI','#4f8dff','.gemini/settings.json',{b:['y','BeforeAgent'],g:['y',{en:'denies',fa:'رد می‌کند'}],r:['y','write_file · replace']}],
 ['GitHub Copilot','#e6e6e6','.vscode/mcp.json + copilot-instructions.md',{b:['p','MCP dibs_brief'],g:['p','MCP dibs_check_edit'],r:['p','MCP dibs_done']}],
 ['Aider & others','#ffd43b','AGENTS.md · dibs run --agent aider -- aider',{b:['p',{en:'printed at start',fa:'در شروع چاپ می‌شود'}],g:['p',{en:'after the fact',fa:'پس از وقوع'}],r:['y',{en:'whole run',fa:'کل اجرا'}]}]];
var RL={b:{en:'Brief',fa:'خلاصه'},g:{en:'Guard',fa:'نگهبان'},r:{en:'Records',fa:'ثبت'}};
function tx(v){return typeof v==='string'?v:v[L()]}
function agents(){$('#aglist').innerHTML=AG.map(function(a){return '<div class="ag rv in"><h3><span class="dot" style="background:'+a[1]+'"></span>'+a[0]+'</h3><div class="via">'+esc(a[2])+'</div><ul>'+['b','g','r'].map(function(k){return '<li><span>'+tx(RL[k])+'</span><b class="'+a[3][k][0]+'">'+esc(tx(a[3][k][1]))+'</b></li>'}).join('')+'</ul></div>'}).join('')}
agents();hooks.push(agents);

/* ---------- status terminal ---------- */
var TL=['<span class="d">$</span> dibs status','<span class="h">dibs · ~/shop  (feat/checkout)</span>','','<span class="h">Sync</span>','  <span class="w">!</span> 3 files not committed (2 modified, 1 untracked)','  <span class="w">!</span> 2 commits on feat/checkout never pushed (no upstream)','  <span class="w">!</span> 1 stash','','<span class="h">Agents</span>','  <span class="b">claude</span>   idle       last turn ended 4m ago  · up to date with your edits','  <span class="b">cursor</span>   idle       last turn ended 1h ago  · <span class="w">2 changes since its last turn</span>','','<span class="h">Reverted human lines</span>','  <span class="r">#14</span> api.py by cursor 1h ago: r = requests.get(url, timeout=30, verify="ca.pem")','      → <span class="g">dibs restore api.py</span>    (or `dibs ack 14` if it was wanted)','','<span class="h">Recent changes</span>','  #12   10-09 16:02  <span class="y">human </span>   M api.py +1 −1','  #13   10-09 16:05  <span class="b">claude</span>   M cart.py +18 −2','  #14   10-09 16:40  <span class="b">cursor</span>   M api.py +5 −1  <span class="r">REVERTED HUMAN LINES</span>','  #15   10-09 17:31  <span class="y">human </span>   A notes.md +6'];
var tout=$('#tout'),played=false;
function term(){if(played)return;played=true;if(reduce){tout.innerHTML=TL.join('\n');return}var i=0;(function n(){tout.innerHTML=TL.slice(0,++i).join('\n')+(i<TL.length?'\n<span class="caret"></span>':'');if(i<TL.length)setTimeout(n,i===1?500:110)})()}

/* ---------- install tabs ---------- */
var TABS=['<span class="c"># recommended</span>\npipx install git+https://github.com/mrzroot/dibs\ncd your-repo && dibs init',
'uv tool install git+https://github.com/mrzroot/dibs\ncd your-repo && dibs init',
'<span class="c"># wheel from the GitHub release</span>\npip install https://github.com/mrzroot/dibs/releases/download/v0.1.0/dibs-0.1.0-py3-none-any.whl\ncd your-repo && dibs init',
'git clone https://github.com/mrzroot/dibs && cd dibs\npip install -e .\ncd ../your-repo && dibs init'];
var tc=$('#tabcode');function tab(i){tc.innerHTML=TABS[i];$$('.tabs button').forEach(function(b){b.setAttribute('aria-selected',b.dataset.tab==i?'true':'false')})}
$$('.tabs button').forEach(function(b){b.onclick=function(){tab(+b.dataset.tab)}});tab(0);
copyBtn($('#tabcopy'),function(){return tc.textContent.split('\n').filter(function(l){return l&&l[0]!=='#'}).join('\n')});

/* ---------- commands ---------- */
var CM=[['dibs init','wire hooks for the agents in this repo','هوک ایجنت‌های این مخزن را وصل می‌کند'],['dibs status','sync, agents, reverted lines, recent changes','همگام‌سازی، ایجنت‌ها، خطوط برگشته، تغییرات اخیر'],['dibs sync','uncommitted / unpushed / no remote','کامیت‌نشده / پوش‌نشده / بدون ریموت'],['dibs log --diff','journal of every change and its author','دفتر همهٔ تغییرات و نویسنده‌شان'],['dibs blame FILE','who wrote each line: you or which agent','هر خط را چه کسی نوشته: شما یا کدام ایجنت'],['dibs restore FILE','put back only your reverted lines','فقط خطوط برگشتهٔ شما را بازمی‌گرداند'],['dibs ack N','accept a revert as intended','یک بازگشت را عمدی اعلام می‌کند'],['dibs allow FILE','let agents change your lines for 10 min','۱۰ دقیقه اجازهٔ تغییر خطوط شما را می‌دهد'],['dibs brief --agent A','start a turn and print the brief','نوبت را شروع و خلاصه را چاپ می‌کند'],['dibs run --agent A -- cmd','wrap any CLI agent in a turn','هر ایجنت خط فرمانی را در یک نوبت می‌پیچد'],['dibs mcp','MCP server for any MCP client','سرور MCP برای هر کلاینت MCP'],['dibs uninstall','remove only what dibs added','فقط چیزهایی را که dibs اضافه کرده حذف می‌کند']];
function cmds(){var f=L()==='fa';$('#cmdlist').innerHTML=CM.map(function(c){return '<div><code>'+esc(c[0])+'</code><span>'+(f?c[2]:c[1])+'</span></div>'}).join('')}
cmds();hooks.push(cmds);

/* ---------- comparison ---------- */
var CH={y:'<span class="y">✓</span>',p:'<span class="p">◐</span>',n:'<span class="n">✗</span>'};
var CT={h:{en:['','dibs','git-ai · Agent Blame','agentdiff','agentrec · flashpoint','Editor checkpoints'],fa:['','dibs','git-ai · Agent Blame','agentdiff','agentrec · flashpoint','چک‌پوینت ویرایشگر']},
r:[[{en:'Tells the agent what you changed since its last turn',fa:'به ایجنت می‌گوید از نوبت قبلش چه تغییر داده‌اید'},'y','n','n','p','n'],
[{en:'Blocks an edit that undoes your lines, before it lands',fa:'ویرایشی را که خطوط شما را برمی‌گرداند پیش از اعمال متوقف می‌کند'},'y','n','n','n','n'],
[{en:'Restores only your lines, keeps the agent\'s other work',fa:'فقط خطوط شما را برمی‌گرداند و بقیهٔ کار ایجنت می‌ماند'},'y','n','n','p','n'],
[{en:'Line attribution: human vs which agent',fa:'انتساب خط: انسان یا کدام ایجنت'},'y','y','y','p','n'],
[{en:'Uncommitted / unpushed / no-remote warnings',fa:'هشدار کامیت‌نشده / پوش‌نشده / بدون ریموت'},'y','n','n','n','n'],
[{en:'Works across several agents in one repo',fa:'با چند ایجنت در یک مخزن کار می‌کند'},'y','y','n','p','n'],
[{en:'Survives in git history (notes)',fa:'در تاریخچهٔ گیت می‌ماند (notes)'},'n','y','y','n','n']]};
function cmp(){var l=L();$('#cmp').innerHTML='<thead><tr>'+CT.h[l].map(function(h){return '<th>'+h+'</th>'}).join('')+'</tr></thead><tbody>'+CT.r.map(function(r){return '<tr><td>'+r[0][l]+'</td>'+r.slice(1).map(function(c,i){return '<td'+(i===0?' class="us"':'')+'>'+CH[c]+'</td>'}).join('')+'</tr>'}).join('')+'</tbody>'}
cmp();hooks.push(cmp);

/* ---------- faq ---------- */
var FQ=[
[{en:'Does anything leave my machine?',fa:'آیا چیزی از دستگاه من خارج می‌شود؟'},{en:'No. The journal and file snapshots live in <code>.git/dibs</code> (or <code>.dibs/</code> outside git). dibs makes no network calls; <code>dibs sync --fetch</code> only runs <code>git fetch</code> when you ask.',fa:'خیر. دفتر و نسخه‌های فایل در <code>.git/dibs</code> (یا <code>.dibs/</code> بیرون از گیت) ذخیره می‌شوند. dibs هیچ تماس شبکه‌ای ندارد و <code>dibs sync --fetch</code> فقط وقتی بخواهید <code>git fetch</code> اجرا می‌کند.'}],
[{en:'How does it know an edit was mine?',fa:'از کجا می‌فهمد ویرایش مال من بوده؟'},{en:'Agents edit inside turns that hooks mark. Anything that changed between an agent\'s turns, and was not written by another agent\'s turn, is yours. If two agents are active at once, the change is labelled <code>unknown</code> and protected the same way.',fa:'ایجنت‌ها در نوبت‌هایی ویرایش می‌کنند که هوک‌ها مشخص می‌کنند. هر چیزی که بین نوبت‌های ایجنت تغییر کرده و کار نوبت ایجنت دیگری نبوده، مال شماست. اگر دو ایجنت همزمان فعال باشند، تغییر <code>unknown</code> علامت می‌خورد و به همان شکل محافظت می‌شود.'}],
[{en:'What if I really want the agent to change my line?',fa:'اگر واقعاً بخواهم ایجنت خط مرا تغییر دهد؟'},{en:'Say so in the prompt. The agent (or you) runs <code>dibs allow FILE</code>, which lifts protection for 10 minutes. Claude Code simply asks you to approve.',fa:'در درخواست بگویید. ایجنت (یا خودتان) <code>dibs allow FILE</code> را اجرا می‌کند و محافظت ۱۰ دقیقه برداشته می‌شود. در Claude Code فقط از شما تأیید خواسته می‌شود.'}],
[{en:'Will the guard block every edit near my code?',fa:'آیا نگهبان هر ویرایشی نزدیک کد من را رد می‌کند؟'},{en:'No. It only looks at your significant lines from the last 72 hours (braces, <code>pass</code>, blank lines are ignored) and only triggers when an edit removes a line you added or re-adds one you deleted.',fa:'خیر. فقط خطوط معنادار شما در ۷۲ ساعت اخیر را بررسی می‌کند (آکولاد، <code>pass</code> و خط خالی نادیده گرفته می‌شوند) و فقط وقتی فعال می‌شود که ویرایشی خطی را که اضافه کرده‌اید حذف کند یا خط حذف‌شده‌ای را برگرداند.'}],
[{en:'What about edits through the shell, like sed or a script?',fa:'ویرایش از طریق شل، مثل sed یا یک اسکریپت چه؟'},{en:'They cannot be stopped in advance, but they are caught after the command: the agent is told in the same turn, and <code>dibs status</code> lists the revert with a <code>dibs restore</code> hint. The pre-commit hook also refuses to commit unresolved reverts.',fa:'از قبل قابل توقف نیستند، اما پس از اجرای دستور شناسایی می‌شوند: در همان نوبت به ایجنت گفته می‌شود و <code>dibs status</code> بازگشت را با راهنمای <code>dibs restore</code> نشان می‌دهد. هوک pre-commit هم کامیت بازگشت‌های حل‌نشده را رد می‌کند.'}],
[{en:'Does a hook failure break my agent?',fa:'آیا خطای هوک ایجنت را از کار می‌اندازد؟'},{en:'No. Every hook fails open: on any error it allows the action and writes the details to <code>.git/dibs/hook-errors.log</code>.',fa:'خیر. همهٔ هوک‌ها در صورت خطا اجازه می‌دهند و جزئیات را در <code>.git/dibs/hook-errors.log</code> می‌نویسند.'}],
[{en:'Do teammates need dibs installed?',fa:'آیا هم‌تیمی‌ها هم باید dibs نصب کنند؟'},{en:'No. If you commit the hook configs, agents without dibs on PATH report a failing hook and carry on, and the pre-commit line skips itself.',fa:'خیر. اگر تنظیمات هوک را کامیت کنید، ایجنت‌هایی که dibs ندارند یک هوک ناموفق گزارش می‌کنند و ادامه می‌دهند و خط pre-commit هم خودش را رد می‌کند.'}],
[{en:'How is this different from checkpoints or git-ai?',fa:'چه فرقی با چک‌پوینت‌ها یا git-ai دارد؟'},{en:'Checkpoints roll back a whole turn, after you notice. git-ai and Agent Blame record authorship in git notes at commit time. dibs works inside the session: it briefs the agent, guards the edit, and restores only your lines.',fa:'چک‌پوینت‌ها کل یک نوبت را پس از اینکه متوجه شدید برمی‌گردانند. git-ai و Agent Blame نویسندگی را هنگام کامیت در git notes ثبت می‌کنند. dibs در حین کار عمل می‌کند: به ایجنت خلاصه می‌دهد، ویرایش را کنترل می‌کند و فقط خطوط شما را برمی‌گرداند.'}]];
function faq(){var l=L();var open=$$('#faqlist details').map(function(d){return d.open});$('#faqlist').innerHTML=FQ.map(function(q,i){return '<details'+(open[i]||(!open.length&&i===0)?' open':'')+'><summary>'+q[0][l]+'</summary><p>'+q[1][l]+'</p></details>'}).join('')}
faq();hooks.push(faq);

/* ---------- reveal ---------- */
if('IntersectionObserver' in window){var io=new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting){e.target.classList.add('in');if(e.target.classList.contains('term'))term();io.unobserve(e.target)}})},{threshold:.15});$$('.rv').forEach(function(el){io.observe(el)})}else{$$('.rv').forEach(function(el){el.classList.add('in')});term()}
setLang(L());
})();
