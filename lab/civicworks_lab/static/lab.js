"use strict";
// CivicWorks Lab - one page, hash routes, no build step and no external libraries.
const $ = (s, el = document) => el.querySelector(s);
const app = $("#app");
let C = null;                         // content from /api/content
let TERMS = [];                       // glossary terms, longest first
const store = {
  get(k, d) { try { return JSON.parse(localStorage.getItem("cw:" + k)) ?? d } catch { return d } },
  set(k, v) { try { localStorage.setItem("cw:" + k, JSON.stringify(v)) } catch { /* private window */ } },
};
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const api = async (path, body) => {
  const r = await fetch(path, body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {});
  return r.json();
};

// --- glossary: underline known words; hover or tap shows the plain meaning ---------------------------
function terms(text) {
  let out = esc(text);
  const used = new Set();
  for (const t of TERMS) {
    if (used.size > 6) break;
    const re = new RegExp(`(^|[^\\w-])(${t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}s?)(?![\\w-])`, "i");
    if (re.test(out) && !used.has(t)) {
      out = out.replace(re, (m, pre, word) => `${pre}<span class="term" data-term="${esc(t)}">${word}</span>`);
      used.add(t);
    }
  }
  return out;
}
document.addEventListener("mouseover", e => {
  const el = e.target.closest(".term"); const tip = $("#tip");
  if (!el) { tip.hidden = true; return }
  const g = C.glossary[el.dataset.term]; if (!g) return;
  tip.innerHTML = `<b>${esc(el.dataset.term)}</b>: ${esc(g.plain)}${g.like ? `<i>Like: ${esc(g.like)}</i>` : ""}`;
  const r = el.getBoundingClientRect();
  tip.hidden = false;
  tip.style.left = Math.min(r.left, innerWidth - 360) + "px";
  tip.style.top = (r.bottom + 8) + "px";
});

