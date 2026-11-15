# Grok Iran forecast — visualization & analysis prompts

This file supports **two workflows**:

1. **Automated dashboard (recommended):** Run `python3 util/parse_forecasts.py` from the project root. It reads `forecasts/grok_iran_forecast-*.md`, writes `analysis/structured/*.csv`, `narratives.json`, and **`analysis/structured/forecast_evolution.md`** (aggregate first→latest deltas + scenario weights), then regenerates **`analysis/grok_iran_forecast.html`** (self-contained, Tailwind + Vega-Lite + marked.js via CDN). The evolution markdown is embedded in the “Forecast evolution analysis” section.

2. **Optional extra narrative:** The dashboard already embeds auto-generated **Forecast evolution analysis** from `forecast_evolution.md` on each parser run. Use **Part 1** below only if you want a separate, deeper write-up for humans (e.g. a memo); it is not required for the HTML. **Part 2** is for regenerating the entire HTML without the Python script (advanced).

**Day-to-day operations** (new forecast file → parse → optional memo → gist → validate) are spelled out in **Ongoing workflow** near the end of this file.

---

## Inputs the LLM should receive (Part 1)

Attach or paste these files from the repo after running the parser:

| File | Contents |
|------|----------|
| `analysis/structured/probabilities.csv` | One row per date × horizon: probability, base rate, confidence, gating, triggers |
| `analysis/structured/sub_forecasts.csv` | Decomposed components × horizon percentages |
| `analysis/structured/evidence_ledger.csv` | Evidence items over time |
| `analysis/structured/scenarios.csv` | Faster vs prolonged scenario weights by date |
| `analysis/structured/drivers.csv` | Ranked drivers toward / against normalization |
| `analysis/structured/narratives.json` | Optional: snapshots of narrative fields (if the model reads JSON) |
| `analysis/structured/forecast_evolution.md` | Auto-generated each run (headline deltas, cross-run notes, scenario weights) and embedded in the dashboard |

The **daily source markdown** lives in `forecasts/grok_iran_forecast-YYYYMMDD.md` (same structure as `prompts/grok_iran_forecast.md`).

---

## Part 1 — Qualitative trend analysis (for Grok / LLM)

You are a geopolitical risk analyst. You are given **structured CSV exports** (and optionally narrative JSON) covering **multiple forecast dates** for the same question: probability that the Persian Gulf returns to **functional normality** after the 2026 Iran War, across horizons 1 week … 18 months.

**Task:** Write a concise **decision-grade qualitative synthesis** of how the forecast **evolves over time**. Do not restate raw tables row-by-row. Focus on interpretation.

**Address explicitly:**

1. **Overall trajectory** — Are headline probabilities trending up, down, or flat? Any **inflection dates**?
2. **Horizon divergence** — Which horizons moved together vs diverged (e.g., short vs long dated)?
3. **Evidence ledger dynamics** — What themes **entered, exited, or flipped** (impact direction / confidence)? What does that imply for calibration?
4. **Drivers** — How did top “toward” vs “against” drivers **shift in emphasis or ordering**?
5. **Scenario weights** — How did faster normalization vs prolonged instability weights change, and what narrative does that tell?
6. **Sub-forecasts** — Which **gating components** (strikes, transit, insurance, exports, proxy) are binding the aggregate forecast at the **latest** date vs earlier dates?
7. **Analytical integrity** — Where might the **latest** forecast still be too optimistic or too pessimistic relative to the evidence path?

**Output format:** Markdown only, with clear `##` / `###` headings, bullet lists where helpful, and a short **bottom-line** paragraph at the end. No HTML unless the user asks for it.

**Length:** Roughly 800–1500 words unless the user specifies otherwise.

Use this output as a standalone memo or brief; the live dashboard does not depend on it.

---

## Part 2 — Optional full HTML regeneration (multi-day dashboard)

Use only if you are **not** using the Python builder and want a model to emit the **entire** page. The canonical layout is already implemented by `util/parse_forecasts.py` + `util/dashboard_client.js`; prefer re-running the script.

If you must regenerate manually, output **one** valid HTML file and nothing else. Requirements:

### Technical

