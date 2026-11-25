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
  "": home, ideas: concepts, glossary: concepts, prep, cards, quick,
  p: (key, tab) => pipeline(key, tab || "flow"),
};
// Which parts are public (a recorded version is on the website, the code is on GitHub) and which are yours alone.
const PUBLIC = `<span class="vis pub" title="A recorded version is on the public website; here it runs live on this computer">Public - also on the website</span>`;
const PRIVATE = `<span class="vis priv" title="Lives outside the repository; never published">Private - only on this computer</span>`;
const layer = (title, hint, body, open = false) => `<details class="layer" ${open ? "open" : ""}><summary><b>${esc(title)}</b><span>${esc(hint)}</span></summary><div class="layer-body">${body}</div></details>`;
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
    <div class="eyebrow">Your eight pipelines ${PUBLIC}</div>
    <h1>Run each one, break it on purpose, and learn why it is built that way.</h1>
    <p class="lede">Pick a pipeline. Its <b>flow</b> shows every step in plain words, with the real code and the database rule behind it.
    Switch a safeguard off to see what it protects against. Hover any underlined word for a plain meaning.</p>
  </section>
  <div class="start">
    <a href="#/p/masterrecord/flow"><b>Start here: click through a flow</b><span>MasterRecord - three sources disagree, a person decides, one cell is written.</span></a>
    <a href="#/p/openbadge/flow"><b>Switch off a safeguard</b><span>Remove the check after upload and watch a broken file go live - for real.</span></a>
    <a href="#/prep"><b>My prep</b><span>Your pitch, questions by role, and where each pipeline fits your own work. ${PRIVATE}</span></a>
  </div>
  <h2>The pipelines</h2>
  <div class="grid">${C.pipelines.map(p => `
    <a class="card" href="#/p/${p.key}/flow">
      <span class="num">${String(p.order).padStart(2, "0")}${done[p.key] ? " &middot; guided run completed" : ""}</span>
      <h3>${esc(p.title)}</h3><p>${esc(p.tagline)}</p>
      ${C.prep && C.prep.work_hints ? `<p class="note"><b>In real work:</b> ${esc(C.prep.work_hints[p.key])}</p>` : ""}
    </a>`).join("")}</div>`;
}

function pipeline(key, tab) {
  const p = C.pipelines.find(x => x.key === key); if (!p) return home();
  const tabs = [["flow", "The flow"], ["run", "Guided run"], ["try", "Try it"], ["data", "Query the data"], ["deeper", "Go deeper"]];
  app.innerHTML = `
    <section class="hero"><div class="eyebrow">Pipeline ${p.order} of 8</div><h1>${esc(p.title)}</h1><p class="lede">${esc(p.tagline)}</p></section>
    <nav class="tabs">${tabs.map(([k, l]) => `<a href="#/p/${key}/${k}" class="${k === tab ? "on" : ""}">${l}</a>`).join("")}</nav>
    <div id="tab"></div>`;
  ({ flow: flowTab, run: guided, try: tryit, data: dataTab, deeper })[tab in { flow: 1, run: 1, try: 1, data: 1, deeper: 1 } ? tab : "flow"](p, $("#tab"));
}

function flowTab(p, el) {
  el.className = "section";
  const hint = C.prep && C.prep.work_hints ? C.prep.work_hints[p.key] : "";
  el.innerHTML = `<div class="two"><div class="card"><span class="eyebrow">The problem it solves ${PUBLIC}</span><p>${terms(p.story)}</p></div>
    <div class="card"><span class="eyebrow">Say it in one minute</span><p>${terms(p.one_minute)}</p>
    ${hint ? `<p class="note"><b>Where it might fit your work:</b> ${esc(hint)} <a href="#/prep">Write yours in My prep</a> ${PRIVATE}</p>` : ""}</div></div>
    <div id="flowbox"></div>`;
  renderFlow($("#flowbox"), C.flows[p.key], {
    live: true, repo: "https://github.com/data-dl/civicworks-automation-lab",
    runSwitch: async (node, progress) => {
      const ids = await api("/api/experiment", { key: p.key, id: node.switch.id });
      if (ids.error) throw new Error(ids.error);
      let a = 0, b = 0;
      const [, off] = await Promise.all([
        waitRun(ids.normal, s => { a = s.next; progress(`normal run: ${a} lines - without the safeguard: ${b} lines`) }),
        waitRun(ids.experiment, s => { b = s.next; progress(`normal run: ${a} lines - without the safeguard: ${b} lines`) })]);
      const cmp = await api(`/api/compare?a=${ids.normal}&b=${ids.experiment}`);
      return { diff: cmp.lines || [], exit: off.exit, look_for: node.switch.look_for, defend: node.switch.defend };
    },
  });
}

function deeper(p, el) {
  el.className = "section";
  el.innerHTML = `<p class="lede">The detail, one piece at a time. Open what you need. ${PUBLIC}</p>` + [
    layer("Why it is built this way", `${p.decisions.length} design decisions and what was chosen instead`,
      p.decisions.map(d => `<div class="decision"><h3>${esc(d.choice)}</h3><span class="vs">instead of: ${esc(d.instead_of)}</span><p>${terms(d.why)}</p></div>`).join("")),
    layer("What goes wrong, and what happens", `${p.failures.length} situations`,
      `<div class="scroll"><table><tr><th>what goes wrong</th><th>what the pipeline does</th></tr>${p.failures.map(f => `<tr><td>${terms(f.what)}</td><td>${terms(f.result)}</td></tr>`).join("")}</table></div>`),
    layer("What goes in and what comes out", "Inputs and outputs, named",
      `<div class="two"><div><span class="eyebrow">In</span><table>${p.inputs.map(i => `<tr><td><code>${esc(i.name)}</code></td><td>${terms(i.what)}</td></tr>`).join("")}</table></div>
       <div><span class="eyebrow">Out</span><table>${p.outputs.map(o => `<tr><td><code>${esc(o.name)}</code></td><td>${terms(o.what)}</td></tr>`).join("")}</table></div></div>`),
    p.rules ? layer("The rulebook", `${p.rules.length} rules`, `<div class="scroll"><table><tr><th>rule</th><th>severity</th><th>why it exists</th><th>how to fix</th></tr>
      ${p.rules.map(r => `<tr><td><code>${esc(r.id)}</code></td><td>${esc(r.severity)}</td><td>${esc(r.rationale)}</td><td>${esc(r.remediation)}</td></tr>`).join("")}</table></div>`) : "",
    layer("Questions it answers", `${p.questions.length} questions - a short answer and a deeper one`, p.questions.map(qa).join("")),
    layer("Watch the video", "Narrated, replayed from a real run", p.video ? `<video controls preload="metadata" src="${p.video}"></video>` : "<p>Not recorded yet.</p>"),
    layer("From a terminal", "The commands behind the buttons", p.try.map(t => `<h4>${esc(t.title)}</h4><p>${terms(t.how)}</p><p class="note"><b>Expect:</b> ${terms(t.expect)}</p>`).join("")),
  ].join("");
}

function qa(q) {
  return `<div class="qa"><span class="q">${esc(q.q)}</span><div class="a">
    <p><span class="label">Simple answer</span>${terms(q.simple)}</p><p><span class="label">If they ask for more</span>${terms(q.technical)}</p></div></div>`;
}

// --- shared table helpers --------------------------------------------------------------------------------
const srcLabel = s => { const [f, t] = s.split("::"); return t ? `<code>${esc(t)}</code> <span class="note">table in ${esc(f)}</span>`
  : s.includes(" > ") ? `<code>${esc(s.split(" > ")[1])}</code> <span class="note">sheet in ${esc(s.split(" > ")[0])}</span>` : `<code>${esc(s)}</code>`; };
function gridHtml(cols, rows, max = 12) {   // rows: [{row, cls, cells:{i: html}}]
  const n = Math.min(max, Math.max(cols.length, ...rows.map(r => r.row.length)));
  return `<div class="rowgrid"><table><tr>${Array.from({ length: n }, (_, i) => `<th>${esc(cols[i] ?? "")}</th>`).join("")}</tr>
    ${rows.map(r => `<tr class="${r.cls || ""}">${Array.from({ length: n }, (_, i) => r.cells && i in r.cells ? `<td class="hit">${r.cells[i]}</td>`
      : `<td>${esc(r.row[i] ?? "")}</td>`).join("")}</tr>`).join("")}</table></div>`;
}
function changedRowsHtml(list) {
  return list.slice(0, 6).map(r => `<h4>${srcLabel(r.source)}</h4>${gridHtml(r.cols, [
    ...r.changed.map(c => ({ row: c.row, cells: Object.fromEntries(c.cells.map(i => [i, `<s>${esc(c.before[i] ?? "")}</s> ${esc(c.row[i] ?? "")}`])) })),
    ...r.added.map(row => ({ row, cls: "addrow" })), ...r.removed.map(row => ({ row, cls: "delrow" }))])}`).join("");
}
function diffHtml(lines) {
  if (!lines.length) return `<p class="note">The output was identical to the normal run.</p>`;
  return `<div class="terminal diff">${lines.map(l => `<div class="${l.kind === "heading" ? "h" : l.kind === "added" ? "plus" : "minus"}">${
    l.kind === "added" ? "+ " : l.kind === "removed" ? "- " : ""}${esc(l.text)}</div>`).join("")}</div>`;
}
const waitRun = async (id, onTick) => {
  for (;;) { const s = await api(`/api/state?run=${id}&since=0`); if (onTick) onTick(s); if (s.status === "done") return s; await new Promise(r => setTimeout(r, 600)) }
};

// --- experiments: change the real data, run the real pipeline, see only what changed ----------------------
function tryit(p, el) {
  el.className = "section";
  const X = C.experiments[p.key] || { experiments: [] };
  el.innerHTML = `<p class="lede">${PUBLIC} Change one thing in the real input data, then let the real pipeline run on. The Lab runs a normal run beside
    it and shows you <b>only the lines of output your change made different</b>. Predict first - that is where the learning happens.</p>
    ${X.note ? `<div class="card"><p>${terms(X.note)}</p></div>` : ""}
    ${X.experiments.map((x, i) => `<div class="card exp" id="x${i}"><span class="eyebrow">Experiment ${i + 1}</span><h3>${esc(x.title)}</h3>
      <p>${terms(x.plain)}</p>
      <details class="note"><summary>The exact change</summary><ul>${x.edits.map(e => `<li><code>${esc(e.sql || JSON.stringify(e))}</code></li>`).join("")}</ul></details>
      <div class="predict"><b>Predict first</b><p>${terms(x.predict)}</p></div>
      <div class="actions"><button data-x="${i}">Run the normal run and this experiment</button><span class="note" id="xs${i}"></span></div>
      <div id="xr${i}"></div></div>`).join("")}
    <h2>Your own experiment</h2>
    <div class="two"><div class="card"><span class="eyebrow">Change any input</span><p>Start the <a href="#/p/${p.key}/run">guided run</a>. After scene 1,
      press <b>Change the data</b>: edit any cell of an input file, or run SQL against the run's database, then run the next scene and see what the pipeline does with it.</p></div>
      <div class="card"><span class="eyebrow">Ask the data a question</span><p>The <a href="#/p/${p.key}/data">Query the data</a> tab has a SQL console on this
      pipeline's database, with example questions that teach joins, window functions and more.</p></div></div>
