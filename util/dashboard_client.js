/**
 * Injected into grok_iran_forecast.html by parse_forecasts.py
 * Placeholders: __HORIZON_KEYS__, __HORIZON_LABELS__ (JSON arrays)
 */
(function () {
  const raw = document.getElementById("forecast-data");
  const DATA = JSON.parse(raw.textContent);
  const dates = DATA.dates;
  const narratives = DATA.narratives;
  const probLong = DATA.probLong;
  const subLong = DATA.subLong;
  const HORIZON_KEYS = __HORIZON_KEYS__;
  const HORIZON_LABELS = __HORIZON_LABELS__;

  function vegaEmbedSafe(el, spec) {
    vegaEmbed(el, spec, { actions: false, renderer: "svg" }).catch(console.error);
  }

  const axisConfig = {
    grid: true,
    gridColor: "#1f1f23",
    labelColor: "#a1a1aa",
    titleColor: "#a1a1aa",
    tickColor: "#3f3f46",
    domainColor: "#3f3f46",
  };

  const trajValues = probLong.map(function (row) {
    return Object.assign({}, row, { dateT: row.date });
  });

  const trajSpec = {
    $schema: "https://vega.github.io/schema/vega-lite/v5.json",
    background: null,
    config: {
      axis: axisConfig,
      view: { stroke: null },
      legend: {
        labelColor: "#e4e4e7",
        titleColor: "#e4e4e7",
        orient: "top",
        direction: "horizontal",
        symbolOpacity: 1,
      },
    },
    width: "container",
    height: 340,
    data: { values: trajValues },
    transform: [{ calculate: "datum.probability - datum.prevProbability", as: "delta" }],
    mark: { type: "line", strokeWidth: 1.75, interpolate: "monotone" },
    encoding: {
      x: {
        field: "dateT",
        type: "temporal",
        title: null,
        axis: {
          format: "%b",
          labelAngle: 0,
          tickCount: "month",
          grid: false,
        },
      },
      y: {
        field: "probability",
        type: "quantitative",
        scale: { domain: [0, 100] },
        title: "Normality probability (%)",
      },
      color: {
        field: "horizon",
        type: "nominal",
        title: null,
        scale: {
          domain: HORIZON_LABELS,
          range: ["#38bdf8", "#fb923c", "#f87171", "#2dd4bf", "#a3e635", "#facc15"],
        },
      },
      opacity: { value: 0.9 },
      tooltip: [
        { field: "date", type: "nominal", title: "Forecast date" },
        { field: "horizon", type: "nominal", title: "Horizon" },
        { field: "probability", type: "quantitative", title: "Normality %" },
        { field: "delta", type: "quantitative", title: "Change vs prior day" },
      ],
    },
  };
  vegaEmbedSafe("#chart-trajectory", trajSpec);

  function gateFamily(name) {
    const s = String(name || "").toLowerCase();
    if (s.indexOf("strike") >= 0) return "Strike pause";
    if (s.indexOf("insurance") >= 0) return "Insurance";
    if (s.indexOf("transit") >= 0) return "Commercial transit";
    return null;
  }

  function renderGateCharts() {
    const host = document.getElementById("chart-heatmap");
    host.innerHTML = "";

    const byDate = {};
    subLong.forEach(function (row) {
      if (row.horizonKey !== "6mo") return;
      const family = gateFamily(row.component);
      if (!family) return;
      if (!byDate[row.date]) byDate[row.date] = {};
      // Prefer denser labels when duplicates exist on a day.
      const prev = byDate[row.date][family];
      if (prev == null || String(row.component).length >= String(prev.src || "").length) {
        byDate[row.date][family] = { value: row.value, src: row.component };
      }
    });

    const levelRows = [];
    const gapRows = [];
    Object.keys(byDate)
      .sort()
      .forEach(function (d) {
        const strike = byDate[d]["Strike pause"];
        ["Strike pause", "Insurance", "Commercial transit"].forEach(function (family) {
          const cell = byDate[d][family];
          if (!cell) return;
          levelRows.push({
            date: d,
            dateT: d,
            gate: family,
            value: cell.value,
          });
          if (family !== "Strike pause" && strike) {
            gapRows.push({
              date: d,
              dateT: d,
              gate: family,
              gap: strike.value - cell.value,
            });
          }
        });
      });

    function panel(title, chartId) {
      const wrap = document.createElement("div");
      wrap.className = "border border-zinc-800 rounded-xl p-3 bg-zinc-950/60";
      const h = document.createElement("div");
      h.className = "text-xs font-mono text-zinc-300 mb-2 font-medium leading-snug";
      h.textContent = title;
      const chartDiv = document.createElement("div");
      chartDiv.id = chartId;
      chartDiv.className = "w-full min-h-[260px]";
      wrap.appendChild(h);
      wrap.appendChild(chartDiv);
      host.appendChild(wrap);
    }

    panel("6-month probability by gate", "gate-levels");
    panel("Points behind strike-pause (higher = more binding)", "gate-gaps");

    const gateColors = {
      domain: ["Strike pause", "Insurance", "Commercial transit"],
      range: ["#f87171", "#38bdf8", "#a3e635"],
    };

    vegaEmbedSafe("#gate-levels", {
      $schema: "https://vega.github.io/schema/vega-lite/v5.json",
      background: null,
      width: "container",
      height: 260,
      config: {
        axis: axisConfig,
        view: { stroke: null },
        legend: { labelColor: "#e4e4e7", title: null, orient: "top", direction: "horizontal" },
      },
      data: { values: levelRows },
      mark: { type: "line", strokeWidth: 2, interpolate: "monotone" },
      encoding: {
        x: {
          field: "dateT",
          type: "temporal",
          title: null,
          axis: { format: "%b", labelAngle: 0, tickCount: "month", grid: false },
        },
        y: {
          field: "value",
          type: "quantitative",
          title: "6-month P%",
          scale: { domain: [0, 100] },
        },
        color: { field: "gate", type: "nominal", scale: gateColors, title: null },
        tooltip: [
          { field: "date", type: "nominal", title: "Date" },
          { field: "gate", type: "nominal", title: "Gate" },
          { field: "value", type: "quantitative", title: "6-month %" },
        ],
      },
    });

    vegaEmbedSafe("#gate-gaps", {
      $schema: "https://vega.github.io/schema/vega-lite/v5.json",
      background: null,
      width: "container",
      height: 260,
      config: {
        axis: axisConfig,
        view: { stroke: null },
        legend: { labelColor: "#e4e4e7", title: null, orient: "top", direction: "horizontal" },
      },
      data: { values: gapRows },
      mark: { type: "area", line: true, opacity: 0.35, interpolate: "monotone" },
      encoding: {
        x: {
          field: "dateT",
          type: "temporal",
          title: null,
          axis: { format: "%b", labelAngle: 0, tickCount: "month", grid: false },
        },
        y: {
          field: "gap",
          type: "quantitative",
          title: "Gap vs strike-pause (pts)",
        },
        color: {
          field: "gate",
          type: "nominal",
          scale: { domain: ["Insurance", "Commercial transit"], range: ["#38bdf8", "#a3e635"] },
          title: null,
        },
        tooltip: [
          { field: "date", type: "nominal", title: "Date" },
          { field: "gate", type: "nominal", title: "Gate" },
          { field: "gap", type: "quantitative", title: "Pts behind strikes" },
        ],
      },
    });
  }

  renderGateCharts();

  const sixMoByDate = {};
  probLong.forEach(function (row) {
    if (row.horizon === "6 Months" && row.probability != null) {
      sixMoByDate[row.date] = row.probability;
    }
  });

  function oddsColor(p) {
    if (p == null || isNaN(p)) return "#27272a";
    const t = Math.max(0, Math.min(1, p / 100));
    // blue → teal → green
    const stops = [
      [13, 71, 161],
      [2, 136, 209],
      [0, 172, 193],
      [38, 166, 154],
      [67, 160, 71],
    ];
    const x = t * (stops.length - 1);
    const i = Math.floor(x);
    const f = x - i;
    const a = stops[i];
    const b = stops[Math.min(i + 1, stops.length - 1)];
    const r = Math.round(a[0] + (b[0] - a[0]) * f);
    const g = Math.round(a[1] + (b[1] - a[1]) * f);
    const bl = Math.round(a[2] + (b[2] - a[2]) * f);
    return "rgb(" + r + "," + g + "," + bl + ")";
  }

  function formatLongDate(iso) {
    const parts = iso.split("-").map(Number);
    const dt = new Date(Date.UTC(parts[0], parts[1] - 1, parts[2]));
    return dt.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      timeZone: "UTC",
    });
  }

  const sel = document.getElementById("date-select");
  const slider = document.getElementById("date-slider");
  const calendar = document.getElementById("date-calendar");
  const dateLabel = document.getElementById("date-label");
  const dateMeta = document.getElementById("date-meta");
  dates.forEach(function (d) {
    const opt = document.createElement("option");
    opt.value = d;
    opt.textContent = d;
    sel.appendChild(opt);
  });
  slider.min = "0";
  slider.max = String(Math.max(0, dates.length - 1));
  document.getElementById("date-range-start").textContent = formatLongDate(dates[0]);
  document.getElementById("date-range-end").textContent = formatLongDate(
    dates[dates.length - 1]
  );

  dates.forEach(function (d, idx) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.setAttribute("role", "option");
    btn.dataset.date = d;
    btn.dataset.index = String(idx);
    btn.title = d + " · 6-month " + (sixMoByDate[d] != null ? sixMoByDate[d] + "%" : "n/a");
    btn.style.background = oddsColor(sixMoByDate[d]);
    const month = d.slice(5, 7);
    const prevMonth = idx > 0 ? dates[idx - 1].slice(5, 7) : null;
    if (month !== prevMonth) {
      btn.classList.add("month-start");
      const names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
      btn.setAttribute("data-month", names[parseInt(month, 10) - 1]);
    }
    btn.addEventListener("click", function () {
      setSelectedDate(d, true);
    });
    calendar.appendChild(btn);
  });

  function setSelectedDate(dateStr, scrollDetail) {
    if (dates.indexOf(dateStr) < 0) return;
    sel.value = dateStr;
    slider.value = String(dates.indexOf(dateStr));
    dateLabel.textContent = formatLongDate(dateStr);
    const p6 = sixMoByDate[dateStr];
    const conflict =
      DATA.parsedByDate[dateStr] && DATA.parsedByDate[dateStr].conflict_day
        ? "Conflict day " + DATA.parsedByDate[dateStr].conflict_day
        : "Forecast run";
    dateMeta.textContent =
      conflict + (p6 != null ? " · 6-month " + p6 + "%" : "");
    Array.prototype.forEach.call(calendar.querySelectorAll("button"), function (btn) {
      btn.setAttribute("aria-selected", btn.dataset.date === dateStr ? "true" : "false");
    });
    renderDetail(dateStr);
    if (scrollDetail) {
      const pane = document.getElementById("detail");
      if (pane) pane.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }

  slider.addEventListener("input", function () {
    const idx = parseInt(slider.value, 10);
    if (!isNaN(idx) && dates[idx]) setSelectedDate(dates[idx], false);
  });
  document.getElementById("date-prev").addEventListener("click", function () {
    const idx = dates.indexOf(sel.value);
    if (idx > 0) setSelectedDate(dates[idx - 1], false);
  });
  document.getElementById("date-next").addEventListener("click", function () {
    const idx = dates.indexOf(sel.value);
    if (idx >= 0 && idx < dates.length - 1) setSelectedDate(dates[idx + 1], false);
  });

  const latestDate = dates[dates.length - 1];
  sel.value = latestDate;

  function impactClass(impact) {
    const t = (impact || "").toLowerCase();
    if (t.includes("toward") && !t.includes("against")) return "evidence-mild";
    if (t.includes("against")) return "evidence-negative";
    if (t.includes("mildly")) return "evidence-mild";
    return "evidence-negative";
  }

  function renderDetail(dateStr) {
    const p = DATA.parsedByDate[dateStr];
    const n = narratives[dateStr];
    if (!p || !n) return;
    const hd = n.horizon_details || {};
    const scrub = function (s) {
      return String(s || "")
        .replace(/<grok:render[\s\S]*?<\/grok:render>/gi, "")
        .replace(/<grok:render[^>]*\/>/gi, "")
        .replace(/\s+$/gm, "")
        .trim();
    };
    const esc = function (s) {
      const d = document.createElement("div");
      d.textContent = scrub(s);
      return d.innerHTML;
    };

    let evRows = "";
    (p.evidence || []).forEach(function (ev) {
      evRows +=
        '<tr class="border-b border-zinc-800">' +
        '<td class="py-3 pr-4 font-medium text-sm">' +
        esc(ev.evidence_item) +
        "</td>" +
        '<td class="py-3 px-2 text-xs text-zinc-400">' +
        esc(ev.source_type) +
        "</td>" +
        '<td class="py-3 px-2"><span class="' +
        impactClass(ev.impact) +
        ' px-2 py-0.5 rounded-full text-xs">' +
        esc(ev.impact) +
        "</span></td>" +
        '<td class="py-3 px-2 text-xs">' +
        esc(ev.confidence) +
        "</td>" +
        '<td class="py-3 pl-2 text-xs text-emerald-300">' +
        esc(ev.status) +
        "</td></tr>";
    });

    let toward = "";
    (p.drivers_toward || []).forEach(function (t, i) {
      toward +=
        '<div class="flex gap-3"><span class="text-teal-400 font-mono">0' +
        (i + 1) +
        '</span><div>' +
        esc(t) +
        "</div></div>";
    });
    let against = "";
    (p.drivers_against || []).forEach(function (t, i) {
      against +=
        '<div class="flex gap-3"><span class="text-amber-400 font-mono">0' +
        (i + 1) +
        '</span><div>' +
        esc(t) +
        "</div></div>";
    });

    let cards = "";
    HORIZON_LABELS.forEach(function (label) {
      const d = hd[label] || {};
      cards +=
        '<div class="bg-zinc-900 border border-zinc-700 rounded-2xl p-4 flex flex-col">' +
        '<div class="text-[10px] font-mono text-zinc-500">' +
        esc(label) +
        "</div>" +
        '<div class="text-5xl font-light heading-font text-cyan-300 mt-2">' +
        esc(d.probability || "") +
        '%</div><div class="mt-4 space-y-1 text-xs text-zinc-400">' +
        '<div><span class="text-zinc-500">Base:</span> ' +
        esc(d.base_rate_anchor || "") +
        "</div>" +
        '<div><span class="text-zinc-500">Adj:</span> ' +
        esc(d.current_evidence_adjustment || "") +
        "</div>" +
        '<div class="text-zinc-200 font-medium mt-2">' +
        esc(d.main_gating_factor || "") +
        "</div>" +
        '<div class="pt-2 border-t border-zinc-800 mt-2">Conf: ' +
        esc(d.confidence || "") +
        "</div></div></div>";
    });

    let subTable = "";
    (p.sub_forecasts || []).forEach(function (sf) {
      subTable += '<tr class="border-b border-zinc-800 text-center">';
      subTable +=
        '<td class="py-2 text-left text-sm">' + esc(sf.component) + "</td>";
      HORIZON_KEYS.forEach(function (k) {
        const v = sf[k];
        subTable +=
          '<td class="py-2 text-sm">' +
          (v === "" || v === undefined ? "—" : esc(String(v))) +
          "</td>";
      });
      subTable += "</tr>";
    });

    let sumRows = "";
    (n.summary_table || []).forEach(function (r) {
      sumRows +=
        '<tr class="border-b border-zinc-800">' +
        '<td class="p-2">' +
        esc(r.horizon) +
        "</td>" +
        '<td class="p-2 font-mono">' +
        esc(r.probability) +
        "</td>" +
        '<td class="p-2 text-zinc-400">' +
        esc(r.gating || "") +
        "</td>" +
        '<td class="p-2 text-zinc-400">' +
        esc(r.upside || "") +
        "</td>" +
        '<td class="p-2 text-zinc-400">' +
        esc(r.downside || "") +
        "</td></tr>";
    });

    const snapHtml = marked.parse(scrub(n.snapshot || ""));
    const opHtml = marked.parse(scrub(n.operational_definition || ""));
    const sigHtml = marked.parse(scrub(n.critical_signals || ""));

    document.getElementById("detail-pane").innerHTML =
      '<div class="grid grid-cols-1 lg:grid-cols-2 gap-6">' +
      '<div class="bg-zinc-900/80 border border-zinc-700 rounded-2xl p-5">' +
      '<div class="text-xs font-mono text-amber-300 mb-2">Operational definition</div>' +
      '<div class="prose-snapshot prose prose-invert prose-sm max-w-none text-zinc-300">' +
      opHtml +
      "</div></div>" +
      '<div class="bg-zinc-900/80 border border-amber-900/30 rounded-2xl p-5">' +
      '<div class="text-xs font-mono text-amber-300 mb-2">Current situation snapshot</div>' +
      '<div class="prose-snapshot prose prose-invert prose-sm max-w-none text-zinc-200">' +
      snapHtml +
      "</div>" +
      '<div class="mt-3 text-xs text-zinc-500">Conflict day: <span class="text-amber-200 font-mono">' +
      esc(p.conflict_day || "") +
      "</span></div></div></div>" +
      '<div><div class="text-xs font-mono text-zinc-500 mb-2">Evidence ledger</div>' +
      '<div class="overflow-x-auto border border-zinc-800 rounded-xl">' +
      '<table class="w-full text-sm min-w-[640px]">' +
      '<thead><tr class="text-left text-xs font-mono text-zinc-500 border-b border-zinc-800">' +
      "<th class=\"p-3\">Item</th><th class=\"p-3\">Source</th><th class=\"p-3\">Impact</th><th class=\"p-3\">Conf.</th><th class=\"p-3\">Status</th>" +
      "</tr></thead><tbody>" +
      evRows +
      "</tbody></table></div></div>" +
      '<div class="grid grid-cols-1 md:grid-cols-2 gap-6">' +
      '<div class="bg-zinc-900 border border-teal-800 rounded-2xl p-5 space-y-4">' +
      '<div class="text-xs font-mono text-teal-300">Toward normalization</div>' +
      toward +
      "</div>" +
      '<div class="bg-zinc-900 border border-amber-800 rounded-2xl p-5 space-y-4">' +
      '<div class="text-xs font-mono text-amber-300">Against normalization</div>' +
      against +
      "</div></div>" +
      '<div><div class="text-xs font-mono text-zinc-500 mb-2">Decomposed sub-forecasts</div>' +
      '<div class="overflow-x-auto border border-zinc-800 rounded-xl">' +
      '<table class="w-full text-xs min-w-[720px]">' +
      '<thead><tr class="border-b border-zinc-800 text-zinc-500 font-mono">' +
      '<th class="text-left p-2">Component</th>' +
      '<th class="p-2">1wk</th><th class="p-2">1mo</th><th class="p-2">3mo</th>' +
      '<th class="p-2">6mo</th><th class="p-2">1yr</th><th class="p-2">18mo</th>' +
      "</tr></thead><tbody>" +
      subTable +
      "</tbody></table></div></div>" +
      '<div><div class="text-xs font-mono text-cyan-400 mb-2">Final probabilities by horizon</div>' +
      '<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-3">' +
      cards +
      "</div></div>" +
      '<div class="grid grid-cols-1 md:grid-cols-2 gap-6">' +
      '<div class="bg-teal-950/30 border border-teal-800 rounded-2xl p-5">' +
      '<div class="text-xs font-mono text-teal-300 mb-2">Faster normalization (~' +
      esc(n.scenario_faster_weight || "?") +
      "%)</div>" +
      '<p class="text-sm text-zinc-300 whitespace-pre-wrap">' +
      esc(n.faster_case || p.scenario_faster_body || "") +
      "</p></div>" +
      '<div class="bg-amber-950/30 border border-amber-800 rounded-2xl p-5">' +
      '<div class="text-xs font-mono text-amber-300 mb-2">Prolonged instability (~' +
      esc(n.scenario_prolonged_weight || "?") +
      "%)</div>" +
      '<p class="text-sm text-zinc-300 whitespace-pre-wrap">' +
      esc(n.prolonged_case || p.scenario_prolonged_body || "") +
      "</p></div></div>" +
      '<div class="bg-black/50 border border-red-900/40 rounded-2xl p-5">' +
      '<div class="text-xs font-mono text-red-400 mb-2">Red-team critique</div>' +
      '<p class="text-sm text-zinc-300 whitespace-pre-wrap">' +
      esc(n.red_team || "") +
      "</p></div>" +
      '<div><div class="text-xs font-mono text-zinc-500 mb-2">Critical signals to monitor</div>' +
      '<div class="prose prose-invert prose-sm max-w-none text-zinc-300">' +
      sigHtml +
      "</div></div>" +
      '<div><div class="text-xs font-mono text-zinc-500 mb-2">Final summary table</div>' +
      '<div class="overflow-x-auto border border-zinc-800 rounded-xl">' +
      '<table class="w-full text-sm">' +
      '<thead><tr class="text-left text-xs text-zinc-500 border-b border-zinc-800">' +
      "<th class=\"p-2\">Horizon</th><th class=\"p-2\">P</th><th class=\"p-2\">Gating</th><th class=\"p-2\">Upside</th><th class=\"p-2\">Downside</th>" +
      "</tr></thead><tbody>" +
      sumRows +
      "</tbody></table></div></div>" +
      '<div class="bg-zinc-900/50 border border-zinc-700 rounded-2xl p-5">' +
      '<div class="text-xs font-mono text-teal-300 mb-2">Most likely path</div>' +
      '<p class="text-zinc-200">' +
      esc(n.most_likely_path || "") +
      "</p></div>";
  }

  setSelectedDate(latestDate, false);

  const tbody = document.getElementById("delta-table-body");
  HORIZON_LABELS.forEach(function (label, idx) {
    const series = dates.map(function (d) {
      const row = probLong.find(function (x) {
        return x.date === d && x.horizon === label;
      });
      return row ? row.probability : null;
    });
    let first = null;
    for (let i = 0; i < series.length; i++) {
      if (series[i] != null) {
        first = series[i];
        break;
      }
    }
    let last = null;
    for (let i = series.length - 1; i >= 0; i--) {
      if (series[i] != null) {
        last = series[i];
        break;
      }
    }
    const delta = first != null && last != null ? last - first : null;
    const tr = document.createElement("tr");
    tr.innerHTML =
      '<td class="p-3 font-medium">' +
      label +
      "</td>" +
      '<td class="p-3 text-center font-mono">' +
      (first != null ? first : "—") +
      "</td>" +
      '<td class="p-3 text-center font-mono">' +
      (last != null ? last : "—") +
      "</td>" +
      '<td class="p-3 text-center font-mono">' +
      (delta != null ? (delta > 0 ? "+" : "") + delta : "—") +
      "</td>" +
      '<td class="p-3"><div id="spark-' +
      idx +
      '" class="h-10 w-44"></div></td>';
    tbody.appendChild(tr);

    const sparkData = [];
    dates.forEach(function (d, i) {
      if (series[i] != null) sparkData.push({ date: d, dateT: d, v: series[i] });
    });
    const sparkSpec = {
      $schema: "https://vega.github.io/schema/vega-lite/v5.json",
      background: null,
      width: 160,
      height: 40,
      padding: 0,
      data: { values: sparkData },
      mark: { type: "line", strokeWidth: 1.5, interpolate: "monotone" },
      encoding: {
        x: {
          field: "dateT",
          type: "temporal",
          axis: null,
          title: null,
        },
        y: {
          field: "v",
          type: "quantitative",
          axis: null,
          title: null,
          scale: { domain: [0, 100] },
        },
        color: { value: "#67e8f9" },
      },
    };
    vegaEmbedSafe("#spark-" + idx, sparkSpec);
  });

  const qel = document.getElementById("qualitative-body");
  const qmd = document.getElementById("qualitative-md");
  if (qel && qmd) {
    qel.innerHTML = marked.parse(qmd.textContent);
    const table = qel.querySelector("table");
    if (table) {
      const wrap = document.createElement("div");
      wrap.className =
        "overflow-x-auto border border-zinc-800 rounded-xl mb-6 bg-zinc-950/60";
      table.parentNode.insertBefore(wrap, table);
      wrap.appendChild(table);
    }
  }

  document.getElementById("copy-prompt-btn").addEventListener("click", function () {
    const t = document.getElementById("source-prompt-text").innerText;
    navigator.clipboard.writeText(t).then(function () {
      alert("Copied source prompt");
    });
  });
})();