- Single file, opens from disk (`file://`) with **no** fetches to local CSV paths. Embed data as JSON in a `<script type="application/json" id="forecast-data">` block (same schema the dashboard expects: `dates`, `narratives`, `parsedByDate`, `probLong`, `subLong`).
- **Tailwind CSS**, **Vega-Lite**, **Vega**, **Vega-Embed**, **marked** — all via **CDN** only.
- Dark mode, mobile-responsive, print-friendly CSS.
- Charts: (1) multi-line **trajectory** of final probabilities by horizon over dates; (2) one **heatmap per sub-forecast component** (timeframe × forecast date); (3) small **sparklines** for first-vs-latest deltas.

### Content / UX

- **Header:** title, date range, run count, conflict day (latest).
- **Trajectory + heatmap** as above.
- **Date selector** driving a detail pane: operational definition, snapshot, evidence table, drivers, sub-forecast table, horizon cards, scenarios, red-team, signals, summary table, most likely path — all for the **selected** date.
- **Delta table:** first vs latest probability per horizon + sparkline.
- **Forecast evolution analysis:** auto-generated markdown embedded at build time (rendered with marked).
- **Source prompt:** collapsible `<details>` with the **full** text of `prompts/grok_iran_forecast.md` (or state that it is embedded at build time).

### Design principles (carry forward from single-day briefings)

- Preserve analytical structure: definition, evidence, drivers, decomposition, scenarios, red-team, signals — not a flattened infographic.
- Serious briefing aesthetic: hierarchy, restrained color, semantic encoding (normalization-positive vs instability vs neutral).
- No autoplay animation, parallax, or chartjunk.

**Final instruction for the model:** Output only the HTML file. No markdown fences, no commentary.

---

## Ongoing workflow (repeat each time you add or change forecasts)

Use this checklist so the **local dashboard**, **structured exports**, and **public gist** stay in sync.

### 1. Add or edit the daily source file

- Path pattern: `forecasts/grok_iran_forecast-YYYYMMDD.md` (e.g. `grok_iran_forecast-20260328.md`).
- Structure matches the canonical prompt in `prompts/grok_iran_forecast.md` (sections, tables, narrative fields).
- Optional: to create empty stub files for a date range (e.g. before filling them in), run `util/gen_daily_output_file.sh` — see that script’s header for usage.

### 2. Regenerate the dashboard and structured data

From the **project root**:

```bash
python3 util/parse_forecasts.py
```

This step:

- Reads every `forecasts/grok_iran_forecast-*.md`.
- Writes `analysis/structured/*.csv`, `narratives.json`, and **`analysis/structured/forecast_evolution.md`** (cross-run deltas and notes).
- Rebuilds **`analysis/grok_iran_forecast.html`** (single self-contained file: embedded JSON, Tailwind + Vega-Lite + marked via CDN; client logic is compiled from `util/dashboard_client.js` at build time).

Always run the parser after changing any forecast markdown so the HTML and CSVs match.

### 3. Quick local check (recommended)

- Open `analysis/grok_iran_forecast.html` in a browser, or serve the `analysis/` folder and load the page (e.g. `python3 -m http.server` from `analysis/`).
- Confirm charts render, the date selector switches runs, and “Forecast evolution analysis” reflects the latest `forecast_evolution.md` content.

### 4. Optional — Part 1 qualitative memo

- Not required for the dashboard. If you want a separate decision memo, follow **Part 1** below and attach the files listed under **Inputs the LLM should receive (Part 1)**.

### 5. Publish the live HTML gist

