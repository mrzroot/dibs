(() => {
  "use strict";
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];

  /* ------------------------------------------------------------------ i18n */
  const FA = {
    skip: "پرش به دمو", nav_demo: "دمو", nav_how: "چطور", nav_verified: "آزموده‌شده", nav_install: "نصب",
    who_you: "شما", who_ai: "ایجنت",
    hero_you: "یک خط را دستی درست کردید.", hero_ai: "او فایل را از حافظه بازنویسی کرد.",
    h1: "dibs نمی‌گذارد ایجنت‌های هوش مصنوعی چیزی را که شما نوشته‌اید برگردانند.",
    pitch: "ایجنت‌ها ویرایش‌هایی را که بین نوبت‌هایشان انجام می‌دهید نمی‌بینند و آن‌ها را «درست» برمی‌گردانند. dibs به آن‌ها می‌گوید چه چیزی را عوض کرده‌اید، جلوی برگرداندن را پیش از اعمال می‌گیرد و اگر چیزی رد شد، فقط خطوط شما را برمی‌گرداند.",
    cta_play: "بازی کنید: شما در برابر ایجنت ↓", cta_gh: "کد در گیت‌هاب",
    arena_h: "میدان", arena_sub: "نسخهٔ زندهٔ همان کاری که dibs در مخزن شما می‌کند",
    step1: "یک خط از <code>api.py</code> را ویرایش کنید (مثلاً <code>timeout=30</code>)", step2: "به ایجنت کاری بدهید", step3: "ببینید که می‌خواهد از حافظه بنویسد",
    pane_you: "ویرایشگر شما · اینجا تایپ کنید", ghost: "agent", auto_edit: "ویرایشم را خودت انجام بده",
    lg_you: "خطوط شما", lg_ai: "خطوط تازهٔ ایجنت", saved: "خط نجات یافت",
    mem_tab: "حافظهٔ ایجنت", pane_ai: "فکر می‌کند api.py این است",
    t_logging: "بگو: «لاگ اضافه کن»", t_retry: "بگو: «تلاش مجدد اضافه کن»", t_types: "بگو: «نوع‌ها را اضافه کن»",
    guard: "نگهبان dibs", reset: "از نو",
    fix_msg: "ایجنت خط شما را برگرداند. dibs هنوز آن را در دفترش دارد.",
    beats_h: "یک نوبت، از دو سوی درز",
    b1y_h: "شما دستی ویرایش می‌کنید", b1y: "بین دو نوبت، <code>timeout=10</code> را به <code>timeout=30</code> تغییر می‌دهید. dibs آن را به نام شما ثبت می‌کند — با خطوط، زمان و فایل.",
    b1a_h: "ایجنت خلاصه می‌گیرد",
    b2y_h: "باز هم تلاش می‌کند", b2y: "پیش از اجرای هر ویرایش، dibs بررسی می‌کند که آیا خطی را که افزوده‌اید حذف می‌کند یا خطی را که پاک کرده‌اید برمی‌گرداند. Claude Code از شما می‌پرسد؛ Codex و Gemini و Cursor پاسخ ردی می‌گیرند که خطوط شما را نام می‌برد.",
    b2a_h: "ویرایش پس زده می‌شود",
    b3y_h: "چیزی رد شد؟", b3y: "یک <code>sed</code> در دستور شل، یا ایجنتی بدون هوک. dibs بلافاصله می‌بیند، به ایجنت می‌گوید، جلوی کامیت را می‌گیرد و فقط خطوط شما را برمی‌گرداند.",
    b3a_h: "خطوط شما برمی‌گردند",
    ver_h: "آزموده با خود CLIها — صادقانه", ver_sub: "باینری واقعی ایجنت‌ها، تجزیهٔ واقعی تنظیمات، اجراکنندهٔ واقعی هوک. فقط پاسخ‌های مدل از پیش نوشته شده بود (هیچ حسابی استفاده نشد).",
    th_agent: "ایجنت", th_ver: "نسخه", th_guard: "نگهبان پیش از ویرایش", th_shell: "تشخیص برگرداندن با شل", th_brief: "رسیدن خلاصه به مدل",
    after_run: "بعد از اجرا", unit_only: "آزمون واحد از روی کد خودش · برای آزمون کامل حساب Cursor لازم است", not_run: "اجرا نشده · VS Code و حساب Copilot لازم است",
    inst_h: "در ۲۰ ثانیه dibs بگویید", inst_p: "پایتون ۳٫۹ به بالا، بدون وابستگی. همه چیز روی دستگاه خودتان در <code>.git/dibs/</code> می‌ماند.",
    copy: "کپی دستور نصب", release: "یادداشت انتشار",
    /* runtime strings */
    log_empty: "جلسهٔ ایجنت اینجا نمایش داده می‌شود.",
    k_user: "شما", k_tool: "ابزار", k_dibs: "dibs → ایجنت", k_agent: "ایجنت", k_ok: "انجام شد", k_warn: "dibs (نگهبان خاموش)", k_restore: "dibs restore",
    from_memory: "از حافظه، بدون خواندن دوبارهٔ فایل",
    agent_reply: "فهمیدم — خط شما را نگه می‌دارم و تغییرم را دور آن می‌سازم.",
    wrote_ok: "نوشته شد. هیچ خطی از شما حذف نشد.",
    warn_revert: "ایجنت {n} خط شما را برگرداند (#{seq}). کامیت مسدود خواهد شد تا restore یا ack کنید.",
    restored: "خطوط شما برگشت؛ تغییرات دیگر ایجنت ماند.",
    acked: "پذیرفته شد: نسخهٔ ایجنت می‌ماند.",
    no_edit_hint: "نکته: اول یک خط را دستی عوض کنید تا ببینید dibs چطور وارد می‌شود.",
    copied: "کپی شد ✓", guard_on: "روشن", guard_off: "خاموش",
    task_logging: "لاگ اضافه کن", task_retry: "تلاش مجدد اضافه کن", task_types: "نوع‌ها را اضافه کن",
  };
  const EN = {};
  $$("[data-i]").forEach(el => { EN[el.dataset.i] = el.innerHTML; });
  Object.assign(EN, {
    log_empty: "The agent's session shows up here.",
    k_user: "you", k_tool: "tool call", k_dibs: "dibs → agent", k_agent: "agent", k_ok: "done", k_warn: "dibs (guard off)", k_restore: "dibs restore",
    from_memory: "from memory, without re-reading the file",
    agent_reply: "Got it — keeping your line and building my change around it.",
    wrote_ok: "Written. None of your lines were touched.",
    warn_revert: "The agent undid {n} of your line(s) (#{seq}). The commit will be blocked until you restore or ack.",
    restored: "Your lines are back; the agent's other changes stay.",
    acked: "Accepted: the agent's version stays.",
    no_edit_hint: "Tip: change a line by hand first to see dibs step in.",
    copied: "Copied ✓", guard_on: "ON", guard_off: "OFF",
    task_logging: "add logging", task_retry: "add retries", task_types: "add type hints",
  });
  const params = new URLSearchParams(location.search);
  let lang = params.get("lang") === "fa" || params.get("lang") === "en" ? params.get("lang") : null;
  try { lang = lang || localStorage.getItem("dibs-lang"); } catch (e) { /* storage blocked */ }
  if (lang !== "fa") lang = "en";
  const t = k => (lang === "fa" ? FA[k] : EN[k]) ?? EN[k] ?? k;

  function applyLang() {
    const html = document.documentElement;
    html.lang = lang; html.dir = lang === "fa" ? "rtl" : "ltr";
    $$("[data-i]").forEach(el => { const v = t(el.dataset.i); if (v != null) el.innerHTML = v; });
    $("#lang").textContent = lang === "fa" ? "EN" : "فا";
    $("#lang").setAttribute("aria-label", lang === "fa" ? "Switch to English" : "تغییر به فارسی");
    $("#log").dataset.empty = t("log_empty");
    const heads = $$(".tbl thead th").map(th => th.textContent);
    $$(".tbl tbody tr").forEach(tr => { let c = 0; $$("th,td", tr).forEach(cell => { if (cell.tagName === "TD") cell.dataset.l = cell.colSpan > 1 ? "" : heads[c] || ""; c += cell.colSpan || 1; }); });
    $("#guardState").textContent = guard() ? t("guard_on") : t("guard_off");
    document.title = lang === "fa" ? "dibs — چیزی که نوشتید را ایجنت پس نمی‌گیرد" : "dibs — you typed it, the agent can't take it back";
  }
  $("#lang").addEventListener("click", () => {
    lang = lang === "fa" ? "en" : "fa";
    try { localStorage.setItem("dibs-lang", lang); } catch (e) { /* ignore */ }
    applyLang(); relabelLog();
  });

  /* ------------------------------------------------------------------ model */
  const V1 = [
    "import requests",
    "",
    'BASE = "https://api.example.com"',
    "",
    "",
    "def fetch(path):",
    "    r = requests.get(BASE + path, timeout=10)",
    "    r.raise_for_status()",
    "    return r.json()",
  ];
  const TRIVIAL = new Set(["", ")", "]", "}", "else:", "pass", "try:", "#"]);
  const norm = s => s.replace(/\s+/g, " ").trim();
  const sig = s => !TRIVIAL.has(norm(s)) && norm(s).length > 1;

  // Each task is what the agent "knows how to do", applied to whatever text it starts from.
  const lastImport = L => { let i = -1; L.forEach((l, k) => { if (/^(import|from)\s/.test(l)) i = k; }); return i; };
  const TASKS = {
    logging(L) {
      L = L.slice();
      if (!L.some(l => /^import logging\b/.test(l))) L.unshift("import logging");
      if (!L.some(l => /^log = logging/.test(l))) { const i = lastImport(L); L.splice(i + 1, 0, "", "log = logging.getLogger(__name__)"); }
      const g = L.findIndex(l => /requests\.\w+\(/.test(l) && /^\s+/.test(l));
      if (g >= 0 && !L.some(l => /log\.info\(/.test(l))) L.splice(g, 0, L[g].match(/^\s*/)[0] + 'log.info("GET %s", path)');
      return L;
    },
    retry(L) {
      L = L.slice();
      if (!L.some(l => /tenacity/.test(l))) { const i = lastImport(L); L.splice(i + 1, 0, "from tenacity import retry, stop_after_attempt"); }
      const d = L.findIndex(l => /^def fetch/.test(l));
      if (d >= 0 && !/^@retry/.test(L[d - 1] || "")) L.splice(d, 0, "@retry(stop=stop_after_attempt(3))");
      return L;
    },
    types(L) {
      return L.map(l => l.replace(/^def fetch\((\w+)\):/, "def fetch($1: str) -> dict:"));
    },
  };

  let mem = V1.slice();          // what the agent remembers
  let mine = new Set();          // normalized lines the human wrote (protected)
  let deleted = new Set();       // normalized lines the human deleted
  let aiNew = new Set();         // lines the agent added in its last write
  let saved = 0, seq = 6, busy = false, pending = null, edited = false;
  const done = new Set();

  const ta = $("#ta"), hl = $("#hl"), gutter = $("#gutter"), ghost = $("#ghost"), stamp = $("#stamp"), log = $("#log");
  const guard = () => $("#guard").checked;
  const lines = () => ta.value.split("\n");
  const count = arr => { const m = new Map(); arr.forEach(l => { const k = norm(l); m.set(k, (m.get(k) || 0) + 1); }); return m; };

  function track() {
    const cur = lines(), cm = count(cur), mm = count(mem);
    const next = new Set();
    for (const l of cur) { const k = norm(l); if (sig(l) && (mine.has(k) || (cm.get(k) || 0) > (mm.get(k) || 0))) next.add(k); }
    mine = next;
    deleted = new Set([...deleted].filter(k => !cm.has(k)));
    for (const l of mem) { const k = norm(l); if (sig(l) && !cm.has(k)) deleted.add(k); }
  }

  function metrics() {
    const cs = getComputedStyle(ta);
    return { lh: parseFloat(cs.lineHeight) || 24, pad: parseFloat(cs.paddingTop) || 14, ch: chWidth() };
  }
  let _ch = 0;
  function chWidth() {
    if (_ch) return _ch;
    const s = document.createElement("span");
    s.textContent = "0".repeat(40); s.style.cssText = "position:absolute;visibility:hidden;white-space:pre;font:inherit";
    $("#code").appendChild(s); _ch = s.getBoundingClientRect().width / 40; s.remove();
    return _ch || 8;
  }

  function render(fx = {}) {
    const cur = lines();
    const maxLen = Math.max(...cur.map(l => l.length), 20);
    ta.rows = cur.length;
    ta.style.width = `calc(${maxLen + 3}ch + ${2 * metrics().pad}px)`;
    ta.style.height = `${cur.length * metrics().lh + 2 * metrics().pad}px`;
    const cls = l => { const k = norm(l); return mine.has(k) ? "you" : aiNew.has(k) && sig(l) ? "ai" : ""; };
    hl.innerHTML = ""; gutter.innerHTML = "";
    cur.forEach((l, i) => {
      const c = cls(l);
      const d = document.createElement("div"); d.className = [c, fx[i] || ""].join(" ").trim(); d.textContent = l || " "; hl.appendChild(d);
      const g = document.createElement("div"); g.className = c;
      g.innerHTML = `<span>${i + 1}</span><span class="tg">${c === "you" ? "YOU" : c === "ai" ? "AI" : ""}</span>`;
      gutter.appendChild(g);
    });
    const cm = count(cur);
    const pre = $("#mem"); pre.innerHTML = "";
    mem.forEach(l => { const d = document.createElement("div"); d.textContent = l; if (sig(l) && !cm.has(norm(l))) d.className = "stale"; pre.appendChild(d); });
    steps();
  }

  function steps() {
    const s = $$(".steps li");
    s.forEach(li => li.classList.remove("on", "done"));
    if (!edited) s[0].classList.add("on");
    else { s[0].classList.add("done"); (busy ? s[2] : s[1]).classList.add("on"); if (busy) s[1].classList.add("done"); }
  }

  /* ------------------------------------------------------------------ log */
  const entries = [];
  function say(kind, key, extra = {}) { entries.push({ kind, key, extra }); drawMsg(entries[entries.length - 1]); }
  function drawMsg(e) {
    const d = document.createElement("div"); d.className = `msg ${e.kind}`;
    const k = document.createElement("span"); k.className = "k"; k.textContent = t("k_" + e.kind); d.appendChild(k);
    if (e.key) { const p = document.createElement("span"); p.textContent = fill(t(e.key), e.extra); d.appendChild(p); }
    if (e.extra.text) { const p = document.createElement("span"); p.textContent = e.extra.text; d.appendChild(p); }
    if (e.extra.pre) { const p = document.createElement("pre"); p.textContent = e.extra.pre; d.appendChild(p); }
    log.appendChild(d); log.scrollTop = log.scrollHeight;
  }
  const fill = (s, x) => s.replace(/\{(\w+)\}/g, (_, k) => x[k] ?? "");
  function relabelLog() { log.innerHTML = ""; entries.forEach(drawMsg); }

  /* ------------------------------------------------------------------ the duel */
  const sleep = ms => new Promise(r => setTimeout(r, matchMedia("(prefers-reduced-motion: reduce)").matches ? Math.min(ms, 60) : ms));
  function placeGhost(i, col) {
    const m = metrics();
    ghost.style.transform = `translate(${m.pad + col * m.ch}px, ${m.pad + i * m.lh}px)`;
  }
  async function sweep(from, to, L) {
    for (let i = from; i <= to; i++) { placeGhost(i, (L[i] || "").match(/^\s*/)[0].length); await sleep(Math.max(60, 900 / Math.max(L.length, 1))); }
  }
  function dibsMessage(revs) {
    return "dibs: this edit to api.py would undo changes the human made by hand.\n" +
      (revs.dropped.length ? "It removes lines the human added or changed:\n" + revs.dropped.map(l => "  + " + l.trim()).join("\n") + "\n" : "") +
      (revs.back.length && !revs.dropped.length ? "It brings back lines the human deleted:\n" + revs.back.map(l => "  - " + l.trim()).join("\n") + "\n" : "") +
      "Keep the human's version and make your change around it. Only if the user explicitly asked to change these lines, run `dibs allow api.py` and retry.";
  }
  function lock(on) {
    busy = on; ta.readOnly = on;
    $$(".task").forEach(b => { b.disabled = on || done.has(b.dataset.task) || !!pending; });
    $("#autoEdit").disabled = on || !!pending; $("#reset").disabled = on;
    steps();
  }

  async function runTask(name) {
    if (busy || pending) return;
    lock(true); track();
    const cur = lines();
    const stale = TASKS[name](mem);         // what the agent writes from memory
    const merged = TASKS[name](cur);        // the same change built on the real file
    const staleSet = count(stale);
    const dropped = cur.filter(l => mine.has(norm(l)) && !staleSet.has(norm(l)));
    const back = stale.filter(l => deleted.has(norm(l)));
    const r = $("#ed").getBoundingClientRect();
    if (r.top < 60 || r.bottom > innerHeight) {  // on phones the buttons sit below the editor: bring the duel into view
      $("#ed").scrollIntoView({ behavior: "smooth", block: r.height > innerHeight - 80 ? "start" : "center" });
      await sleep(450);
    }
    say("user", "task_" + name);
    say("tool", null, { text: `\u2066Write(api.py)\u2069 — ${t("from_memory")}` });
    if (!mine.size && !deleted.size) say("agent", "no_edit_hint");
    ghost.classList.add("on");
    const hitAt = dropped.length ? cur.findIndex(l => norm(l) === norm(dropped[0]))
      : back.length ? Math.max(0, cur.findIndex(l => norm(l) === norm(stale[stale.findIndex(s => deleted.has(norm(s))) - 1] || ""))) : -1;
    if (hitAt < 0) {
      await sweep(0, cur.length - 1, cur);
      finishWrite(merged, name);
      say("ok", "wrote_ok");
    } else {
      await sweep(0, hitAt, cur);
      seq++;
      if (guard()) {
        ghost.classList.add("hit"); stamp.style.top = `${metrics().pad + hitAt * metrics().lh - 8}px`;
        stamp.classList.remove("on"); void stamp.offsetWidth; stamp.classList.add("on");
        const fx = {}; cur.forEach((l, i) => { if (dropped.some(d => norm(d) === norm(l))) fx[i] = "boom"; }); render(fx);
        say("dibs", null, { pre: dibsMessage({ dropped, back }) });
        await sleep(1100); ghost.classList.remove("hit");
        say("agent", "agent_reply");
        await sweep(0, 0, merged);
        await sweep(0, merged.length - 1, merged);
        finishWrite(merged, name);
        bumpSaved(Math.max(dropped.length, back.length));
        say("ok", "wrote_ok");
      } else {
        const fx = {}; cur.forEach((l, i) => { if (dropped.some(d => norm(d) === norm(l))) fx[i] = "gone"; }); render(fx);
        await sleep(700);
        await sweep(hitAt, stale.length - 1, stale);
        const before = cur.slice();
        const oldMem = count(mem);
        ta.value = stale.join("\n"); aiNew = new Set([...newLines(before, stale)].filter(k => !oldMem.has(k))); mem = stale.slice();
        pending = { merged, n: Math.max(dropped.length, back.length), name, mine: [...mine] };
        const cm0 = count(before);
        render(markLines(stale, stale.filter(l => sig(l) && !cm0.has(norm(l)) && !aiNew.has(norm(l)) || back.includes(l)), "gone"));
        say("tool", null, { text: "\u2066Write(api.py) ✓\u2069" });
        say("warn", "warn_revert", { n: Math.max(dropped.length, back.length), seq });
        $("#fix").hidden = false;
        done.add(name); markDone();
      }
    }
    ghost.classList.remove("on");
    lock(false);
  }
  const newLines = (before, after) => { const b = count(before), s = new Set(); after.forEach(l => { if (!b.has(norm(l))) s.add(norm(l)); }); return s; };
  const markLines = (L, which, c) => { const fx = {}; L.forEach((l, i) => { if (which.some(w => norm(w) === norm(l))) fx[i] = c; }); return fx; };
  function finishWrite(next, name) {
    const before = lines();
    aiNew = newLines(before, next);
    ta.value = next.join("\n"); mem = next.slice();
    done.add(name); markDone(); track(); render();
  }
  function markDone() { $$(".task").forEach(b => b.classList.toggle("done", done.has(b.dataset.task))); }
  function bumpSaved(n) {
    saved += n; $("#saved").textContent = saved;
    const m = $(".meter"); m.classList.remove("bump"); void m.offsetWidth; m.classList.add("bump");
  }

  $("#restore").addEventListener("click", () => {
    if (!pending) return;
    const p = pending; pending = null;
    const before = lines();
    ta.value = p.merged.join("\n"); mem = p.merged.slice();
    mine = new Set(p.mine); deleted = new Set(); track();
    const fx = {}; p.merged.forEach((l, i) => { if (mine.has(norm(l)) && !before.some(b => norm(b) === norm(l))) fx[i] = "back"; });
    render(fx);
    say("restore", "restored");
    bumpSaved(p.n);
    $("#fix").hidden = true; lock(false);
  });
  $("#ack").addEventListener("click", () => {
    if (!pending) return;
    pending = null; mine = new Set(); deleted = new Set(); track(); render();
    say("ok", "acked"); $("#fix").hidden = true; lock(false);
  });

  /* ------------------------------------------------------------------ human input */
  ta.addEventListener("input", () => { edited = true; track(); render(); });
  ta.addEventListener("keydown", e => {
    if (e.key === "Tab" && !e.shiftKey && !ta.readOnly) { e.preventDefault(); document.execCommand ? document.execCommand("insertText", false, "    ") : null; }
  });
  $("#autoEdit").addEventListener("click", async () => {
    if (busy || pending) return;
    const cur = lines();
    let i = cur.findIndex(l => /timeout=\d+\)/.test(l));
    if (i < 0) i = cur.findIndex(l => /requests\./.test(l));
    if (i < 0) return;
    lock(true);
    const target = cur[i].includes("timeout=10)") ? cur[i].replace("timeout=10)", 'timeout=30, verify="ca.pem")')
      : cur[i].replace(/\)\s*$/, ', verify="ca.pem")');
    const start = cur.slice(0, i).join("\n").length + (i ? 1 : 0);
    const orig = cur[i];
    let pfx = 0; while (pfx < Math.min(orig.length, target.length) && target[pfx] === orig[pfx]) pfx++;
    let sfx = 0; while (sfx < Math.min(orig.length, target.length) - pfx && target[target.length - 1 - sfx] === orig[orig.length - 1 - sfx]) sfx++;
    ta.focus({ preventScroll: true });
    const tail = target.slice(target.length - sfx);
    for (let k = pfx; k <= target.length - sfx; k++) {
      cur[i] = target.slice(0, k) + tail;
      ta.value = cur.join("\n");
      ta.setSelectionRange(start + k, start + k);
      edited = true; track(); render();
      await sleep(30);
    }
    cur[i] = target; ta.value = cur.join("\n"); track(); render();
    lock(false);
  });

  $$(".task").forEach(b => b.addEventListener("click", () => runTask(b.dataset.task)));
  $("#guard").addEventListener("change", () => { $("#guardState").textContent = guard() ? t("guard_on") : t("guard_off"); });
  function reset() {
    mem = V1.slice(); mine = new Set(); deleted = new Set(); aiNew = new Set(); pending = null; edited = false;
    done.clear(); markDone(); entries.length = 0; log.innerHTML = ""; $("#fix").hidden = true;
    ta.value = V1.join("\n"); render(); lock(false);
  }
  $("#reset").addEventListener("click", reset);

  $("#copy").addEventListener("click", async () => {
    const cmd = "pipx install git+https://github.com/mrzroot/dibs@v0.1.1";
    try { await navigator.clipboard.writeText(cmd); } catch (e) {
      const x = document.createElement("textarea"); x.value = cmd; document.body.appendChild(x); x.select();
      try { document.execCommand("copy"); } catch (e2) { /* ignore */ } x.remove();
    }
    const b = $("#copy"); b.textContent = t("copied"); setTimeout(() => { b.textContent = t("copy"); }, 1600);
  });

  // re-measure when fonts arrive or the layout changes
  const remeasure = () => { _ch = 0; render(); };
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(remeasure);
  addEventListener("resize", () => { clearTimeout(remeasure.t); remeasure.t = setTimeout(remeasure, 150); });

  applyLang();
  reset();
  window.__dibsDemo = { runTask, state: () => ({ mine: [...mine], mem, text: ta.value, saved, pending: !!pending }) };
})();
