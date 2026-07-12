/* ============================================================
   Yantra Rakshak - dashboard controller
   ============================================================ */
(function () {
  "use strict";
  const C = window.YRCharts;

  const state = {
    view: "overview",
    nodes: {},              // machine_id -> node status
    alerts: [],             // recent alert events (with advisory)
    spark: {},              // machine_id -> [mse...]
    selected: null,
    llm: { available: false, model: "—" },
  };

  const MACHINE_ICONS = {
    motor: "⚡", pump: "💧", lathe: "⚙", compressor: "🌀", default: "⚙",
  };
  const icon = (t) => MACHINE_ICONS[t] || MACHINE_ICONS.default;
  const $ = (id) => document.getElementById(id);

  /* ---------------- WebSocket ---------------- */
  let ws, reconnectTimer;
  function connect() {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    ws = new WebSocket(`${proto}://${location.host}/ws`);

    ws.onopen = () => setConn(true);
    ws.onclose = () => { setConn(false); scheduleReconnect(); };
    ws.onerror = () => ws.close();
    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data);
      if (msg.type === "nodes") ingestNodes(msg.nodes);
      else if (msg.type === "event") ingestEvent(msg.event);
      else if (msg.type === "alerts") { state.alerts = msg.alerts.reverse(); renderAlerts(); }
      else if (msg.type === "advisory") upgradeAdvisory(msg.id, msg.advisory);
    };
  }
  function scheduleReconnect() {
    clearTimeout(reconnectTimer);
    reconnectTimer = setTimeout(connect, 2500);
  }
  function setConn(ok) {
    $("wsDot").className = "dot " + (ok ? "on" : "off");
    $("wsText").textContent = ok ? "Cloud connected" : "Reconnecting…";
  }

  /* ---------------- ingest ---------------- */
  function ingestNodes(nodes) {
    nodes.forEach((n) => { state.nodes[n.machine_id] = n; });
    renderKpis(); renderCurrentView();
  }

  function ingestEvent(ev) {
    const id = ev.machine_id;
    (state.spark[id] = state.spark[id] || []).push(ev.mse_score);
    if (state.spark[id].length > 40) state.spark[id].shift();

    // keep node snapshot fresh even before the periodic nodes push
    const prev = state.nodes[id] || {};
    state.nodes[id] = Object.assign({}, prev, {
      machine_id: id,
      machine_type: ev.machine_type,
      location: ev.location,
      severity: ev.severity,
      fault_type: ev.fault_type,
      mse_score: ev.mse_score,
      confidence: ev.confidence,
      rpm: ev.rpm,
      temp_c: (ev.features || {}).temp_c || 0,
      online: true,
    });

    if (ev.severity !== "OK" && ev.advisory) {
      state.alerts.unshift(ev);
      if (state.alerts.length > 60) state.alerts.pop();
      bumpAlertBadge();
    }

    // live detail refresh if this machine is open
    if (state.view === "machines" && state.selected === id) renderMachineDetail(id);
    if (state.view === "alerts") renderAlerts();

    renderKpis();
    if (state.view === "overview") renderOverview();
  }

  function upgradeAdvisory(id, advisory) {
    const a = state.alerts.find((x) => x.id === id);
    if (!a) return;
    a.advisory = advisory;
    if (state.view === "alerts") renderAlerts();
  }

  /* ---------------- KPIs ---------------- */
  function renderKpis() {
    const ns = Object.values(state.nodes);
    const online = ns.filter((n) => n.online).length;
    const warn = ns.filter((n) => n.severity === "WARNING").length;
    const crit = ns.filter((n) => n.severity === "CRITICAL").length;
    const events = ns.reduce((a, n) => a + (n.events_total || 0), 0);
    $("kpiMachines").textContent = ns.length;
    $("kpiOnline").textContent = online;
    $("kpiWarn").textContent = warn;
    $("kpiCrit").textContent = crit;
    $("kpiEvents").textContent = events;
  }

  function bumpAlertBadge() {
    const b = $("navAlertBadge");
    b.hidden = false;
    b.textContent = state.alerts.length;
  }

  /* ---------------- OVERVIEW ---------------- */
  function renderOverview() {
    const grid = $("machineGrid");
    const ns = Object.values(state.nodes).sort((a, b) => a.machine_id.localeCompare(b.machine_id));
    if (!ns.length) {
      grid.innerHTML = `<div class="empty">Waiting for nodes to publish telemetry…<br/><br/>
        Run <code>python simulator.py</code> in the <b>node/</b> folder.</div>`;
      return;
    }
    grid.innerHTML = ns.map((n) => {
      const sev = n.online ? n.severity : "OFFLINE";
      const spark = C.sparkline(state.spark[n.machine_id], n.severity);
      return `
        <div class="card" data-mid="${n.machine_id}">
          <div class="card-top">
            <div>
              <div class="card-name">${icon(n.machine_type)} ${n.machine_id}</div>
              <div class="card-loc">${n.location} &middot; ${n.rpm} rpm</div>
            </div>
            <span class="pill ${sev}">${sev}</span>
          </div>
          <div class="card-body">
            <div class="gauge">${C.gauge(n.mse_score || 1, n.severity)}</div>
            <div class="card-metrics">
              <div class="metric"><span>Confidence</span><b>${Math.round((n.confidence||0)*100)}%</b></div>
              <div class="metric"><span>Temp</span><b>${(n.temp_c||0).toFixed(1)}°C</b></div>
              <div class="metric"><span>Events</span><b>${n.events_total||0}</b></div>
              <div class="metric"><span>Alerts</span><b>${n.alerts_total||0}</b></div>
            </div>
          </div>
          <div class="card-spark">${spark}</div>
          <div class="card-foot">
            <span class="fault-tag ${n.fault_type}">${(n.fault_type||"NORMAL").replace(/_/g," ")}</span>
            <span>${n.online ? "● live" : "○ offline"}</span>
          </div>
        </div>`;
    }).join("");

    grid.querySelectorAll(".card").forEach((el) =>
      el.addEventListener("click", () => openMachine(el.dataset.mid))
    );
  }

  /* ---------------- MACHINES DETAIL ---------------- */
  function renderMachineList() {
    const list = $("machineList");
    const ns = Object.values(state.nodes).sort((a, b) => a.machine_id.localeCompare(b.machine_id));
    list.innerHTML = ns.map((n) => `
      <div class="mlist-item ${state.selected===n.machine_id?"active":""}" data-mid="${n.machine_id}">
        <span class="status-dot" style="background:${C.sevColor(n.severity)}"></span>
        <div>
          <div class="mlist-name">${n.machine_id}</div>
          <div class="mlist-sub">${n.machine_type} &middot; ${n.location}</div>
        </div>
      </div>`).join("");
    list.querySelectorAll(".mlist-item").forEach((el) =>
      el.addEventListener("click", () => { state.selected = el.dataset.mid; renderMachineList(); renderMachineDetail(el.dataset.mid); })
    );
  }

  async function renderMachineDetail(mid) {
    const n = state.nodes[mid];
    const box = $("machineDetail");
    if (!n) { box.innerHTML = `<div class="empty">Select a machine.</div>`; return; }

    box.innerHTML = `
      <div class="detail-head">
        <div>
          <h3>${icon(n.machine_type)} ${n.machine_id}</h3>
          <div class="card-loc">${n.location} &middot; ${n.machine_type} &middot; ${n.rpm} rpm</div>
        </div>
        <span class="pill ${n.severity}">${n.severity}</span>
      </div>
      <div class="detail-metrics">
        <div class="dm"><span>Anomaly Score</span><b>${(n.mse_score||1).toFixed(2)}×</b></div>
        <div class="dm"><span>Fault</span><b style="font-size:14px">${(n.fault_type||"NORMAL").replace(/_/g," ")}</b></div>
        <div class="dm"><span>Confidence</span><b>${Math.round((n.confidence||0)*100)}%</b></div>
        <div class="dm"><span>Temperature</span><b>${(n.temp_c||0).toFixed(1)}°C</b></div>
      </div>
      <div class="chart-block">
        <h4>Anomaly Score History (green→amber→red bands)</h4>
        <canvas class="chart-canvas" id="histChart"></canvas>
      </div>
      <div class="chart-block">
        <h4>Live Vibration Waveform (MPU-6050)</h4>
        <canvas class="chart-canvas" id="waveChart"></canvas>
      </div>`;

    // fetch history
    try {
      const res = await fetch(`/api/machine/${mid}/history?limit=120`);
      const data = await res.json();
      const series = (data.history || []).map((h) => h.mse_score);
      const last = data.history[data.history.length - 1];
      C.lineChart($("histChart"), series.length ? series : [1], { height: 200 });
      C.waveform($("waveChart"), (last && last.waveform) || [], { height: 160, color: C.sevColor(n.severity) });
    } catch (e) {
      C.lineChart($("histChart"), state.spark[mid] || [1], { height: 200 });
    }
  }

  function openMachine(mid) {
    state.selected = mid;
    switchView("machines");
  }

  /* ---------------- ALERTS ---------------- */
  function renderAlerts() {
    const wrap = $("alertsWrap");
    if (!state.alerts.length) {
      wrap.innerHTML = `<div class="empty">No alerts yet. Healthy fleet or waiting for telemetry…</div>`;
      return;
    }
    wrap.innerHTML = state.alerts.map((a) => {
      const adv = a.advisory || {};
      const t = new Date(a.ts).toLocaleTimeString();
      return `
        <div class="alert-card ${a.severity}">
          <div class="alert-head">
            <div class="alert-title">${icon(a.machine_type)} ${a.machine_id} &middot; ${(a.fault_type||"").replace(/_/g," ")}</div>
            <span class="pill ${a.severity}">${a.severity}</span>
          </div>
          <div class="alert-meta">${a.location} &middot; ${Math.round((a.confidence||0)*100)}% confidence &middot; MSE ${(a.mse_score||0).toFixed(2)}× &middot; ${t}</div>
          <div class="advisory">
            <div class="advisory-row"><b>Root Cause</b><span>${adv.root_cause||"—"}</span></div>
            <div class="advisory-row"><b>Action</b><span>${adv.action||"—"}</span></div>
            <div class="advisory-row"><b>Urgency</b><span>${adv.urgency||"—"}</span></div>
            <div class="advisory-src">Advisory by ${adv.source||"rules"}</div>
          </div>
        </div>`;
    }).join("");
  }

  /* ---------------- HARDWARE ---------------- */
  function renderHardware() {
    // topology - nodes + link to cloud
    const ns = Object.values(state.nodes).sort((a, b) => a.machine_id.localeCompare(b.machine_id));
    const cloud = `
      <div class="topo-node" style="border-color:#38bdf8">
        <span class="topo-ico">💻</span>
        <div class="topo-info"><b>Cloud Command Centre (this laptop)</b>
          <span>FastAPI + SQLite + local LLM &middot; ${location.host}</span></div>
        <span class="pill OK">HOST</span>
      </div>`;
    const nodesHtml = ns.length ? ns.map((n) => {
      const bars = n.online ? "live" : "";
      return `
        <div class="topo-node">
          <span class="topo-ico">${icon(n.machine_type)}</span>
          <div class="topo-info"><b>${n.machine_id} — Arduino UNO Q</b>
            <span>MPU-6050 → STM32U585 → Wi-Fi → cloud</span></div>
          <span class="topo-link">
            <span class="signal-bars ${bars}">
              <i style="height:5px"></i><i style="height:8px"></i><i style="height:11px"></i><i style="height:14px"></i>
            </span>
            ${n.online ? "connected" : "offline"}
          </span>
        </div>`;
    }).join("") : `<div class="empty">No nodes connected yet.</div>`;
    $("topology").innerHTML = cloud + nodesHtml;
    $("boardSvg").innerHTML = boardSvg();
  }

  function boardSvg() {
    return `
      <svg viewBox="0 0 240 150" width="100%">
        <rect x="10" y="20" width="90" height="110" rx="8" fill="#0e7c86" stroke="#26304a"/>
        <text x="55" y="16" text-anchor="middle" fill="#8b97b0" font-size="9">MPU-6050</text>
        <rect x="140" y="20" width="90" height="110" rx="8" fill="#123a63" stroke="#26304a"/>
        <text x="185" y="16" text-anchor="middle" fill="#8b97b0" font-size="9">UNO Q</text>
        ${["VCC/3V3","GND","SCL/A5","SDA/A4","INT/D2"].map((lbl,i)=>{
          const y = 34 + i*20;
          const col = ["#ef4444","#5a6684","#f59e0b","#38bdf8","#a78bfa"][i];
          return `<line x1="100" y1="${y}" x2="140" y2="${y}" stroke="${col}" stroke-width="2.5"/>
                  <circle cx="100" cy="${y}" r="3" fill="${col}"/><circle cx="140" cy="${y}" r="3" fill="${col}"/>
                  <text x="120" y="${y-4}" text-anchor="middle" fill="#8b97b0" font-size="7">${lbl}</text>`;
        }).join("")}
      </svg>`;
  }

  /* ---------------- SYSTEM ---------------- */
  function renderSystem() {
    const steps = [
      { i: "📳", b: "MPU-6050", s: "1 kHz vibration" },
      { i: "🧠", b: "TinyML", s: "INT8 autoencoder" },
      { i: "📡", b: "Wi-Fi / LAN", s: "JSON health event" },
      { i: "💻", b: "Cloud", s: "FastAPI + SQLite" },
      { i: "🗣", b: "LLM", s: "plain-language advisory" },
      { i: "📊", b: "Dashboard", s: "this screen" },
    ];
    $("flow").innerHTML = steps.map((s, i) => `
      <div class="flow-step"><div class="fs-ico">${s.i}</div><b>${s.b}</b><span>${s.s}</span></div>
      ${i < steps.length - 1 ? '<span class="flow-arrow">→</span>' : ""}`).join("");
    $("sysLlm").textContent = state.llm.available ? "Local LLM (Ollama)" : "Rule-based expert";
    $("sysLlmModel").textContent = state.llm.available ? state.llm.model : "deterministic";
  }

  /* ---------------- view switching ---------------- */
  const TITLES = {
    overview: ["Fleet Overview", "Real-time machine health across the shop floor"],
    machines: ["Machine Inspector", "Live signature, waveform and anomaly history"],
    alerts: ["Alerts & AI Advisory", "LLM-generated maintenance guidance per fault"],
    hardware: ["Hardware Setup", "Sensor wiring, node topology and deployment"],
    system: ["System & Architecture", "Edge-to-cloud pipeline running fully offline"],
  };
  function switchView(v) {
    state.view = v;
    document.querySelectorAll(".nav-item").forEach((b) => b.classList.toggle("active", b.dataset.view === v));
    document.querySelectorAll(".view").forEach((el) => (el.hidden = el.id !== `view-${v}`));
    $("viewTitle").textContent = TITLES[v][0];
    $("viewSub").textContent = TITLES[v][1];
    if (v === "alerts") { $("navAlertBadge").hidden = true; }
    renderCurrentView();
  }
  function renderCurrentView() {
    if (state.view === "overview") renderOverview();
    else if (state.view === "machines") { renderMachineList(); if (state.selected) renderMachineDetail(state.selected); }
    else if (state.view === "alerts") renderAlerts();
    else if (state.view === "hardware") renderHardware();
    else if (state.view === "system") renderSystem();
  }

  /* ---------------- boot ---------------- */
  async function checkHealth() {
    try {
      const r = await fetch("/api/health");
      const d = await r.json();
      state.llm.available = d.llm_available;
      state.llm.model = d.llm_model;
      $("llmDot").className = "dot on";
      $("llmText").textContent = d.llm_available ? `LLM: ${d.llm_model}` : "LLM: rule-based";
    } catch (e) {
      $("llmDot").className = "dot off";
      $("llmText").textContent = "LLM: offline";
    }
  }

  function tickClock() {
    $("clock").textContent = new Date().toLocaleTimeString();
  }

  function init() {
    document.querySelectorAll(".nav-item").forEach((b) =>
      b.addEventListener("click", () => switchView(b.dataset.view))
    );
    setInterval(tickClock, 1000); tickClock();
    checkHealth(); setInterval(checkHealth, 15000);
    connect();
    switchView("overview");
    // periodic nodes refresh nudge over ws
    setInterval(() => { if (ws && ws.readyState === 1) ws.send("ping"); }, 5000);
  }

  document.addEventListener("DOMContentLoaded", init);
})();