The public preview is backed by a GitHub gist; updating it replaces the file **`grok_iran_forecast.html`** on gist **`c597082b35f0c457274c80daadfa5ff0`**. If you also publish a qualitative memo on the same gist, name it so it sorts **after** `grok_iran_forecast.html` in the gist file list (e.g. **`memo_persian_gulf_qualitative.md`**). Otherwise [gistpreview](https://gistpreview.github.io/)’s default URL (`?gist_id` only) picks the **first** file alphabetically and will `document.write` the wrong file (see `main.js` on gistpreview: first key in `info.files` wins when the path segment is empty).

**Prerequisites**

- [GitHub CLI](https://cli.github.com/) (`gh`) installed.
- Authentication: `gh auth login`, **or** `GH_TOKEN` / `GITHUB_TOKEN` set to a token with **gist** scope for the account that owns the gist.

**Command** (from anywhere; the script resolves the repo root):

```bash
./util/publish_gist.sh
```

Equivalent manual command if you prefer not to use the script:

```bash
gh gist edit c597082b35f0c457274c80daadfa5ff0 \
  --filename grok_iran_forecast.html \
  analysis/grok_iran_forecast.html
```

(Run from project root so `analysis/grok_iran_forecast.html` resolves correctly.)

### 6. Validate the public preview

- Open **[Gist HTML Preview (explicit HTML file)](https://gistpreview.github.io/?c597082b35f0c457274c80daadfa5ff0/grok_iran_forecast.html)** — always include **`/grok_iran_forecast.html`** when the gist has more than one file, or confirm the default `?gist_id` still resolves to the dashboard (HTML must be first in lexicographic order among gist files). Confirm the document title, navigation, and main sections.

**How gistpreview works (and when it “breaks”):** The tool’s [`main.js`](https://gistpreview.github.io/main.js) fetches the gist via the GitHub API and injects the chosen file with **`document.write(content)`** — it does not host your page on `gist.githubusercontent.com`. In **normal desktop Chrome/Firefox**, that usually replaces the preview tab so your CDN scripts (Tailwind, Vega, etc.) run. A few more gotchas:

- **`Uncaught SyntaxError: Unexpected token 'export'`** — Gistpreview’s shell still loads [`fetch.js` from `github/fetch` master](https://cdn.jsdelivr.net/gh/github/fetch@master/fetch.js) as a **classic** `<script>`. Upstream **switched that file to ES modules** (`export function Headers` around line 86, etc.), so the browser throws on parse. **Modern browsers already have `fetch`**, so `main.js` usually still runs afterward; the error is **gistpreview’s bug/outdated polyfill**, not your dashboard HTML. Ignore it, or use **raw gist** / **htmlpreview** / **local `http.server`** to avoid their shell entirely.

- **`apple-mobile-web-app-capable` is deprecated** — That `<meta>` comes from **gistpreview’s** [`index.html`](https://github.com/gistpreview/gistpreview.github.io/blob/master/index.html), not from `grok_iran_forecast.html`. Harmless noise until gistpreview updates their template.

1. **Chrome `document.write` + cross-origin scripts** — Chrome may log *parser-blocking, cross site … invoked via document.write* and throttle or block those script loads on some connections (see [Chrome Lighthouse: avoid document.write](https://developer.chrome.com/docs/lighthouse/best-practices/no-document-write)). If charts never appear, try another browser or open the raw file (below).

2. **Embedded / IDE browsers** — Some environments load the preview in a **sandboxed** context and report *Blocked script execution … allow-scripts is not set* for the gist raw URL. That is not gistpreview’s static `index.html` (which has no sandbox iframe); validate in a **regular browser tab** or use the alternatives below.

**Alternatives if gistpreview is flaky:**

- **Raw gist in a normal tab:** `https://gist.githubusercontent.com/<user>/<gist_id>/raw/grok_iran_forecast.html` — full dashboard, no `document.write` wrapper.
- **[htmlpreview.github.io](https://htmlpreview.github.io/)** — prepend to the raw URL, e.g. `https://htmlpreview.github.io/?https://gist.githubusercontent.com/tripp-smith/c597082b35f0c457274c80daadfa5ff0/raw/grok_iran_forecast.html`. **Caveat:** htmlpreview rewrites and re-injects remote scripts through its own loader; this dashboard’s **CDN `<script src>` chain (Tailwind, Vega, Vega-Lite, Vega-Embed)** often does **not** execute correctly there (`vegaEmbed is not defined`, script `appendChild` errors in console). Prefer **raw gist** or **GitHub Pages** for a **fully working** chart UI; htmlpreview is still fine for static HTML smoke checks.
- **Local:** `python3 -m http.server` from repo root and open `http://127.0.0.1:8000/analysis/grok_iran_forecast.html` (see §3).
- **Long-term:** publish the same HTML to **GitHub Pages** or another static host so you are not dependent on `document.write` preview tools.

---

## Where the code lives

| Piece | Location |
|-------|----------|
| Parser + HTML build | `util/parse_forecasts.py` |
| Dashboard behavior (charts, date selector, rendering) | `util/dashboard_client.js` (inlined into the HTML on build) |
| Gist publish | `util/publish_gist.sh` |
| Canonical forecast prompt (embedded in HTML at build) | `prompts/grok_iran_forecast.md` |
