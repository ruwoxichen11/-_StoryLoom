/* 故事织机 StoryLoom - 前端逻辑（原生 JS，无框架） */
const $ = (s) => document.querySelector(s);
const $$ = (s) => document.querySelectorAll(s);
const API = "";
let state = { work: null, ws: null, raw: "" };

/* ---------- 通用 ---------- */
function toast(msg) {
  const t = $("#toast"); t.textContent = msg; t.classList.add("show");
  setTimeout(() => t.classList.remove("show"), 2200);
}
async function api(path, opts) {
  const r = await fetch(API + path, opts);
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
  return r.json();
}
function gotoStage(n) {
  $$(".stage").forEach((s) => s.classList.toggle("show", +s.dataset.stage === n));
  $$(".spine .step").forEach((s) => s.classList.toggle("active", +s.dataset.go === n));
  if (n === 4) renderChapters();
  if (n === 6) renderOverview();
}
$$(".spine .step").forEach((s) => s.addEventListener("click", () => {
  if (!state.work) return toast("请先新建或选择作品");
  gotoStage(+s.dataset.go);
}));

/* ---------- SSE 流式读取 ---------- */
async function sse(path, opts, onDelta, onDone) {
  const r = await fetch(API + path, { ...opts, headers: { "Content-Type": "application/json", ...(opts.headers || {}) } });
  const reader = r.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    const parts = buf.split("\n\n"); buf = parts.pop();
    for (const p of parts) {
      const ev = (p.match(/event: (.*)/) || [])[1];
      const dataLine = (p.match(/data: (.*)/s) || [])[1];
      if (!dataLine) continue;
      const data = JSON.parse(dataLine);
      if (ev === "delta") onDelta && onDelta(data.text);
      else if (ev === "done") onDone && onDone(data);
    }
  }
}

/* ---------- 作品管理 ---------- */
async function loadWork(id) {
  state.work = await api(`/api/works/${id}`);
  $("#workTitle").textContent = state.work.title;
  $("#workMeta").textContent = `阶段 ${state.work.stage} · ${state.work.chapters.length} 章`;
  hydrate();
  closeDrawer();
}
function hydrate() {
  const w = state.work;
  if (w.gene && w.gene.genre) { $("#inspText").value = w.gene.raw_input || ""; fillGeneForm(w.gene); }
  if (w.characters.length) renderCast(w.characters);
  if (w.outline.beats.length) renderOutline(w.outline);
}
async function refreshWorkList() {
  const { works } = await api("/api/works");
  $("#workList").innerHTML = works.map((w) =>
    `<div class="chapcard" style="margin-bottom:8px" onclick="loadWork('${w.id}')">
      <b style="font-family:var(--serif)">${w.title}</b>
      <div class="muted" style="font-size:11px">阶段${w.stage} · ${w.chapters}章 · ${(w.updated_at || "").slice(0, 10)}</div>
    </div>`).join("") || `<p class="muted">还没有作品，新建一部吧。</p>`;
}
$("#btnNewWork").addEventListener("click", async () => {
  const title = $("#newWorkTitle").value.trim() || "未命名作品";
  const w = await api("/api/works", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title }) });
  $("#newWorkTitle").value = "";
  await refreshWorkList(); loadWork(w.id); toast("作品已创建");
});
window.loadWork = loadWork;

/* ---------- Stage 1 灵感 ---------- */
$("#btnExtract").addEventListener("click", async () => {
  if (!state.work) return toast("请先新建作品");
  const text = $("#inspText").value.trim();
  if (!text) return toast("先写点灵感");
  $("#geneCard").style.display = "block"; $("#geneStream").textContent = ""; $("#geneForm").style.display = "none";
  $("#btnExtract").disabled = true; $("#extractHint").textContent = "缪斯推演中…";
  try {
    await sse(`/api/gen/${state.work.id}/gene/extract`, { method: "POST", body: JSON.stringify({ text }) },
      (t) => { $("#geneStream").textContent += t; },
      (d) => { fillGeneForm(d.gene); $("#geneForm").style.display = "block"; $("#geneStream").textContent = ""; toast("基因已提取"); });
  } catch (e) { toast(e.message); }
  $("#btnExtract").disabled = false; $("#extractHint").textContent = "";
});
function fillGeneForm(g) {
  $("#geneCard").style.display = "block"; $("#geneForm").style.display = "block";
  $("#g_genre").value = g.genre || ""; $("#g_mood").value = g.mood || "";
  $("#g_tension").value = g.core_tension || ""; $("#g_premise").value = g.world_premise || "";
  $("#g_keywords").value = (g.keywords || []).join("、");
}
$("#saveGene").addEventListener("click", async () => {
  const gene = {
    genre: $("#g_genre").value, mood: $("#g_mood").value, core_tension: $("#g_tension").value,
    world_premise: $("#g_premise").value, keywords: $("#g_keywords").value.split(/[、,，]/).filter(Boolean),
  };
  await api(`/api/works/${state.work.id}/gene`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ gene }) });
  await loadWork(state.work.id); gotoStage(2); toast("已保存");
});