`;
  el.querySelectorAll("[data-x]").forEach(b => b.onclick = async () => {
    const i = +b.dataset.x, x = X.experiments[i], out = $(`#xr${i}`), st = $(`#xs${i}`);
    b.disabled = true; out.innerHTML = ""; st.textContent = "starting both runs...";
    const ids = await api("/api/experiment", { key: p.key, id: x.id });
    if (ids.error) { st.textContent = ids.error; b.disabled = false; return }
    let a = 0, e = 0;
    const [, run] = await Promise.all([
      waitRun(ids.normal, s => { a = s.next; st.textContent = `normal run: ${a} lines · experiment: ${e} lines` }),
      waitRun(ids.experiment, s => { e = s.next; st.textContent = `normal run: ${a} lines · experiment: ${e} lines` })]);
    const cmp = await api(`/api/compare?a=${ids.normal}&b=${ids.experiment}`);
    const ap = run.applied || {};
    st.textContent = "both runs finished";
    out.innerHTML = `
      ${ap.error ? `<div class="answer refused"><b>The change was refused before the pipeline saw it:</b> <code>${esc(ap.error)}</code>
        <p class="note">Nothing was written, so the run continued exactly as normal.</p></div>`
        : `<span class="eyebrow">1. Your change, in the data</span>${changedRowsHtml(ap.rows || [])}`}
      <span class="eyebrow">2. What the pipeline did differently</span>
      <p class="note">Lines starting with <b>+</b> appear only in your experiment; <b>-</b> only in the normal run. Scene headings show where.</p>
      ${diffHtml(cmp.lines || [])}
      <div class="answer"><b>What to notice:</b> ${terms(x.look_for)}</div>
      <div class="actions"><button class="ghost small" data-files="${esc(ids.experiment)}">Open the experiment's files</button></div>`;
    out.querySelector("[data-files]").onclick = () => allFiles(ids.experiment);
    b.disabled = false; b.textContent = "Run it again";
  });
}

