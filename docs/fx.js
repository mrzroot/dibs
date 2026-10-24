/* shared helpers for the per-project identity scripts (no dependencies) */
(function(){'use strict';
var d=document,R=d.documentElement;
var FX=window.FX={
 reduce:!!(window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches),
 $:function(s,c){return(c||d).querySelector(s)},
 $$:function(s,c){return Array.prototype.slice.call((c||d).querySelectorAll(s))},
 mouse:{x:-1e3,y:-1e3,px:.5,py:.5},
 /* add .rv and reveal on scroll */
 reveal:function(sel,cls){cls=cls||'in';var els=FX.$$(sel);els.forEach(function(e){e.classList.add('rv')});
  if(FX.reduce||!('IntersectionObserver' in window)){els.forEach(function(e){e.classList.add(cls)});return}
  var io=new IntersectionObserver(function(es){es.forEach(function(x){if(x.isIntersecting){x.target.classList.add(cls);io.unobserve(x.target)}})},{rootMargin:'0px 0px -6% 0px'});els.forEach(function(e,i){e.style.setProperty('--i',i%6);io.observe(e)})},
 /* canvas loop: sizes to its box, pauses offscreen / hidden tab; draw(ctx,w,h,t,dt,m) with m = mouse in canvas px */
 loop:function(cv,draw,o){o=o||{};var ctx=cv.getContext('2d'),w=0,h=0,dpr=1,raf=0,on=false,vis=true,last=0,t0=performance.now(),m={x:-1e3,y:-1e3,in:false};
  function size(){var r=cv.getBoundingClientRect();w=r.width;h=r.height;dpr=Math.min(o.dpr||2,window.devicePixelRatio||1);cv.width=Math.max(1,Math.round(w*dpr));cv.height=Math.max(1,Math.round(h*dpr));ctx.setTransform(dpr,0,0,dpr,0,0);if(o.resize)o.resize(w,h)}
  function fr(now){if(!on)return;var t=(now-t0)/1000,dt=Math.min(.05,(now-last)/1000||.016);last=now;ctx.setTransform(dpr,0,0,dpr,0,0);draw(ctx,w,h,t,dt,m);raf=requestAnimationFrame(fr)}
  function go(){if(on||FX.reduce||d.hidden||!vis)return;on=true;last=performance.now();raf=requestAnimationFrame(fr)}
  function stop(){on=false;cancelAnimationFrame(raf)}
  size();addEventListener('resize',function(){size();if(!on){ctx.setTransform(dpr,0,0,dpr,0,0);draw(ctx,w,h,0,0,m)}});
  var host=o.host||cv.parentElement;host.addEventListener('pointermove',function(e){var r=cv.getBoundingClientRect();m.x=e.clientX-r.left;m.y=e.clientY-r.top;m.in=true},{passive:true});host.addEventListener('pointerleave',function(){m.in=false;m.x=m.y=-1e3});
  if(FX.reduce){draw(ctx,w,h,o.still||2,0,m)}else{
   if('IntersectionObserver' in window)new IntersectionObserver(function(es){vis=es[0].isIntersecting;vis?go():stop()},{threshold:0}).observe(cv);else go();
   d.addEventListener('visibilitychange',function(){d.hidden?stop():go()});draw(ctx,w,h,0,0,m)}
  return{size:size,draw:function(){draw(ctx,w,h,(performance.now()-t0)/1000,0,m)},ctx:ctx};},
 /* create an absolutely positioned canvas as the first child of host */
 layer:function(host,cls){var cv=d.createElement('canvas');cv.className='fx '+(cls||'');cv.setAttribute('aria-hidden','true');cv.setAttribute('role','presentation');if(getComputedStyle(host).position==='static')host.style.position='relative';host.insertBefore(cv,host.firstChild);return cv},
 css:function(n){return getComputedStyle(R).getPropertyValue(n).trim()},
 rnd:function(a,b){return a+Math.random()*(b-a)},
 theme:function(){return R.getAttribute('data-theme')==='dark'?'dark':'light'}
};
addEventListener('pointermove',function(e){FX.mouse.x=e.clientX;FX.mouse.y=e.clientY;FX.mouse.px=e.clientX/innerWidth;FX.mouse.py=e.clientY/innerHeight},{passive:true});
R.classList.add('fxjs');
})();