/* ---------- Stage 2 选角 ---------- */
$("#btnCast").addEventListener("click", async () => {
  $("#castStream").textContent = ""; $("#btnCast").disabled = true;
  try {
    await sse(`/api/gen/${state.work.id}/cast/generate`, { method: "POST", body: "{}" },
      (t) => { $("#castStream").textContent = ($("#castStream").textContent + t).slice(-600); },
      (d) => { renderCast(d.characters); state.work.characters = d.characters; $("#castStream").textContent = ""; toast("角色已就位"); });
  } catch (e) { toast(e.message); }
  $("#btnCast").disabled = false;
});
function renderCast(chars) {
  $("#castGrid").innerHTML = chars.map((c) => `
    <div class="charcard" style="border-left-color:${c.accent || "#c8612b"}">
      <h4>${c.name}</h4><div class="arche">${c.archetype}</div>
      <p><b>性格</b> ${c.temper || "-"}</p>
      <p><b>动机</b> ${c.drive || "-"}</p>
      <p><b>弱点</b> ${c.flaw || "-"}</p>
      <p class="muted" style="font-size:11.5px">「${c.tagline || ""}」</p>
    </div>`).join("");
  $("#toOutline").style.display = chars.length ? "inline-flex" : "none";
}
$("#btnAddChar").addEventListener("click", async () => {
  const name = prompt("角色名"); if (!name) return;
  const chars = [...(state.work.characters || []), { name, archetype: "配角", accent: "#2f7d6b" }];
  const saved = await api(`/api/works/${state.work.id}/characters`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ characters: chars }) });
  state.work.characters = saved; renderCast(saved);
});
$("#toOutline").addEventListener("click", () => gotoStage(3));

/* ---------- Stage 3 经纬 ---------- */
$("#btnOutline").addEventListener("click", async () => {
  $("#outlineStream").textContent = ""; $("#btnOutline").disabled = true;
  try {
    await sse(`/api/gen/${state.work.id}/outline/generate`, { method: "POST", body: "{}" },
      (t) => { $("#outlineStream").textContent = ($("#outlineStream").textContent + t).slice(-600); },
      (d) => { renderOutline(d.outline); state.work.outline = d.outline; $("#outlineStream").textContent = ""; toast("经纬已成"); });
  } catch (e) { toast(e.message); }
  $("#btnOutline").disabled = false;
});
function renderOutline(o) {
  $("#beatsCard").style.display = "block"; $("#threadsCard").style.display = o.threads.length ? "block" : "none";
  $("#beatsList").innerHTML = o.beats.map((b) => `
    <div class="beat"><div class="ord ${b.kind}">${b.order}</div>
      <div><h4>${b.title}</h4><small>${b.summary}</small>
      <div>${(b.cast || []).map((n) => `<span class="tag">${n}</span>`).join("")}</div></div></div>`).join("");
  $("#threadsList").innerHTML = o.threads.map((t) =>
    `<p style="padding:6px 0"><span class="tag" style="background:${t.accent};color:#fff">${t.name}</span> ${t.summary}</p>`).join("");
  $("#btnLock").style.display = o.beats.length ? "inline-flex" : "none";
}
$("#btnLock").addEventListener("click", async () => {
  await api(`/api/works/${state.work.id}/outline`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ locked: true }) });
  await loadWork(state.work.id); gotoStage(4); toast("已锁定并拆分章回");
});