// --- the SQL console on a run's database ------------------------------------------------------------------
async function sqlConsole(el, p, runId) {
  const Q = (C.experiments.queries || {})[p.key] || { db: "", list: [] };
  const { dbs = [] } = await api(`/api/dbs?run=${runId}`);
  const pick = dbs.find(d => d.split("/").pop() === Q.db) || dbs[0];
  el.innerHTML = `<div class="sql">
    <div class="actions"><label class="note">Database <select id="sqldb">${dbs.map(d => `<option ${d === pick ? "selected" : ""}>${esc(d)}</option>`).join("")}</select></label>
      <button class="ghost small" id="schema">See its tables</button></div>
    <div class="chips">${Q.list.map((q, i) => `<button class="chip qbtn" data-q="${i}" title="${esc(q.teaches)}">${esc(q.title)}</button>`).join("")}</div>
    <p class="note" id="teach">Pick a question above, or write your own. This is a sandbox copy - changes stay in this run.</p>
    <textarea id="sqltext" spellcheck="false" rows="8">${esc(Q.list[0]?.sql || "SELECT name FROM sqlite_master WHERE type = 'table';")}</textarea>
    <div class="actions"><button id="runsql">Run (Ctrl+Enter)</button><span class="note" id="sqlinfo"></span></div><div id="sqlout"></div></div>`;
  const run = async () => {
    const r = await api("/api/sql", { run: runId, db: $("#sqldb", el).value, sql: $("#sqltext", el).value });
    $("#sqlinfo", el).textContent = r.error ? "" : r.cols.length ? `${r.rows.length}${r.more ? "+" : ""} row(s)` : `${r.changed} row(s) changed`;
    $("#sqlout", el).innerHTML = r.error ? `<div class="answer refused"><b>The database said no:</b> <code>${esc(r.error)}</code></div>`
      : r.cols.length ? gridHtml(r.cols, r.rows.map(row => ({ row })), 20) : `<p class="note">Done. Re-run a SELECT to see the effect.</p>`;
  };
  el.querySelectorAll("[data-q]").forEach(b => b.onclick = () => { const q = Q.list[+b.dataset.q];
    $("#sqltext", el).value = q.sql; $("#teach", el).innerHTML = `<b>Teaches:</b> ${esc(q.teaches)}`; run() });
  $("#runsql", el).onclick = run;
  $("#sqltext", el).onkeydown = e => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); run() } };
  $("#schema", el).onclick = () => openFile(runId, $("#sqldb", el).value);
  if (Q.list.length) run();
}