// --- routing ---------------------------------------------------------------------------------------------
const routes = {
  "": home, ideas, glossary, interview, cards, quick,
  p: (key, tab) => pipeline(key, tab || "overview"),
};
function route() {
  const [, head = "", ...rest] = location.hash.replace(/^#\/?/, "/").split("/");
  document.querySelectorAll("[data-nav]").forEach(a => a.classList.toggle("on", a.dataset.nav === (head || "home")));
  $("#drawer").hidden = true; $("#tip").hidden = true;
  if ("speechSynthesis" in window) speechSynthesis.cancel();
  (routes[head] || home)(...rest);
  scrollTo(0, 0);
}
addEventListener("hashchange", route);
$("#quit").onclick = async () => { await api("/api/quit", {}); document.body.innerHTML = "<main><h2>The Lab has stopped.</h2><p class='lede'>Start it again from the desktop shortcut.</p></main>" };
$("#drawer-close").onclick = () => { $("#drawer").hidden = true };
$("#drawer").onclick = e => { if (e.target.id === "drawer") $("#drawer").hidden = true };

// --- pages ------------------------------------------------------------------------------------------------
function home() {
  const done = store.get("done", {});
  app.innerHTML = `
  <section class="hero">
    <div class="eyebrow">Your eight pipelines</div>
    <h1>Run each one, watch what it does, and learn why it is built that way.</h1>
    <p class="lede">Every pipeline here runs for real on invented data. Pick one and press <b>Guided run</b>: it stops before each scene,
    asks what you think will happen, runs it, then shows you exactly which files, rows and cells changed. Hover any underlined word for a plain meaning.</p>
  </section>
  <div class="start">
    <a href="#/p/atlas/run"><b>Start here: a guided run of Atlas</b><span>The flagship: data checked, frozen, printed into 12 PDFs, verified, published.</span></a>
    <a href="#/ideas"><b>The nine big ideas</b><span>Understand these and you understand all eight pipelines.</span></a>
    <a href="#/interview"><b>Interview prep</b><span>A 30-second pitch, a 2-minute walkthrough, real stories, honest answers.</span></a>
    <a href="#/cards"><b>Flashcards</b><span>Every interview question, simple answer first, technical second.</span></a>
  </div>
  <h2>The pipelines</h2>
  <div class="grid">${C.pipelines.map(p => `
    <a class="card" href="#/p/${p.key}">
      <span class="num">${String(p.order).padStart(2, "0")}${done[p.key] ? " &middot; guided run completed" : ""}</span>
      <h3>${esc(p.title)}</h3><p>${esc(p.tagline)}</p>
      <div class="chips">${p.skills.slice(0, 4).map(s => `<span class="chip">${esc(s)}</span>`).join("")}</div>
    </a>`).join("")}</div>`;
}

function pipeline(key, tab) {
  const p = C.pipelines.find(x => x.key === key); if (!p) return home();
  const tabs = [["overview", "Overview"], ["run", "Guided run"], ["why", "Why built this way"], ["wrong", "What goes wrong"],
                ["questions", "Questions"], ["try", "Try it yourself"], ["video", "Video"]];
  app.innerHTML = `
    <section class="hero"><div class="eyebrow">Pipeline ${p.order} of 8</div><h1>${esc(p.title)}</h1><p class="lede">${esc(p.tagline)}</p></section>
    <nav class="tabs">${tabs.map(([k, l]) => `<a href="#/p/${key}/${k}" class="${k === tab ? "on" : ""}">${l}</a>`).join("")}</nav>
    <div id="tab"></div>`;
  ({ overview, run: guided, why, wrong, questions, try: tryit, video })[tab](p, $("#tab"));
}

function overview(p, el) {
  el.className = "section";
  el.innerHTML = `
    <div class="two">
      <div class="card"><span class="eyebrow">The story</span><p>${terms(p.story)}</p></div>
      <div class="card"><span class="eyebrow">In one minute (say this)</span><p>${terms(p.one_minute)}</p></div>
    </div>
    <h2>What happens, step by step</h2>
    <div class="flow">${p.steps.map(s => `<div class="step"><b>${esc(s.name)}</b><span>${terms(s.plain)}</span><small>${esc(s.technical)}</small></div>`).join("")}</div>
    <div class="two">
      <div class="card"><span class="eyebrow">What goes in</span><table>${p.inputs.map(i => `<tr><td><code>${esc(i.name)}</code></td><td>${terms(i.what)}</td></tr>`).join("")}</table></div>
      <div class="card"><span class="eyebrow">What comes out</span><table>${p.outputs.map(o => `<tr><td><code>${esc(o.name)}</code></td><td>${terms(o.what)}</td></tr>`).join("")}</table></div>
    </div>
    ${p.rules ? `<h2>The rulebook</h2><div class="scroll"><table><tr><th>rule</th><th>severity</th><th>why it exists</th><th>how to fix</th></tr>
      ${p.rules.map(r => `<tr><td><code>${esc(r.id)}</code></td><td>${esc(r.severity)}</td><td>${esc(r.rationale)}</td><td>${esc(r.remediation)}</td></tr>`).join("")}</table></div>` : ""}
    <div class="card"><span class="eyebrow">Skills this shows</span><div class="chips">${p.skills.map(s => `<span class="chip">${esc(s)}</span>`).join("")}</div></div>
    <div class="actions"><a href="#/p/${p.key}/run"><button>Start the guided run</button></a></div>`;
}

function why(p, el) {
  el.className = "section";
  el.innerHTML = `<p class="lede">Every design choice had an alternative. Knowing why one was picked is what interviewers probe.</p>` +
    p.decisions.map(d => `<div class="decision"><h3>${esc(d.choice)}</h3><span class="vs">instead of: ${esc(d.instead_of)}</span><p>${terms(d.why)}</p></div>`).join("");
}

function wrong(p, el) {
  el.className = "section";
  el.innerHTML = `<div class="scroll"><table><tr><th>what goes wrong</th><th>what the pipeline does</th></tr>
    ${p.failures.map(f => `<tr><td>${terms(f.what)}</td><td>${terms(f.result)}</td></tr>`).join("")}</table></div>`;
}

function qa(q) {
  return `<div class="qa"><span class="q">${esc(q.q)}</span><div class="a">
    <p><span class="label">Simple answer</span>${terms(q.simple)}</p><p><span class="label">If they ask for more</span>${terms(q.technical)}</p></div></div>`;
}
function questions(p, el) { el.className = "section"; el.innerHTML = p.questions.map(qa).join("") }

function tryit(p, el) {
  el.className = "section";
  el.innerHTML = `<p class="lede">Small experiments. Run the guided run first so the workspace exists, then open a terminal in
    <code>${esc(p.dir)}</code> and try these. Predict the result before you press Enter.</p>` +
    p.try.map(t => `<div class="card"><h3>${esc(t.title)}</h3><p>${terms(t.how)}</p><p class="note"><b>Expect:</b> ${terms(t.expect)}</p></div>`).join("");
}

function video(p, el) {
  el.className = "section";
  el.innerHTML = p.video ? `<video controls preload="metadata" src="${p.video}"></video><p class="note">Replayed from a real run of the demo; captions explain each scene.</p>`
                         : `<p class="lede">The video for this pipeline is being made.</p>`;
}

// --- the guided run ----------------------------------------------------------------------------------
function guided(p, el) {
  const scenes = Object.entries(p.scenes).map(([n, s]) => ({ n: +n, ...s }));
  let run = null, next = 0, current = 1, lines = [], titles = {}, changes = {}, timer = null, reading = store.get("readAloud", false);
  el.className = "runbox";
  el.innerHTML = `<aside class="scenes" id="scene-list"></aside><div class="stage" id="stage"></div>`;

  function speak(text) {
    if (!reading || !("speechSynthesis" in window)) return;
    speechSynthesis.cancel(); const u = new SpeechSynthesisUtterance(text); u.rate = 0.98; speechSynthesis.speak(u);
  }
  function list() {
    $("#scene-list").innerHTML = scenes.map(s => `<div class="s ${s.n === current ? "now" : s.n < current || (run && run.status === "done") ? "done" : ""}">
      <span class="n">${s.n}</span><span>${esc(titles[s.n] || "Scene " + s.n)}</span></div>`).join("");
  }
  function lineClass(t) {
    if (t.startsWith("== ")) return "h";
    if (/\b(BLOCKED|REFUSED|FAILED|QUARANTINED|STOPPED|rejected|overdue)\b|\[x\]|!!/.test(t)) return "bad";
    if (/\b(PUBLISHED|APPROVED|COMPLETE|FINAL|accepted|verified|OK)\b/.test(t)) return "ok";
    if (/\[-\]|awaiting|held|NOTHING NEW|stale/.test(t)) return "warn";
    return "";
  }
  function stage() {
    const s = scenes.find(x => x.n === current); const ran = run && (current < run.scene || (current === run.scene && run.status !== "running"));
    const mine = lines.filter(l => l.scene === current);
    const ch = changes[current];
    const last = current === scenes.length;
    $("#stage").innerHTML = `
      <div class="scene-card">
        <div class="actions"><span class="status">Scene ${current} of ${scenes.length}</span>
          ${run ? `<span class="status">${run.status === "running" ? "running..." : run.status === "done" ? "finished" : "paused, waiting for you"}</span>` : ""}
          <label class="note" style="margin-left:auto"><input type="checkbox" id="ra" ${reading ? "checked" : ""}> Read aloud</label></div>
        <h2>${esc(titles[current] || "Scene " + current)}</h2>
        <p>${terms(s.explain)}</p>
        <div class="predict"><b>Predict first</b><p>${terms(s.predict)}</p></div>
        ${ran ? `<div class="answer"><b>What happened:</b> ${terms(s.answer)}</div>` : ""}
        <div class="actions">
          ${!run ? `<button id="go">Run scene 1</button><span class="note">Make your prediction, then start the real ${esc(p.title)} demo on fresh invented data.</span>` : ""}
          ${run && !ran && run.status === "paused" ? `<button id="go">Run scene ${current}</button><span class="note">Prediction made? Run it and compare.</span>` : ""}
          ${run && ran && !last ? `<button id="nextscene">Next scene</button><span class="note">Read what changed below first.</span>` : ""}
          ${run && ran && last ? `<button id="again" class="ghost">Run it again from the start</button><span class="note">Guided run complete.</span>` : ""}
          ${run ? `<button class="ghost small" id="files">All files in this run</button><button class="ghost small" id="folder">Open the folder</button>` : ""}
        </div>
      </div>
      ${mine.length ? `<div class="terminal">${mine.map(l => `<div class="${lineClass(l.text)}">${esc(l.text)}</div>`).join("")}</div>` : ""}
      ${ran && ch ? changesView(ch) : ""}`;
    $("#ra").onchange = e => { reading = e.target.checked; store.set("readAloud", reading); if (reading) speak(s.explain) };
    const go = $("#go"); if (go) go.onclick = runCurrent;
    const ns = $("#nextscene"); if (ns) ns.onclick = () => { current += 1; speak(scenes.find(x => x.n === current).explain); stage(); scrollTo(0, 0) };
    const again = $("#again"); if (again) again.onclick = () => { run = null; current = 1; lines = []; titles = {}; changes = {}; list(); stage() };
    const files = $("#files"); if (files) files.onclick = () => allFiles(run.id);
    const folder = $("#folder"); if (folder) folder.onclick = () => api("/api/open-folder", { run: run.id });
    el.querySelectorAll("[data-file]").forEach(b => b.onclick = () => openFile(run.id, b.dataset.file));
    list();
  }
  function changesView(ch) {
    const files = [...ch.added.map(f => [f, "new"]), ...ch.changed.map(f => [f, "changed"])].filter(([f]) => !f.includes("__pycache__"));
    return `<div class="card changes"><span class="eyebrow">What this scene changed</span>
      ${files.length ? `<ul>${files.slice(0, 40).map(([f, k]) => `<li><span class="badge ${k === "new" ? "add" : "chg"}">${k}</span>
        <button class="filebtn" data-file="${esc(f)}">${esc(f)}</button></li>`).join("")}</ul>` : `<p class="note">No files changed.</p>`}
      ${files.length > 40 ? `<p class="note">...and ${files.length - 40} more (see All files).</p>` : ""}
      ${ch.tables.length ? `<span class="eyebrow">Database rows</span><table><tr><th>table</th><th>before</th><th>after</th></tr>
        ${ch.tables.map(t => `<tr><td><code>${esc(t.table.split("::")[1])}</code> <span class="note">${esc(t.table.split("::")[0])}</span></td><td>${t.before}</td><td>${t.after}</td></tr>`).join("")}</table>` : ""}
      <p class="note">Click any file to open it here: spreadsheets, Word reports, PDF pages, databases and drafts.</p></div>
      ${rowsView(ch)}`;
  }
  const srcName = s => { const [f, t] = s.split("::"); return t ? `<code>${esc(t)}</code> <span class="note">table in ${esc(f)}</span>`
    : s.includes(" > ") ? `<code>${esc(s.split(" > ")[1])}</code> <span class="note">sheet in ${esc(s.split(" > ")[0])}</span>` : `<code>${esc(s)}</code>`; };
  function grid(cols, rows) {   // rows: [{row, cls, cells:{i: html}}]
    const n = Math.min(12, Math.max(cols.length, ...rows.map(r => r.row.length)));
    return `<div class="rowgrid"><table><tr>${Array.from({ length: n }, (_, i) => `<th>${esc(cols[i] ?? "")}</th>`).join("")}</tr>
      ${rows.map(r => `<tr class="${r.cls || ""}">${Array.from({ length: n }, (_, i) => r.cells && i in r.cells ? `<td class="hit">${r.cells[i]}</td>`
        : `<td>${esc(r.row[i] ?? "")}</td>`).join("")}</tr>`).join("")}</table></div>`;
  }
  function rowsView(ch) {
    const traced = ch.traced || [], rows = (ch.rows || []);
    const edits = rows.filter(r => r.n_changed || (!r.new_source && (r.n_added || r.n_removed)));
    const fresh = rows.filter(r => r.new_source);
    if (!traced.length && !rows.length) return "";
    const tracedHtml = traced.length ? `<div class="card rows"><span class="eyebrow">Traced to the exact rows</span>
      <p class="note">Every record this scene's output names, found in the data. Highlighted cells hold the identifier.</p>
      ${traced.slice(0, 6).map(t => `<h4>${srcName(t.source)}</h4>${grid(t.cols, t.rows.map(r => ({ row: r.row,
        cells: Object.fromEntries(r.cells.map(i => [i, `<mark>${esc(r.row[i])}</mark>`])) })))}`).join("")}</div>` : "";
    const editHtml = edits.length ? `<div class="card rows"><span class="eyebrow">Rows that changed</span>
      <p class="note">Changed cells show <s>before</s> and after. Shaded rows were added; struck-through rows were removed.</p>
      ${edits.slice(0, 6).map(r => `<h4>${srcName(r.source)} <span class="note">${[r.n_changed && r.n_changed + " changed", r.n_added && r.n_added + " added",
        r.n_removed && r.n_removed + " removed"].filter(Boolean).join(", ")}</span></h4>${grid(r.cols, [
        ...r.changed.map(c => ({ row: c.row, cells: Object.fromEntries(c.cells.map(i => [i, `<s>${esc(c.before[i] ?? "")}</s> ${esc(c.row[i] ?? "")}`])) })),
        ...r.added.map(row => ({ row, cls: "addrow" })), ...r.removed.map(row => ({ row, cls: "delrow" }))])}`).join("")}</div>` : "";
    const freshHtml = fresh.length ? `<div class="card rows"><span class="eyebrow">New data written</span><ul>${fresh.map(r =>
      `<li><details><summary>${srcName(r.source)} <span class="note">${r.n_added} rows</span></summary>${grid(r.cols, r.added.map(row => ({ row })))}
      ${r.n_added > r.added.length ? `<p class="note">First ${r.added.length} of ${r.n_added} shown.</p>` : ""}</details></li>`).join("")}</ul></div>` : "";
    return tracedHtml + editHtml + freshHtml;
  }
  async function runCurrent() {
    if (!run) { const r = await api("/api/start", { key: p.key }); run = { id: r.run, status: "running", scene: 0 }; current = 1 }
    else { await api("/api/next", { run: run.id }); run.status = "running" }
    stage(); poll();
  }
  async function poll() {
    clearTimeout(timer);
    const s = await api(`/api/state?run=${run.id}&since=${next}`);
    next = s.next; lines.push(...s.lines); run.status = s.status; run.scene = s.scene; changes = s.changes;
    for (const l of s.lines) { const m = l.text.match(/^== (\d+)\. (.*)$/); if (m) titles[+m[1]] = m[2] }
    stage();
    if (s.status === "running") timer = setTimeout(poll, 350);
    else if (s.status === "done") { const d = store.get("done", {}); d[p.key] = true; store.set("done", d) }
  }
  list(); stage(); speak(scenes[0].explain);
}

// --- file and database previews ----------------------------------------------------------------------
async function allFiles(run) {
  const r = await api(`/api/files?run=${run}`);
  drawer("All files in this run", `<ul>${r.files.filter(f => !f.includes("__pycache__")).map(f => `<li><button class="filebtn" data-file="${esc(f)}">${esc(f)}</button></li>`).join("")}</ul>`);
  $("#drawer-body").querySelectorAll("[data-file]").forEach(b => b.onclick = () => openFile(run, b.dataset.file));
}
function drawer(title, html) { $("#drawer-title").textContent = title; $("#drawer-body").innerHTML = html; $("#drawer").hidden = false }
function sheetTable(s) {
  return `<h3>${esc(s.name)}${s.charts ? ` <span class="badge">${s.charts} chart</span>` : ""}${s.total ? ` <span class="note">${s.total} rows</span>` : ""}</h3>
    <div class="scroll"><table>${s.rows.map((r, i) => `<tr>${r.map(c => i === 0 ? `<th>${esc(c)}</th>` : `<td>${esc(c)}</td>`).join("")}</tr>`).join("")}</table></div>`;
}
async function openFile(run, path) {
  const r = await api(`/api/preview?run=${run}&path=${encodeURIComponent(path)}`);
  const q = `run=${run}&path=${encodeURIComponent(path)}`;
  if (r.error) return drawer(path, `<p>${esc(r.error)}</p>`);
  if (r.kind === "table") return drawer(path, (r.note ? `<p class="note">${esc(r.note)}</p>` : "") + r.sheets.map(sheetTable).join(""));
  if (r.kind === "doc") return drawer(path, `<div class="card doc">${r.parts.map(x => x.type === "p" ? `<p class="${esc(x.style)}">${esc(x.text)}</p>`
    : `<div class="scroll"><table>${x.rows.map((row, i) => `<tr>${row.map(c => i ? `<td>${esc(c)}</td>` : `<th>${esc(c)}</th>`).join("")}</tr>`).join("")}</table></div>`).join("")}</div>`);
  if (r.kind === "pdf") {
    let page = 0;
    const show = () => { $("#pdfimg").src = `/api/pdfpage?${q}&page=${page}`; $("#pg").textContent = `page ${page + 1} of ${r.pages}` };
    drawer(path, `<div class="actions"><button class="ghost small" id="prev">Previous</button><span id="pg" class="status"></span>
      <button class="ghost small" id="nextp">Next</button><span class="note">Bookmarks: ${r.toc.map(t => esc(t[1])).join(", ")}</span></div><img id="pdfimg" class="pdfpage" alt="PDF page">`);
    $("#prev").onclick = () => { page = Math.max(0, page - 1); show() }; $("#nextp").onclick = () => { page = Math.min(r.pages - 1, page + 1); show() };
    return show();
  }
  if (r.kind === "sqlite") {
    drawer(path, `<p class="lede">The data model: each box is a table, <span class="pk">PK</span> marks the primary key and arrows show foreign keys - links a row must have to another table. Click a table to see its rows.</p>
      <div class="erd">${r.tables.map(t => `<div class="t"><h4><button class="filebtn" data-table="${esc(t.name)}">${esc(t.name)}</button><span>${t.rows} rows</span></h4><ul>
      ${t.columns.map(c => { const fk = t.foreign_keys.find(f => f.from === c.name);
        return `<li class="${c.pk ? "pk" : fk ? "fk" : ""}">${esc(c.name)} <span class="note">${esc(c.type)}${c.pk ? " PK" : ""}${fk ? ` &rarr; ${esc(fk.table)}` : ""}</span></li>` }).join("")}</ul></div>`).join("")}</div><div id="rows"></div>`);
    $("#drawer-body").querySelectorAll("[data-table]").forEach(b => b.onclick = async () => {
      const t = await api(`/api/rows?${q}&table=${encodeURIComponent(b.dataset.table)}`); $("#rows").innerHTML = t.sheets.map(sheetTable).join("") });
    return;
  }
  if (r.kind === "text" && r.html) return drawer(path, `<iframe sandbox src="/api/raw?${q}" style="width:100%;height:75vh;border:1px solid var(--line);border-radius:8px;background:#fff"></iframe>`);
  if (r.kind === "image") return drawer(path, `<img class="pdfpage" src="/api/raw?${q}" alt="">`);
  drawer(path, `<div class="terminal" style="max-height:none">${esc(r.text)}</div>`);
}

// --- study pages ------------------------------------------------------------------------------------------
function ideas() {
  app.innerHTML = `<section class="hero"><div class="eyebrow">Architecture, from first principles</div><h1>Nine ideas behind all eight pipelines</h1>
    <p class="lede">Each pipeline is these ideas applied to one problem. If an interviewer asks "why did you build it this way?", the answer is almost always one of these.</p></section>` +
    C.ideas.map((i, n) => `<div class="card"><span class="num">${n + 1}</span><h3>${esc(i.title)}</h3><p>${terms(i.plain)}</p>
      <p class="note"><b>Why:</b> ${terms(i.why)}</p><p class="note"><b>Where to see it:</b> ${esc(i.where)}</p></div>`).join("");
}
function glossary() {
  const entries = Object.entries(C.glossary).sort((a, b) => a[0].localeCompare(b[0]));
  app.innerHTML = `<section class="hero"><div class="eyebrow">${entries.length} words</div><h1>Glossary</h1>
    <p class="lede">Every technical word in the Lab, in plain language with an everyday comparison.</p>
    <input type="search" id="gq" placeholder="Search, e.g. idempotent"></section><div class="gloss" id="gl"></div>`;
  const draw = f => { $("#gl").innerHTML = entries.filter(([k, v]) => !f || (k + v.plain).toLowerCase().includes(f.toLowerCase()))
    .map(([k, v]) => `<div class="g"><b>${esc(k)}</b><span>${esc(v.plain)}${v.like ? ` <i>Like ${esc(v.like.charAt(0).toLowerCase() + v.like.slice(1))}</i>` : ""}</span></div>`).join("") };
  $("#gq").oninput = e => draw(e.target.value); draw("");
}
function interview() {
  const I = C.interview;
  app.innerHTML = `<section class="hero"><div class="eyebrow">Talking about it</div><h1>Interview prep</h1>
    <p class="lede">Say the plain version first. Add the deeper version only when they ask - that is how experienced engineers answer.</p></section>
    <div class="card"><span class="eyebrow">30-second pitch</span><p>${terms(I.pitch_30s)}</p></div>
    <div class="card"><span class="eyebrow">2-minute walkthrough</span><ol>${I.walkthrough_2min.map(s => `<li>${terms(s)}</li>`).join("")}</ol></div>
    <h2>Stories (situation, problem, action, result)</h2>
    ${I.stories.map(s => `<div class="card"><h3>${esc(s.title)}</h3><p><b>Situation.</b> ${terms(s.situation)}</p><p><b>Problem.</b> ${terms(s.problem)}</p>
      <p><b>What I did.</b> ${terms(s.action)}</p><p><b>Result.</b> ${terms(s.result)}</p></div>`).join("")}
    <h2>"Did AI write this?"</h2>
    ${qa({ q: "How did you use AI to build this?", simple: I.about_ai.plain, technical: I.about_ai.deeper })}
    <div class="two"><div class="card"><span class="eyebrow">What you would change for production</span><ul>${I.production_changes.map(x => `<li>${terms(x)}</li>`).join("")}</ul></div>
    <div class="card"><span class="eyebrow">Which roles it speaks to</span>${Object.entries(I.roles).map(([r, t]) => `<p><b>${esc(r)}:</b> ${terms(t)}</p>`).join("")}</div></div>
    <h2>Every pipeline's questions</h2>${C.pipelines.map(p => `<h3>${esc(p.title)}</h3>${p.questions.map(qa).join("")}`).join("")}`;
}
function cards() {
  const all = C.pipelines.flatMap(p => p.questions.map(q => ({ ...q, from: p.title })));
  const known = store.get("known", {});
  let i = 0, shown = false;
  const draw = () => {
    const left = all.filter(q => !known[q.q]); const q = left[i % Math.max(left.length, 1)];
    app.innerHTML = `<section class="hero"><div class="eyebrow">Flashcards</div><h1>Answer out loud, then check</h1>
      <div class="meter"><i style="width:${Math.round(100 * (all.length - left.length) / all.length)}%"></i></div>
      <p class="note">${all.length - left.length} of ${all.length} marked as known. Progress is saved in this browser.</p></section>
      ${q ? `<div class="flash"><span class="note">${esc(q.from)}</span><span class="q">${esc(q.q)}</span>
        ${shown ? `<div class="qa"><div class="a"><p><span class="label">Simple</span>${terms(q.simple)}</p><p><span class="label">Deeper</span>${terms(q.technical)}</p></div></div>
        <div class="actions"><button id="know">I knew it</button><button class="ghost" id="again">Show me again later</button></div>`
        : `<div class="actions"><button id="show">Show the answer</button></div>`}</div>`
      : `<div class="flash"><span class="q">All ${all.length} cards known.</span><div class="actions"><button id="reset" class="ghost">Start over</button></div></div>`}`;
    if ($("#show")) $("#show").onclick = () => { shown = true; draw() };
    if ($("#know")) $("#know").onclick = () => { known[q.q] = true; store.set("known", known); shown = false; draw() };
    if ($("#again")) $("#again").onclick = () => { i += 1; shown = false; draw() };
    if ($("#reset")) $("#reset").onclick = () => { for (const k in known) delete known[k]; store.set("known", known); draw() };
  };
  draw();
}
async function quick() {
  app.innerHTML = `<section class="hero"><div class="eyebrow">Operator view</div><h1>Quick run: all eight, start to finish</h1>
    <p class="lede">Runs every pipeline's full demo without stopping and lists what each produced. Use it to check everything works before you show someone.</p>
    <div class="actions"><button id="go">Run all eight</button></div></section><div id="qr"></div>`;
  const draw = s => { $("#qr").innerHTML = `<p class="status">${s.status === "running" ? `running... ${s.results.length} of 8 done` : s.status}</p>
    ${s.results.length ? `<div class="scroll"><table><tr><th>pipeline</th><th>result</th><th>seconds</th><th>files made</th><th></th></tr>
    ${s.results.map(r => `<tr><td>${esc(r.key)}</td><td>${r.ok ? "finished" : "FAILED"}</td><td>${r.seconds}</td><td>${r.files}</td>
      <td><button class="ghost small" data-folder="${esc(r.folder)}">Open folder</button></td></tr>`).join("")}</table></div>` : ""}`;
    $("#qr").querySelectorAll("[data-folder]").forEach(b => b.onclick = () => api("/api/open-folder", { folder: b.dataset.folder })) };
  const poll = async () => { const s = await api("/api/quick"); draw(s); if (s.status === "running") setTimeout(poll, 1000) };
  $("#go").onclick = async () => { draw(await api("/api/quick", {})); poll() };
  poll();
}

api("/api/content").then(c => {
  C = c; TERMS = Object.keys(c.glossary).sort((a, b) => b.length - a.length); route();
});