/* ---------- Stage 4 章回 ---------- */
function renderChapters() {
  const chs = state.work?.chapters || [];
  $("#chapGrid").innerHTML = chs.map((c) => `
    <div class="chapcard" onclick="enterTheater(${c.num})">
      <div style="display:flex;justify-content:space-between;align-items:center">
        <b style="font-family:var(--serif);font-size:15px">第${c.num}章 ${c.title}</b>
        <span class="st ${c.status}">${({ todo: "待创作", drafting: "创作中", done: "已完成" })[c.status]}</span>
      </div>
      <p class="muted" style="font-size:12px;margin-top:6px">${c.brief || "（点击进入戏台或生成微纲）"}</p>
      <div style="margin-top:6px">${(c.cast || []).map((n) => `<span class="tag">${n}</span>`).join("")}</div>
      <div class="btn-row" style="margin-top:8px">
        <button class="btn ghost" style="padding:5px 12px" onclick="event.stopPropagation();genBrief(${c.num})">生成微纲</button>
        <button class="btn amber" style="padding:5px 12px" onclick="event.stopPropagation();enterTheater(${c.num})">进戏台</button>
      </div>
    </div>`).join("");
}
window.genBrief = async (num) => {
  toast("织线师撰写微纲中…");
  await sse(`/api/gen/${state.work.id}/chapters/${num}/brief/generate`, { method: "POST", body: "{}" },
    null, async () => { await loadWork(state.work.id); renderChapters(); toast("微纲已生成"); });
};
window.enterTheater = (num) => { state.curChapter = num; const c = state.work.chapters.find((x) => x.num === num); $("#curChapName").textContent = `第${num}章 ${c.title}`; gotoStage(5); resetTheater(); };

/* ---------- Stage 5 圆桌戏台（WebSocket） ---------- */
function resetTheater() {
  $("#theaterSetup").style.display = "block"; $("#theaterMain").style.display = "none";
  $("#rawCard").style.display = "none"; $("#manuCard").style.display = "none"; $("#finishPanel").style.display = "none";
  $("#stream").innerHTML = "";
  $("#castMini").innerHTML = (state.work.characters || []).map((c) =>
    `<div class="castline"><span class="swatch" style="background:${c.accent}"></span>${c.name}<span class="muted" style="font-size:11px">· ${c.archetype}</span></div>`).join("");
}
function accentOf(name) { const c = (state.work.characters || []).find((x) => x.name === name); return c ? c.accent : "#274060"; }

function openWS() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const url = `${proto}://${location.host}/ws/roundtable/${state.work.id}/${state.curChapter}`;
  const ws = new WebSocket(url);
  state.ws = ws;
  ws.onmessage = (e) => handleWS(JSON.parse(e.data));
  ws.onclose = () => {};
  return ws;
}
function send(obj) { state.ws && state.ws.readyState === 1 && state.ws.send(JSON.stringify(obj)); }

$("#btnAction").addEventListener("click", () => {
  $("#theaterSetup").style.display = "none"; $("#theaterMain").style.display = "grid"; $("#stream").innerHTML = "";
  const ws = openWS();
  ws.onopen = () => send({ action: "start", budget: +$("#budget").value, ceiling: +$("#ceiling").value });
});
$("#btnPause").addEventListener("click", function () {
  if (this.textContent === "暂停") { send({ action: "pause" }); this.textContent = "继续"; }
  else { send({ action: "resume" }); this.textContent = "暂停"; }
});
$("#btnStop").addEventListener("click", () => send({ action: "stop" }));
$("#btnPolish").addEventListener("click", () => {
  $("#manuCard").style.display = "block"; $("#manuscript").textContent = "";
  send({ action: "polish", text: $("#rawText").value });
});

function bubble(cls, who, text, swatch) {
  const div = document.createElement("div");
  div.className = `bubble ${cls}`;
  const sw = swatch ? `<span class="swatch" style="background:${swatch}"></span>` : "";
  div.innerHTML = `${who ? `<div class="who">${sw}${who}</div>` : ""}<div class="body">${text}</div>`;
  $("#stream").appendChild(div); $("#stream").scrollTop = $("#stream").scrollHeight;
  return div;
}
function renderTrace(traceArr) {
  if (!traceArr || !traceArr.length) return "";
  const steps = traceArr.map((s) =>
    `<div class="step"><span class="lbl">thought</span> ${(s.thought || "").replace(/</g, "&lt;")}
     ${s.tool ? `<br><span class="lbl">action</span> ${s.tool}(${s.tool_input || ""})` : ""}
     ${s.observation ? `<br><span class="lbl">observation</span> ${(s.observation || "").replace(/</g, "&lt;")}` : ""}</div>`).join("");
  return `<details class="trace"><summary>查看 ReAct 推理链（${traceArr.length} 步）</summary>${steps}</details>`;
}
function handleWS(m) {
  switch (m.type) {
    case "phase": if (m.phase === "polishing") toast("誊抄师润色中…"); break;
    case "thinking": {
      const d = bubble("", m.speaker, `<span class="thinking">推理中</span>`, accentOf(m.speaker));
      d.dataset.pending = "1"; break;
    }
    case "line": {
      const pend = [...$$("#stream .bubble")].reverse().find((b) => b.dataset.pending);
      const html = m.text.replace(/</g, "&lt;") + renderTrace(m.trace);
      if (pend) { pend.querySelector(".body").innerHTML = html; pend.dataset.pending = ""; }
      else bubble("", m.speaker, html, accentOf(m.speaker));
      updateProg(m.words); break;
    }
    case "showrunner": bubble("scene", "", m.text.replace(/</g, "&lt;")); updateProg(m.words); break;
    case "progress": updateProg(m.words); break;
    case "ended":
      state.raw = m.transcript; $("#rawCard").style.display = "block"; $("#rawText").value = m.transcript;
      $("#finishPanel").style.display = "block"; toast(`研讨收束 · ${m.words}字`); break;
    case "polish_delta": $("#manuscript").textContent += m.text; break;
    case "polished": $("#manuscript").textContent = m.manuscript; loadWork(state.work.id); toast("正文已誊抄"); break;
    case "error": toast(m.message); break;
  }
}
function updateProg(words) {
  if (words == null) return;
  const budget = +$("#budget").value, ceiling = +$("#ceiling").value;
  $("#wordPill").textContent = `${words} / ${budget} 字`;
  const bar = $("#progbar"); bar.style.width = Math.min(100, (words / ceiling) * 100) + "%";
  bar.className = "progbar" + (words >= ceiling ? " max" : words >= budget ? " over" : "");
}