(function(){var L=['def fetch(url, timeout=30):','    r = session.get(url,','        timeout=timeout,','        headers=HEADERS)','    if r.status_code != 200:','        raise FetchError(r)','    return r.json()','','RETRIES = 3','BACKOFF = 1.5','def retry(fn, n=RETRIES):','    for i in range(n):','        try: return fn()','        except IOError: sleep(BACKOFF**i)','    raise Timeout()','','class Client:','    def __init__(self, base):','        self.base = base.rstrip("/")','    def get(self, path):','        return fetch(self.base + path)'];
function ink(){return getComputedStyle(FX.$('.hero .side.you')).color}
var you=FX.$('.hero .side.you'),ai=FX.$('.hero .side.ai');if(!you||!ai)return;var RH=30;
/* YOU: code rows; random rows get highlighted then locked with a DIBS tag. Click a row to lock it. */
(function(){var cv=FX.layer(you),marks={},nxt=0,shift=0;
 FX.loop(cv,function(c,w,h,t,dt,m){c.clearRect(0,0,w,h);var rows=Math.ceil(h/RH),fs=w<600?12:15,col=ink(),hov=m.in?Math.floor(m.y/RH):-1;
  c.font='500 '+fs+'px JB,ui-monospace,monospace';c.textBaseline='middle';shift=Math.floor(t/7);
  if(t>nxt){nxt=t+.9;var r=Math.floor(Math.random()*rows);marks[r]={p:0,born:t};}
  for(var i=0;i<rows;i++){var y=i*RH+RH/2,txt=L[(i+shift*3)%L.length],xx=w<600?14:36,mk=marks[i];
   if(mk&&t-mk.born>5.5){delete marks[i];mk=null}
   c.globalAlpha=.17;c.fillStyle=col;c.fillText(txt,xx,y);c.globalAlpha=1;
   if(mk||hov===i){var p=mk?Math.min(1,mk.p):1;if(mk)mk.p+=dt*1.7;c.fillStyle=col;c.globalAlpha=mk?.2:.1;c.fillRect(0,y-RH/2+2,w*p,RH-4);c.globalAlpha=mk?.9:.5;c.fillRect(0,y+RH/2-3,w*p,2);c.globalAlpha=1;
    if(mk){     if(p>=1){var lx=w-(w<600?34:60),pop=Math.min(1,(t-mk.born-.6)*6);c.save();c.translate(lx,y);c.rotate(-.12);c.scale(.6+.4*pop,.6+.4*pop);c.fillStyle='#d42a12';c.fillRect(-26,-10,52,20);c.fillStyle='#fff';c.font='800 12px JB,monospace';c.textAlign='center';c.fillText('DIBS',0,1);c.restore();c.font='500 '+fs+'px JB,ui-monospace,monospace';c.textAlign='left'}}}}
 });
 cv.addEventListener('pointerdown',function(e){var r=cv.getBoundingClientRect(),i=Math.floor((e.clientY-r.top)/RH);marks[i]={p:0,born:(performance.now()-window.__t0)/1000}});
 window.__t0=performance.now();
})();
/* AGENT: lines "rewritten from memory": glyphs scramble and revert-sweeps pass */
(function(){var cv=FX.layer(ai),G='abcdefghijklmnopqrstuvwxyz0123456789=(){}[]<>_.,:;+-*/#'.split(''),rows=[];
 function mut(s,k){var o='';for(var i=0;i<s.length;i++){o+=(s[i]!==' '&&Math.random()<k)?G[(Math.random()*G.length)|0]:s[i]}return o}
 FX.loop(cv,function(c,w,h,t,dt){c.clearRect(0,0,w,h);var n=Math.ceil(h/RH),fs=w<600?12:15;c.font='500 '+fs+'px JB,ui-monospace,monospace';c.textBaseline='middle';
  if(rows.length!==n){rows=[];for(var i=0;i<n;i++)rows.push(L[i%L.length])}
  var sweep=((t*.35)%1.6)*h;
  for(i=0;i<n;i++){var y=i*RH+RH/2;if(Math.random()<dt*.9)rows[i]=mut(L[(i+((t/3)|0))%L.length],.18);
   c.globalAlpha=.2;c.fillStyle='#cfc7ff';c.fillText(rows[i],w<600?14:36,y);
   if(Math.abs(y-sweep)<RH/2){c.globalAlpha=.55;c.fillStyle='#d42a12';c.fillRect(0,y-RH/2+2,w,RH-4);c.globalAlpha=.9;c.fillStyle='#fff';c.fillText('- '+rows[i].trim(),w<600?14:36,y)}}
  c.globalAlpha=1},{still:3});
})();
})();
