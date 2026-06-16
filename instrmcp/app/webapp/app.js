/* InstrMCP dashboard — vanilla JS, no build step.
 * Talks to the supervisor API on the same origin: /status, /logs, /doctor,
 * /profiles, /measureit, and the /events WebSocket.
 */
"use strict";

const $ = (id) => document.getElementById(id);
const MAX_LOG_LINES = 1000;

let logRecords = []; // {component, line, ts}
let logFilter = "";

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------

function renderStatus(s) {
  if (!s) return;
  $("profile-name").textContent = "profile: " + (s.profile || "?");

  const agg = (s.aggregate || "idle").toLowerCase();
  const badge = $("aggregate");
  badge.textContent = agg;
  badge.className = "badge badge-" + agg;

  // Component cards.
  const cards = $("status-cards");
  cards.innerHTML = "";
  const comps = s.components || {};
  for (const key of Object.keys(comps)) {
    const c = comps[key];
    const div = document.createElement("div");
    div.className = "card state-" + (c.state || "idle");
    div.innerHTML =
      `<div class="name">${key}</div>` +
      `<div class="state">${c.state || ""}</div>` +
      `<div class="detail">${escapeHtml(c.detail || "")}</div>`;
    cards.appendChild(div);
  }

  // Open-lab link.
  const lab = $("open-lab");
  if (s.jupyter_url) {
    lab.href = s.jupyter_url;
    lab.classList.remove("disabled");
  } else {
    lab.removeAttribute("href");
  }

  // MeasureIt.
  renderMeasureIt(s.measureit);
}

function renderMeasureIt(m) {
  const panel = $("measureit-panel");
  if (!m || !m.enabled) {
    panel.hidden = true;
    return;
  }
  panel.hidden = false;
  const body = $("measureit-body");
  const status = m.status;
  if (!status || !status.active) {
    body.innerHTML = "no active sweeps";
    return;
  }
  const sweeps = status.sweeps || {};
  const rows = Object.keys(sweeps).map((name) => {
    const sw = sweeps[name];
    const prog =
      sw.progress != null ? ` — ${Math.round(sw.progress * 100)}%` : "";
    return `<div class="sweep"><b>${escapeHtml(name)}</b> [${sw.state || "?"}]${prog}</div>`;
  });
  body.innerHTML = rows.join("") || "no active sweeps";
}

function appendLogRecord(rec) {
  logRecords.push(rec);
  if (logRecords.length > MAX_LOG_LINES) {
    logRecords = logRecords.slice(-MAX_LOG_LINES);
  }
  renderLogs();
}

function renderLogs() {
  const el = $("logs");
  const atBottom = el.scrollTop + el.clientHeight >= el.scrollHeight - 20;
  const filtered = logFilter
    ? logRecords.filter((r) => r.component === logFilter)
    : logRecords;
  el.innerHTML = filtered
    .map(
      (r) =>
        `<span class="log-${r.component}">[${r.component}]</span> ${escapeHtml(r.line)}`
    )
    .join("\n");
  if (atBottom) el.scrollTop = el.scrollHeight;
  refreshLogFilterOptions();
}

function refreshLogFilterOptions() {
  const sel = $("log-filter");
  const have = new Set(Array.from(sel.options).map((o) => o.value));
  const comps = new Set(logRecords.map((r) => r.component));
  for (const c of comps) {
    if (!have.has(c)) {
      const opt = document.createElement("option");
      opt.value = c;
      opt.textContent = c;
      sel.appendChild(opt);
    }
  }
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function setMsg(text) {
  $("action-msg").textContent = text || "";
}

// ---------------------------------------------------------------------------
// Data fetching
// ---------------------------------------------------------------------------

async function loadProfiles() {
  try {
    const profiles = await (await fetch("/profiles")).json();
    $("profiles").innerHTML = profiles
      .map(
        (p) =>
          `<li>${escapeHtml(p.name)} <span class="src">[${p.source}]</span></li>`
      )
      .join("");
  } catch (e) {
    /* ignore */
  }
}

async function loadInitialLogs() {
  try {
    const data = await (await fetch("/logs?lines=300")).json();
    logRecords = data.logs || [];
    renderLogs();
  } catch (e) {
    /* ignore */
  }
}

async function runDoctor() {
  $("doctor").textContent = "Running…";
  try {
    const rep = await (await fetch("/doctor")).json();
    const sym = { ok: "OK  ", warn: "WARN", fail: "FAIL" };
    const lines = rep.checks.map((c) => {
      let s = `[${sym[c.status] || c.status}] ${c.name}: ${c.detail}`;
      if (c.fix && c.status !== "ok") s += `\n        fix: ${c.fix}`;
      return s;
    });
    $("doctor").textContent = lines.join("\n");
  } catch (e) {
    $("doctor").textContent = "Doctor request failed: " + e;
  }
}

async function post(path) {
  setMsg("…");
  try {
    const r = await fetch(path, { method: "POST" });
    const data = await r.json();
    setMsg(data.message || JSON.stringify(data));
    return data;
  } catch (e) {
    setMsg("Request failed: " + e);
  }
}

// ---------------------------------------------------------------------------
// Event stream
// ---------------------------------------------------------------------------

function connectEvents() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/events`);
  ws.onopen = () => $("conn").className = "conn conn-up";
  ws.onclose = () => {
    $("conn").className = "conn conn-down";
    setTimeout(connectEvents, 2000); // auto-reconnect
  };
  ws.onmessage = (ev) => {
    let msg;
    try {
      msg = JSON.parse(ev.data);
    } catch (e) {
      return;
    }
    if (msg.type === "status") renderStatus(msg.status);
    else if (msg.type === "log")
      appendLogRecord({ component: msg.component, line: msg.line, ts: msg.ts });
    else if (msg.type === "measureit")
      renderMeasureIt({ enabled: true, status: msg.status });
  };
}

// ---------------------------------------------------------------------------
// Wiring
// ---------------------------------------------------------------------------

function init() {
  $("btn-doctor").onclick = runDoctor;
  $("btn-restart-kernel").onclick = () => post("/restart-kernel");
  $("btn-restart-mcp").onclick = () => post("/restart-mcp");
  $("btn-stop").onclick = () => {
    if (confirm("Stop instrmcp (this shuts down JupyterLab)?")) post("/stop");
  };
  $("log-filter").onchange = (e) => {
    logFilter = e.target.value;
    renderLogs();
  };

  // Prime from REST, then switch to the live stream.
  fetch("/status")
    .then((r) => r.json())
    .then(renderStatus)
    .catch(() => {});
  loadInitialLogs();
  loadProfiles();
  connectEvents();
}

document.addEventListener("DOMContentLoaded", init);