/* ---------- Stage 6 付梓 ---------- */
function renderOverview() {
  const chs = state.work?.chapters || [];
  $("#stChap").textContent = chs.length;
  $("#stWords").textContent = chs.reduce((s, c) => s + (c.words || 0), 0);
  $("#stDone").textContent = chs.filter((c) => c.status === "done").length;
}
$("#btnAudit").addEventListener("click", async () => {
  $("#auditCard").style.display = "block"; $("#auditBody").innerHTML = '<span class="muted">审稿人复核中…</span>';
  let buf = "";
  await sse(`/api/gen/${state.work.id}/audit`, { method: "POST", body: "{}" },
    (t) => { buf += t; },
    (d) => {
      const r = d.report || {};
      $("#auditBody").innerHTML = `
        <p><b style="font-size:22px;font-family:var(--serif);color:var(--navy)">${r.score ?? "—"}</b> / 100　${r.verdict || ""}</p>
        ${(r.issues || []).map((i) => `<div class="beat"><div class="ord ${i.level === "high" ? "climax" : ""}">${i.level === "high" ? "!" : "·"}</div><div><h4>${i.where || ""}</h4><small>${i.problem}　<b style="color:var(--teal)">建议：</b>${i.fix || ""}</small></div></div>`).join("")}`;
    });
});
function download(name, content) {
  const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([content], { type: "text/plain;charset=utf-8" }));
  a.download = name; a.click();
}
function compile(sep) {
  const w = state.work;
  return `${w.title}\n\n` + w.chapters.filter((c) => c.manuscript).map((c) => `${sep}第${c.num}章 ${c.title}\n\n${c.manuscript}`).join("\n\n");
}
$("#exMd").addEventListener("click", () => download(`${state.work.title}.md`, compile("## ")));
$("#exTxt").addEventListener("click", () => download(`${state.work.title}.txt`, compile("")));

/* ---------- 设置抽屉 ---------- */
function openDrawer() { $("#drawer").classList.add("open"); $("#overlay").classList.add("show"); refreshWorkList(); }
function closeDrawer() { $("#drawer").classList.remove("open"); $("#overlay").classList.remove("show"); }
$("#openSettings").addEventListener("click", openDrawer);
$("#switchWork").addEventListener("click", openDrawer);
$("#overlay").addEventListener("click", closeDrawer);
$("#saveSettings").addEventListener("click", async () => {
  const patch = {
    providers: { deepseek: { api_key: $("#setKey").value.trim() } },
    role_models: {
      muse: $("#setReason").value, loomplanner: $("#setReason").value, auditor: $("#setReason").value,
      castmaker: $("#setChat").value, showrunner: $("#setChat").value, actor: $("#setChat").value, scribe: $("#setChat").value,
    },
  };
  const r = await api("/api/settings", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ patch }) });
  updateKeyChip(r.has_key); toast("设置已保存");
});
function updateKeyChip(has) {
  const c = $("#keyChip"); c.textContent = has ? "密钥已配置" : "密钥未配置";
  c.className = "keychip " + (has ? "ok" : "no");
}

/* ---------- 启动 ---------- */
(async function init() {
  try {
    const h = await api("/api/settings/health"); updateKeyChip(h.has_key);
    const { works } = await api("/api/works");
    if (works.length) loadWork(works[0].id); else openDrawer();
    refreshWorkList();
  } catch (e) { console.error(e); }
})();
