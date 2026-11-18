const $ = (s, r = document) => r.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

let token = "";
try { token = localStorage.getItem("token") || ""; } catch {}
let brief = {};
let tab = "ai_business";
let chatHistory = [];

async function api(path, opts = {}) {
  const res = await fetch(path, {
    ...opts,
    headers: { "Content-Type": "application/json", "X-Token": token, ...(opts.headers || {}) },
  });
  if (res.status === 401) {
    token = prompt("Enter your app token") || "";
    try { localStorage.setItem("token", token); } catch {}
    return api(path, opts);
  }
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || res.statusText);
  return res.json();
}

function toast(msg) {
  const t = $("#toast");
  t.textContent = msg; t.classList.add("show");
  setTimeout(() => t.classList.remove("show"), 1800);
}

async function load() {
  try { brief = await api("/api/brief"); } catch (e) { toast(e.message); }
  for (const b of document.querySelectorAll("#tabs [data-tab]")) {
    const n = (brief[b.dataset.tab] || []).length;
    const c = $(".count", b);
    if (c) c.textContent = n ? n : "";
  }
  render();
}

function weightLabel(w) { return w ? ` <span class="w">${w > 0 ? "+" : ""}${w}</span>` : ""; }

function tuneRow(kind, value, label, weight) {
  return `<div class="row"><span class="name">${esc(label)}${weightLabel(weight)}</span>
    <span><button class="up" data-kind="${kind}" data-value="${esc(value)}" data-dir="1" aria-label="More ${esc(label)}">▲</button>
    <button class="down" data-kind="${kind}" data-value="${esc(value)}" data-dir="-1" aria-label="Less ${esc(label)}">▼</button></span></div>`;
}

function card(e) {
  const when = new Date(e.date.replace(" ", "T") + "Z").toLocaleDateString(undefined, { month: "short", day: "numeric" });
  const topics = Object.entries(e.topic_weights).map(([t, w]) => tuneRow("topic", t, "#" + t, w)).join("");
  return `<article class="card" data-id="${esc(e.id)}">
    <div class="meta">${esc(e.sender)} · ${when}</div>
    <h3>${esc(e.subject)}</h3>
    <p>${esc(e.summary)}</p>
    ${e.why ? `<div class="why">${esc(e.why)}</div>` : ""}
    <div class="actions">
      <a class="btn primary" target="_blank" rel="noopener" href="https://mail.google.com/mail/u/0/#all/${esc(e.thread_id)}">Open</a>
      <button class="btn" data-tune>Tune ranking</button>
    </div>
    <div class="tune" hidden>${tuneRow("sender", e.sender_email, "More from " + e.sender, e.sender_weight)}${topics}</div>
  </article>`;
}

function render() {
  const isAsk = tab === "ask";
  $("#list").hidden = isAsk; $("#ask").hidden = !isAsk;
  for (const b of document.querySelectorAll("#tabs [data-tab]")) b.classList.toggle("active", b.dataset.tab === tab);
  if (isAsk) return;
  const items = brief[tab] || [];
  $("#list").innerHTML = items.length ? items.map(card).join("") : `<div class="empty">Nothing here yet. Tap Refresh to check Gmail.</div>`;
}

document.addEventListener("click", async (ev) => {
  const t = ev.target.closest("button");
  if (!t) return;
  if (t.dataset.tab) { tab = t.dataset.tab; render(); return; }
  if (t.hasAttribute("data-tune")) { $(".tune", t.closest(".card")).toggleAttribute("hidden"); return; }
  if (t.dataset.kind) {
    await api("/api/feedback", { method: "POST", body: JSON.stringify({ kind: t.dataset.kind, value: t.dataset.value, direction: +t.dataset.dir }) });
    toast(+t.dataset.dir > 0 ? "Noted: more like this" : "Noted: less like this");
    const open = new Set([...document.querySelectorAll(".tune:not([hidden])")].map((n) => n.closest(".card").dataset.id));
    await load();
    for (const id of open) { const c = document.querySelector(`.card[data-id="${CSS.escape(id)}"] .tune`); if (c) c.hidden = false; }
  }
});

$("#sync").addEventListener("click", async (ev) => {
  const b = ev.currentTarget; b.disabled = true; b.textContent = "Checking…";
  try { const r = await api("/api/sync", { method: "POST" }); toast(r.status === "ok" ? `${r.fetched} new emails` : r.status); await load(); }
  catch (e) { toast(e.message); }
  b.disabled = false; b.textContent = "Refresh";
});

$("#askform").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const q = $("#q").value.trim(); if (!q) return;
  $("#q").value = "";
  const log = $("#log");
  log.insertAdjacentHTML("beforeend", `<div class="msg me">${esc(q)}</div>`);
  const pending = document.createElement("div"); pending.className = "msg bot"; pending.textContent = "Reading your emails…";
  log.append(pending); pending.scrollIntoView({ block: "end" });
  try {
    const r = await api("/api/chat", { method: "POST", body: JSON.stringify({ question: q, history: chatHistory, deep: $("#deep").checked }) });
    chatHistory.push({ role: "user", content: q }, { role: "assistant", content: r.answer });
    const steps = r.steps.length ? `<details><summary>${r.steps.length} search step${r.steps.length > 1 ? "s" : ""}</summary>${r.steps.map((s) => `<div>${esc(s)}</div>`).join("")}</details>` : "";
    const src = r.sources.length ? `<small>Based on:<br>${r.sources.map((s) => `${esc(s.sender)}: ${esc(s.subject)} (${esc(s.date)})`).join("<br>")}</small>` : "";
    const u = r.usage, k = (n) => (n / 1000).toFixed(1) + "k";
    const cost = u ? `<small class="usage">${esc(u.model)} · ${u.steps} step${u.steps === 1 ? "" : "s"} · ${k(u.input + u.cache_read + u.cache_write)} in (${k(u.cache_read)} cached) · ${u.output} out · ${(u.ms / 1000).toFixed(1)}s</small>` : "";
    pending.innerHTML = `${esc(r.answer)}${steps}${src}${cost}`;
  } catch (e) { pending.textContent = "Error: " + e.message; }
  pending.scrollIntoView({ block: "end" });
});

if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});
load();
