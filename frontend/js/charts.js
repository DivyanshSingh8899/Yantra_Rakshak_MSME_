/* ============================================================
   Lightweight canvas/SVG charts - zero dependencies, fully offline
   ============================================================ */
(function (global) {
  "use strict";

  const COLORS = {
    ok: "#22c55e", warn: "#f59e0b", crit: "#ef4444",
    accent: "#38bdf8", dim: "#5a6684", line: "#26304a",
  };

  function sevColor(sev) {
    return sev === "CRITICAL" ? COLORS.crit : sev === "WARNING" ? COLORS.warn : COLORS.ok;
  }

  /* Circular gauge (0..3 mse scale) rendered as SVG. */
  function gauge(mse, severity) {
    const v = Math.max(0, Math.min(3, mse));
    const pct = v / 3;
    const R = 38, C = 2 * Math.PI * R;
    const dash = (pct * C).toFixed(1);
    const col = sevColor(severity);
    return `
      <svg viewBox="0 0 92 92" class="gauge-svg">
        <circle cx="46" cy="46" r="${R}" fill="none" stroke="${COLORS.line}" stroke-width="8"/>
        <circle cx="46" cy="46" r="${R}" fill="none" stroke="${col}" stroke-width="8"
                stroke-linecap="round" stroke-dasharray="${dash} ${C}"
                transform="rotate(-90 46 46)"/>
        <text x="46" y="43" text-anchor="middle" fill="#e7ecf5" font-size="18" font-weight="700">${mse.toFixed(2)}</text>
        <text x="46" y="59" text-anchor="middle" fill="${COLORS.dim}" font-size="9">MSE ×base</text>
      </svg>`;
  }

  /* Inline sparkline for a series of numbers, coloured by severity. */
  function sparkline(values, severity, w, h) {
    w = w || 260; h = h || 40;
    if (!values || values.length < 2) {
      return `<svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" style="width:100%;height:${h}px"></svg>`;
    }
    const min = Math.min(...values), max = Math.max(...values);
    const rng = max - min || 1;
    const step = w / (values.length - 1);
    const pts = values.map((v, i) => {
      const x = i * step;
      const y = h - 4 - ((v - min) / rng) * (h - 8);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    });
    const col = sevColor(severity);
    const area = `0,${h} ${pts.join(" ")} ${w},${h}`;
    return `
      <svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" style="width:100%;height:${h}px">
        <polygon points="${area}" fill="${col}" opacity="0.12"/>
        <polyline points="${pts.join(" ")}" fill="none" stroke="${col}" stroke-width="2"
                  stroke-linejoin="round" stroke-linecap="round"/>
      </svg>`;
  }

  /* Full line chart on a <canvas>: history of mse scores with threshold bands. */
  function lineChart(canvas, series, opts) {
    opts = opts || {};
    const dpr = global.devicePixelRatio || 1;
    const cssW = canvas.clientWidth || 600, cssH = opts.height || 200;
    canvas.width = cssW * dpr; canvas.height = cssH * dpr;
    canvas.style.height = cssH + "px";
    const ctx = canvas.getContext("2d");
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, cssW, cssH);

    const padL = 38, padR = 12, padT = 12, padB = 22;
    const plotW = cssW - padL - padR, plotH = cssH - padT - padB;
    const maxY = Math.max(3, ...series) * 1.1;
    const yToPx = (y) => padT + plotH - (y / maxY) * plotH;

    // threshold bands
    const bands = [
      { y0: 0, y1: 1.5, c: "rgba(34,197,94,.06)" },
      { y0: 1.5, y1: 2.5, c: "rgba(245,158,11,.07)" },
      { y0: 2.5, y1: maxY, c: "rgba(239,68,68,.07)" },
    ];
    bands.forEach((b) => {
      ctx.fillStyle = b.c;
      const y = yToPx(b.y1), h = yToPx(b.y0) - yToPx(b.y1);
      ctx.fillRect(padL, y, plotW, h);
    });

    // grid + y labels
    ctx.strokeStyle = COLORS.line; ctx.fillStyle = COLORS.dim;
    ctx.font = "10px Segoe UI"; ctx.lineWidth = 1;
    [0, 1, 1.5, 2, 2.5, 3].forEach((v) => {
      const y = yToPx(v);
      ctx.beginPath(); ctx.moveTo(padL, y); ctx.lineTo(cssW - padR, y);
      ctx.globalAlpha = v === 1.5 || v === 2.5 ? 0.5 : 0.15; ctx.stroke(); ctx.globalAlpha = 1;
      ctx.fillText(v.toFixed(1), 6, y + 3);
    });

    if (series.length < 2) return;
    const step = plotW / (series.length - 1);

    // area + line
    ctx.beginPath();
    series.forEach((v, i) => {
      const x = padL + i * step, y = yToPx(v);
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    });
    ctx.strokeStyle = COLORS.accent; ctx.lineWidth = 2; ctx.stroke();
    ctx.lineTo(padL + (series.length - 1) * step, yToPx(0));
    ctx.lineTo(padL, yToPx(0)); ctx.closePath();
    ctx.fillStyle = "rgba(56,189,248,.10)"; ctx.fill();

    // last point marker
    const lx = padL + (series.length - 1) * step, ly = yToPx(series[series.length - 1]);
    ctx.beginPath(); ctx.arc(lx, ly, 3.5, 0, 2 * Math.PI);
    ctx.fillStyle = COLORS.accent; ctx.fill();
  }

  /* Vibration waveform on a <canvas>. */
  function waveform(canvas, samples, opts) {
    opts = opts || {};
    const dpr = global.devicePixelRatio || 1;
    const cssW = canvas.clientWidth || 600, cssH = opts.height || 160;
    canvas.width = cssW * dpr; canvas.height = cssH * dpr;
    canvas.style.height = cssH + "px";
    const ctx = canvas.getContext("2d");
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, cssW, cssH);
    if (!samples || !samples.length) return;

    const mid = cssH / 2;
    const amp = Math.max(...samples.map(Math.abs)) || 1;
    const scale = (cssH / 2 - 8) / amp;
    const step = cssW / (samples.length - 1);

    // midline
    ctx.strokeStyle = COLORS.line; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(0, mid); ctx.lineTo(cssW, mid); ctx.stroke();

    const col = opts.color || COLORS.accent;
    ctx.beginPath();
    samples.forEach((v, i) => {
      const x = i * step, y = mid - v * scale;
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    });
    ctx.strokeStyle = col; ctx.lineWidth = 1.6; ctx.lineJoin = "round"; ctx.stroke();
  }

  global.YRCharts = { gauge, sparkline, lineChart, waveform, sevColor, COLORS };
})(window);
