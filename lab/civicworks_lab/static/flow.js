"use strict";
// The pipeline flow: a row of steps you can click. Each step explains itself in plain words, shows the real code
// and the database rule it relies on, and - where it has one - lets you switch its safeguard off to see what it
// protects against. Shared by the website (recorded runs) and the local Lab (live runs).
//
//   renderFlow(element, flow, { runSwitch: async node => result, repo: "https://github.com/..." })
//   result = { diff: [{kind, text}], refused, exit, look_for, defend }
(function () {
  const e = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const KIND = { stop: ["Stops", "■"], hold: ["Waits for a person", "⏸"], quarantine: ["Sets it aside", "⚑"],
                 rollback: ["Can roll back", "↺"], refuse: ["Refuses", "■"] };

  function diffHtml(lines) {
    if (!lines || !lines.length) return `<p class="fl-m">The output was identical to the normal run.</p>`;
    return `<pre class="fl-diff">${lines.map(l => `<span class="${l.kind === "heading" ? "h" : l.kind === "added" ? "plus" : "minus"}">${
      l.kind === "added" ? "+ " : l.kind === "removed" ? "- " : ""}${e(l.text)}</span>`).join("")}</pre>`;
  }

  function resultHtml(r) {
    return `${r.exit ? `<p class="fl-note bad"><b>The run crashed</b> without this safeguard (exit code ${e(r.exit)}) - see the last lines below.</p>` : ""}
      <p class="fl-m"><b>+</b> lines happened only with the safeguard off; <b>-</b> lines only in the normal run.</p>
      ${diffHtml(r.diff)}
      <div class="fl-note"><b>What happened:</b> ${e(r.look_for)}</div>
      <div class="fl-note defend"><b>How to explain the decision:</b> ${e(r.defend)}</div>`;
  }

  window.renderFlow = function (el, flow, opts = {}) {
    let current = 0;
    const nodes = flow.nodes;
    el.classList.add("fl");
    el.innerHTML = `<p class="fl-shape">${e(flow.shape)}</p>
      <div class="fl-play"><button class="fl-btn" data-play>&#9654; Play the pipeline</button>
        <span class="fl-m">Watch the data move through each box, one at a time. Pause on any box to read it; on the box marked
        <b>safeguard</b> you can turn it off and see what happens.</span></div>
      <div class="fl-line" role="list">${nodes.map((n, i) => `
        <button class="fl-node" role="listitem" data-i="${i}" aria-label="Step ${i + 1}: ${e(n.name)}">
          <span class="fl-n">${i + 1}</span><b>${e(n.name)}</b><span class="fl-does">${e(n.does)}</span>
          ${n.branch ? `<span class="fl-exit ${e(n.branch.kind)}">${KIND[n.branch.kind][1]} ${KIND[n.branch.kind][0]}</span>` : ""}
          ${n.switch ? `<span class="fl-sw" title="This step has a safeguard you can switch off">safeguard</span>` : ""}
        </button>`).join(`<span class="fl-arrow" aria-hidden="true">→</span>`)}</div>
      <div class="fl-legend"><span>Click a step to see what it does, its code and the rule behind it.</span>
        ${Object.entries(KIND).filter(([k]) => nodes.some(n => n.branch && n.branch.kind === k))
          .map(([k, [label, icon]]) => `<span class="fl-exit ${k}">${icon} ${label}</span>`).join("")}</div>
      <div class="fl-detail" aria-live="polite"></div>`;
    const detail = el.querySelector(".fl-detail");

    function show(i) {
      current = i;
      el.querySelectorAll(".fl-node").forEach((b, j) => b.classList.toggle("on", j === i));
      const n = nodes[i], s = n.switch, src = n.source, sql = n.sql;
      detail.innerHTML = `
        <div class="fl-head"><span class="fl-n">${i + 1}</span><h3>${e(n.name)}</h3></div>
        <p>${e(n.does)}</p>
        ${n.plain ? `<ul class="fl-plain">${n.plain.map(p => `<li>${e(p)}</li>`).join("")}</ul>` : ""}
        ${n.branch ? `<p class="fl-m"><span class="fl-exit ${e(n.branch.kind)}">${KIND[n.branch.kind][1]} ${KIND[n.branch.kind][0]}</span> here: ${e(n.branch.label)}</p>` : ""}
        ${s ? `<div class="fl-switch"><span class="fl-eyebrow">What if this piece were missing?</span>
            <h4>${e(s.title)}</h4><p>${e(s.protects)}</p>
            <p class="fl-predict"><b>Predict first:</b> ${e(s.predict)}</p>
            <button class="fl-btn" data-run>${opts.live ? "Switch it off and run the real pipeline" : "Show what the real pipeline did without it"}</button>
            <div class="fl-result"></div></div>` : ""}
        ${src ? `<details class="fl-more"><summary>Show the code <span class="fl-m">${e(src.symbol)} &middot; ${e(src.file)}, line ${src.line}</span></summary>
            <pre class="fl-code">${e(src.text)}${src.more ? "\n..." : ""}</pre>
            ${opts.repo ? `<a href="${opts.repo}/blob/main/${e(src.file)}#L${src.line}" target="_blank" rel="noopener">Open the whole file on GitHub</a>` : ""}</details>` : ""}
        ${sql ? `<details class="fl-more"><summary>Show the database rule it relies on <span class="fl-m">${e(sql.object)} (SQL)</span></summary>
            <pre class="fl-code">${e(sql.text)}</pre>
            <table class="fl-parts"><tr><th>This part of the SQL</th><th>means</th></tr>${sql.parts.map(([a, b]) => `<tr><td><code>${e(a)}</code></td><td>${e(b)}</td></tr>`).join("")}</table></details>` : ""}
        <div class="fl-nav"><button class="fl-btn ghost" data-go="-1" ${i ? "" : "disabled"}>&larr; Previous step</button>
          <button class="fl-btn ghost" data-go="1" ${i < nodes.length - 1 ? "" : "disabled"}>Next step &rarr;</button></div>`;
      detail.querySelectorAll("[data-go]").forEach(b => b.onclick = () => show(current + +b.dataset.go));
      const run = detail.querySelector("[data-run]");
      if (run && opts.runSwitch) run.onclick = async () => {
        const out = detail.querySelector(".fl-result");
        run.disabled = true; out.innerHTML = `<p class="fl-m">${opts.live ? "Running the normal pipeline and the one without the safeguard..." : "Loading..."}</p>`;
        try { out.innerHTML = resultHtml(await opts.runSwitch(n, msg => { out.innerHTML = `<p class="fl-m">${e(msg)}</p>` })) }
        catch (err) { out.innerHTML = `<p class="fl-note bad">${e(err.message || err)}</p>` }
        run.remove();
      };
    }
    // Play: step through the boxes on a timer, like data moving along the line. Clicking any box stops it there.
    let timer = null;
    const playBtn = el.querySelector("[data-play]");
    const stop = (label = "&#9654; Play again") => { clearInterval(timer); timer = null; el.classList.remove("playing"); playBtn.innerHTML = label };
    playBtn.onclick = () => {
      if (timer) return stop("&#9654; Keep playing");
      let i = el.querySelector(".fl-node.on") && current < nodes.length - 1 && playBtn.textContent.includes("Keep") ? current + 1 : 0;
      el.classList.add("playing"); playBtn.innerHTML = "&#10073;&#10073; Pause";
      show(i); el.querySelector(".fl-line").scrollIntoView({ block: "nearest", behavior: "smooth" });
      timer = setInterval(() => {
        i += 1;
        if (i >= nodes.length) return stop();
        show(i);
        if (nodes[i].switch) stop("&#9654; Keep playing");      // pause on the safeguard so it can be switched off
      }, 4200);
    };
    el.querySelectorAll(".fl-node").forEach(b => b.onclick = () => { if (timer) stop("&#9654; Keep playing"); show(+b.dataset.i) });
    const first = nodes.findIndex(n => n.switch);
    show(0);
    return { show, first };
  };
})();