async function dataTab(p, el) {
  el.className = "section";
  el.innerHTML = `<p class="lede">Every pipeline keeps its state in a SQLite database with keys, constraints and an audit trail. Ask it questions in SQL -
    the same skill an analytics engineer uses every day. The examples teach one idea each; hover a question to see which.</p><div id="sqlhost"></div>`;
  const host = $("#sqlhost");
  const latest = await api(`/api/latest?key=${p.key}`);
  if (latest.run && latest.status === "done") return sqlConsole(host, p, latest.run);
  host.innerHTML = `<div class="card"><p>${latest.run ? "Your guided run is still in progress; finish it, or make a complete set of data now."
    : "There is no data yet."} Making it runs the real ${esc(p.title)} demo start to finish on invented data (a few seconds to half a minute).</p>
    <div class="actions"><button id="make">Make the data</button><span class="note" id="mk"></span></div></div>`;
  $("#make").onclick = async () => {
    $("#make").disabled = true; const r = await api("/api/run-through", { key: p.key });
    await waitRun(r.run, s => { $("#mk").textContent = `running... ${s.next} lines` });
    sqlConsole(host, p, r.run);
  };
}

// --- change the data mid-run: edit an input CSV or run SQL ------------------------------------------------
async function changeData(runId, p) {
  const { files = [] } = await api(`/api/files?run=${runId}`);
  const csvs = files.filter(f => f.endsWith(".csv"));
  drawer("Change the data", `<p class="lede">Edit an input, save, then press <b>Run scene</b> to see how the pipeline reacts. Only this run's copy changes.</p>
    <div class="two"><div><span class="eyebrow">Edit a file</span><ul>${csvs.map(f => `<li><button class="filebtn" data-edit="${esc(f)}">${esc(f)}</button></li>`).join("")
    || "<li class='note'>No CSV files yet.</li>"}</ul></div><div><span class="eyebrow">Or change a database with SQL</span><div id="drawersql"></div></div></div><div id="editor"></div>`);
  sqlConsole($("#drawersql"), p, runId);
  $("#drawer-body").querySelectorAll("[data-edit]").forEach(b => b.onclick = async () => {
    const r = await api(`/api/csv?run=${runId}&path=${encodeURIComponent(b.dataset.edit)}`);
    if (r.error) { $("#editor").innerHTML = `<p>${esc(r.error)}</p>`; return }
    $("#editor").innerHTML = `<h3>${esc(b.dataset.edit)}</h3><p class="note">Click a cell and type. Changed cells are highlighted.</p>
      <div class="rowgrid edit"><table>${r.rows.map((row, i) => `<tr>${row.map(c => i ? `<td contenteditable="true">${esc(c)}</td>` : `<th>${esc(c)}</th>`).join("")}</tr>`).join("")}</table></div>
      <div class="actions"><button id="savecsv">Save this file</button><span class="note" id="saved"></span></div>`;
    $("#editor").querySelectorAll("td").forEach(td => { const v = td.textContent; td.oninput = () => td.classList.toggle("hit", td.textContent !== v) });
    $("#savecsv").onclick = async () => {
      const rows = [...$("#editor").querySelectorAll("tr")].map(tr => [...tr.children].map(c => c.textContent));
      const s = await api("/api/save-csv", { run: runId, path: b.dataset.edit, rows });
      $("#saved").textContent = s.error ? s.error : `saved ${s.rows} rows - now run the next scene`;
    };
  });
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
          ${run && run.status === "paused" ? `<button class="ghost small" id="change">Change the data</button>` : ""}
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
    const change = $("#change"); if (change) change.onclick = () => changeData(run.id, p);
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
function concepts() {
  const entries = Object.entries(C.glossary).sort((a, b) => a[0].localeCompare(b[0]));
  app.innerHTML = `<section class="hero"><div class="eyebrow">Concepts ${PUBLIC}</div><h1>The ideas behind all eight pipelines</h1>
    <p class="lede">Nine ideas explain why the pipelines are built the way they are. Every technical word is in the glossary below, in plain
    language with an everyday comparison.</p></section>` +
    C.ideas.map((i, n) => layer(`${n + 1}. ${i.title}`, i.plain.length > 110 ? i.plain.slice(0, 107) + "..." : i.plain,
      `<p>${terms(i.plain)}</p><p class="note"><b>Why:</b> ${terms(i.why)}</p><p class="note"><b>Where to see it:</b> ${esc(i.where)}</p>`)).join("") +
    `<h2>Glossary</h2><input type="search" id="gq" placeholder="Search, e.g. idempotent"><div class="gloss" id="gl"></div>`;
  const draw = f => { $("#gl").innerHTML = entries.filter(([k, v]) => !f || (k + v.plain).toLowerCase().includes(f.toLowerCase()))
    .map(([k, v]) => `<div class="g"><b>${esc(k)}</b><span>${esc(v.plain)}${v.like ? ` <i>Like ${esc(v.like.charAt(0).toLowerCase() + v.like.slice(1))}</i>` : ""}</span></div>`).join("") };
  $("#gq").oninput = e => draw(e.target.value); draw("");
}

async function prep() {
  if (!C.prep) {
    app.innerHTML = `<section class="hero"><div class="eyebrow">My prep</div><h1>No private prep on this computer</h1>
      <p class="lede">Interview prep lives outside the repository, in a folder called <code>civicworks-prep</code> next to it (or wherever
      <code>CIVICWORKS_PREP</code> points), so it is never published. Everything else in the Lab works without it.</p></section>`;
    return;
  }
  const I = C.prep.interview, notes = await api("/api/notes");
  const note = (key, label, hint) => `<div class="worksheet"><label for="n-${esc(key)}"><b>${esc(label)}</b>${hint ? `<span class="note">${esc(hint)}</span>` : ""}</label>
    <textarea id="n-${esc(key)}" data-note="${esc(key)}" rows="3" placeholder="Write it in your own words...">${esc(notes[key] || "")}</textarea></div>`;
  app.innerHTML = `<section class="hero"><div class="eyebrow">My prep ${PRIVATE}</div><h1>Get ready to talk about it</h1>
    <p class="lede">Nothing on this page is in the GitHub repository or on the website. It lives in <code>${esc(C.prep.folder)}</code>, and what you
    type is saved there as you go.</p></section>
    <div class="prep-nav"><a href="#pitch">Pitch</a><a href="#map">Map it to your work</a><a href="#roles">Questions by role</a><a href="#stories">Stories</a><a href="#/cards">Flashcards</a></div>
    <section id="pitch"><h2>Your pitch</h2>
      <div class="card"><span class="eyebrow">30 seconds</span><p>${terms(I.pitch_30s)}</p></div>
      ${layer("2-minute walkthrough", "Five beats, in order", `<ol>${I.walkthrough_2min.map(s => `<li>${terms(s)}</li>`).join("")}</ol>`)}
      ${layer('"Did AI write this?"', "Say it plainly, then show your judgement", `<p>${terms(I.about_ai.plain)}</p><p class="note">${terms(I.about_ai.deeper)}</p>`)}
      ${note("pitch", "My pitch, in my own words", "Rewrite the 30 seconds so it sounds like you.")}</section>
    <section id="map"><h2>Where each pipeline fits your work</h2>
      <p class="lede">These pipelines are stand-ins for real work you cannot show. For each one, write the real equivalent - the system, the
      report, the people - so you can say "this is like what I do when..." in an interview.</p>
      ${C.pipelines.map(p => note("map-" + p.key, p.title, (C.prep.work_hints || {})[p.key])).join("")}</section>
    <section id="roles"><h2>Questions by role</h2><p class="lede">Answer out loud first, then open the outline. The outline is a checklist, not a script.</p>
      ${Object.entries(C.prep.roles || {}).map(([role, qs]) => `<h3>${esc(role)}</h3>` + qs.map(q => layer(q.q, "Answer it, then open",
        `<ul>${q.outline.map(o => `<li>${terms(o)}</li>`).join("")}</ul><p class="note"><b>Point to:</b> ${esc(q.point_to)}</p>`)).join("")).join("")}</section>
    <section id="stories"><h2>Stories</h2>${I.stories.map(s => layer(s.title, "Situation, problem, what I did, result",
      `<p><b>Situation.</b> ${terms(s.situation)}</p><p><b>Problem.</b> ${terms(s.problem)}</p><p><b>What I did.</b> ${terms(s.action)}</p><p><b>Result.</b> ${terms(s.result)}</p>`)).join("")}
      ${layer("What I would change for production", "When they ask what is missing", `<ul>${I.production_changes.map(x => `<li>${terms(x)}</li>`).join("")}</ul>`)}</section>`;
  let timer;
  app.querySelectorAll("[data-note]").forEach(ta => ta.oninput = () => {
    clearTimeout(timer); ta.classList.add("saving");
    timer = setTimeout(async () => { await api("/api/notes", { key: ta.dataset.note, text: ta.value }); ta.classList.remove("saving") }, 600);
  });
}

function cards() {
  const all = C.pipelines.flatMap(p => p.questions.map(q => ({ ...q, from: p.title })));
  const known = store.get("known", {});
  let i = 0, shown = false;
  const draw = () => {
    const left = all.filter(q => !known[q.q]); const q = left[i % Math.max(left.length, 1)];
    app.innerHTML = `<section class="hero"><div class="eyebrow">Flashcards ${PRIVATE}</div><h1>Answer out loud, then check</h1>
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
