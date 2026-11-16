#!/usr/bin/env python3
"""
Parse forecasts/grok_iran_forecast-YYYYMMDD.md files into structured CSV/JSON
and generate analysis/grok_iran_forecast.html (self-contained dashboard).
"""
from __future__ import annotations

import csv
import json
import re
import sys
import math
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
FORECASTS_DIR = ROOT / "forecasts"
STRUCTURED_DIR = ROOT / "analysis" / "structured"
HTML_OUT = ROOT / "analysis" / "grok_iran_forecast.html"
SOURCE_PROMPT_PATH = ROOT / "prompts" / "grok_iran_forecast.md"

HORIZON_LABELS = ["1 Week", "1 Month", "3 Months", "6 Months", "1 Year", "18 Months"]
HORIZON_KEYS = ["1wk", "1mo", "3mo", "6mo", "1yr", "18mo"]
HORIZON_KEY_FOR_LABEL = dict(zip(HORIZON_LABELS, HORIZON_KEYS))

# Accept 1w/1wk/1 week, 1m/1mo/1 month, optional ≈/~, <5%, and 5–10% ranges.
_SUB_PCT = r"[~≈]?\s*<?\s*(\d+)(?:\s*[-–]\s*\d+)?\s*%"
SUB_PCT_RE = re.compile(
    rf"1\s*w(?:k|eek)?\s*{_SUB_PCT}\s*[,;]?\s*"
    rf"1\s*m(?:o(?:nth)?)?\s*{_SUB_PCT}\s*[,;]?\s*"
    rf"3\s*m(?:o(?:nth)?s?)?\s*{_SUB_PCT}\s*[,;]?\s*"
    rf"6\s*m(?:o(?:nth)?s?)?\s*{_SUB_PCT}\s*[,;]?\s*"
    rf"1\s*y(?:r|ear)?\s*{_SUB_PCT}\s*[,;]?\s*"
    rf"18\s*m(?:o(?:nth)?s?)?\s*{_SUB_PCT}",
    re.IGNORECASE,
)

# Canonical section titles used after heading normalization.
_SECTION_CANON = [
    "Forecast Question",
    "Operational Definition of “Return to Functional Normality”",
    "Operational Definition of \"Return to Functional Normality\"",
    "Current Situation Snapshot",
    "Reference Classes and Base-Rate Prior",
    "Evidence Ledger",
    "Key Drivers Toward Normalization",
    "Key Drivers Against Normalization",
    "Decomposed Sub-Forecasts",
    "Final Probability Forecasts by Horizon",
    "Most Likely Path",
    "Faster Normalization Case",
    "Prolonged Instability Case",
    "Red-Team Critique",
    "Critical Signals to Monitor",
    "Final Summary Table",
]

# Alias headings seen in the wild -> canonical title.
_SECTION_ALIASES = [
    (
        re.compile(
            r"^(?:Step\s*\d+[.:]\s*)?Final(?:\s+Calibrated)?(?:\s+Probability)?\s+Forecasts?(?:\s+by\s+Horizon)?\b.*",
            re.I,
        ),
        "Final Probability Forecasts by Horizon",
    ),
    (re.compile(r"^Decomposed Sub-Forecasts\b.*", re.I), "Decomposed Sub-Forecasts"),
    (re.compile(r"^Evidence Ledger\b.*", re.I), "Evidence Ledger"),
    (re.compile(r"^Current Situation Snapshot\b.*", re.I), "Current Situation Snapshot"),
    (re.compile(r"^Operational Definition\b.*", re.I), "Operational Definition of “Return to Functional Normality”"),
    (re.compile(r"^Key Drivers Toward Normalization\b.*", re.I), "Key Drivers Toward Normalization"),
    (re.compile(r"^Key Drivers Against Normalization\b.*", re.I), "Key Drivers Against Normalization"),
    (re.compile(r"^Most Likely Path\b.*", re.I), "Most Likely Path"),
    (re.compile(r"^Faster Normalization Case\b.*", re.I), "Faster Normalization Case"),
    (re.compile(r"^Prolonged Instability Case\b.*", re.I), "Prolonged Instability Case"),
    (re.compile(r"^(?:Step\s*\d+[.:]\s*)?Red-?Team(?:\s+Critique)?\b.*", re.I), "Red-Team Critique"),
    (re.compile(r"^Critical Signals to Monitor\b.*", re.I), "Critical Signals to Monitor"),
    (re.compile(r"^(?:Step\s*\d+[.:]\s*)?Final Summary Table\b.*", re.I), "Final Summary Table"),
]


def normalize_forecast_text(text: str) -> str:
    """Normalize drifted Grok headings so existing extractors can match.

    Handles numbered bold headings (`**9. Final ...**`), bullet horizons
    (`**• 1 Week**`), and markdown `###` section headers used on some days.
    """

    def canon_inner(inner: str) -> str:
        s = inner.strip().rstrip(":")
        s = re.sub(r"^[•\-\*]\s*", "", s)
        s = re.sub(r"^(?:Step\s*)?\d+[.:]\s*", "", s, flags=re.IGNORECASE)
        s = s.strip().rstrip(":")
        for pat, title in _SECTION_ALIASES:
            if pat.match(s):
                return title
        # Match known section prefixes; drop trailing notes in the heading.
        for title in _SECTION_CANON:
            if s == title or s.startswith(title):
                return title
        for label in HORIZON_LABELS:
            if s.lower() == label.lower() or s.lower().startswith(label.lower() + " "):
                return label
        return s

    # Convert ### Section ... lines into bold canonical headings.
    def hash_repl(m: re.Match[str]) -> str:
        inner = canon_inner(m.group(1))
        return f"**{inner}**"

    text = re.sub(r"^#{2,4}\s+(.+)$", hash_repl, text, flags=re.MULTILINE)

    def bold_repl(m: re.Match[str]) -> str:
        return f"**{canon_inner(m.group(1))}**"

    text = re.sub(r"\*\*([^*]+)\*\*", bold_repl, text)
    return text


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def extract_between(text: str, start: str, end_markers: list[str]) -> str:
    """Take content after `start` line until a line starting with any end marker."""
    if start not in text:
        return ""
    idx = text.index(start)
    rest = text[idx + len(start) :]
    # skip optional trailing ** on same pattern
    lines = rest.splitlines()
    # If start was '**Foo**' we already consumed it; find first line
    out: list[str] = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("**") and any(
            stripped.startswith(f"**{m}") or stripped == f"**{m}**"
            for m in end_markers
        ):
            break
        if stripped.startswith("**") and stripped.endswith("**"):
            inner = stripped.strip("*")
            if inner in end_markers:
                break
        out.append(line)
    return "\n".join(out).strip()


def parse_operational_definition(text: str) -> str:
    s = extract_between(
        text,
        "**Operational Definition",
        [
            "Current Situation Snapshot",
        ],
    )
    # remove leading title line if duplicated
    s = re.sub(r"^[^\n]*\n", "", s, count=1) if s else s
    return s.strip()


def parse_snapshot(text: str) -> str:
    return extract_between(
        text,
        "**Current Situation Snapshot**",
        ["Reference Classes", "Evidence Ledger"],
    ).strip()


def parse_evidence_table(text: str) -> list[dict[str, str]]:
    if "**Evidence Ledger**" not in text:
        return []
    block = extract_between(
        text,
        "**Evidence Ledger**",
        ["Key Drivers Toward", "Key Drivers"],
    )
    rows: list[dict[str, str]] = []
    for line in block.splitlines():
        line = line.strip()
        if not line.startswith("|") or line.startswith("|---"):
            continue
        parts = [p.strip() for p in line.split("|")]
        parts = [p for p in parts if p]
        if len(parts) < 5:
            continue
        if parts[0].lower() == "evidence item":
            continue
        rows.append(
            {
                "evidence_item": parts[0],
                "source_type": parts[1],
                "impact": parts[2],
                "confidence": parts[3],
                "status": parts[4],
            }
        )
    return rows


def parse_numbered_drivers(text: str, section_start: str, until: str) -> list[str]:
    if section_start not in text:
        return []
    block = extract_between(text, section_start, [until])
    items: list[str] = []
    for line in block.splitlines():
        m = re.match(r"^\d+\.\s*(.+)$", line.strip())
        if m:
            items.append(m.group(1).strip())
    return items


def parse_sub_forecasts(text: str) -> list[dict[str, Any]]:
    if "**Decomposed Sub-Forecasts**" not in text:
        return []
    block = extract_between(
        text,
        "**Decomposed Sub-Forecasts**",
        ["Final Probability Forecasts", "**Final Probability"],
    )
    out: list[dict[str, Any]] = []
    for line in block.splitlines():
        body = line.strip().lstrip("-•*").strip()
        if ":" not in body:
            continue
        name, rest = body.split(":", 1)
        name = name.strip()
        rest = rest.strip()
        if not name or len(name) > 120:
            continue
        m = SUB_PCT_RE.search(rest)
        if not m:
            # Keep component-only prose rows out of the numeric table.
            continue
        row: dict[str, Any] = {
            "component": name,
            "1wk": "",
            "1mo": "",
            "3mo": "",
            "6mo": "",
            "1yr": "",
            "18mo": "",
        }
        for i, k in enumerate(HORIZON_KEYS):
            row[k] = int(m.group(i + 1))
        out.append(row)
    return out


def parse_horizon_detail_block(block: str) -> dict[str, str]:
    bullet = r"[•\-\*]"

    def grab(label: str) -> str:
        m = re.search(
            rf"{bullet}\s*{re.escape(label)}:\s*(.+?)(?=\n{bullet}|\Z)",
            block,
            re.DOTALL | re.IGNORECASE,
        )
        return m.group(1).strip() if m else ""

    # Accept plain, bold, and simple ranges (15-20% -> first value).
    prob_m = re.search(
        rf"{bullet}\s*Probability:\s*\**(\d+)(?:\s*[-–]\s*\d+)?\s*%\**",
        block,
        re.IGNORECASE,
    )
    if not prob_m:
        prob_m = re.search(
            r"Probability:\s*\**(\d+)(?:\s*[-–]\s*\d+)?\s*%\**",
            block,
            re.IGNORECASE,
        )
    prob = prob_m.group(1) if prob_m else ""

    return {
        "probability": prob,
        "base_rate_anchor": grab("Base-rate anchor"),
        "current_evidence_adjustment": grab("Current-evidence adjustment"),
        "core_rationale": grab("Core rationale"),
        "main_gating_factor": grab("Main gating factor"),
        "raise_forecast": grab("What would raise this forecast materially"),
        "lower_forecast": grab("What would lower this forecast materially"),
        "confidence": grab("Confidence in this estimate"),
    }


def parse_final_probability_sections(text: str) -> dict[str, dict[str, str]]:
    if "**Final Probability Forecasts by Horizon**" not in text:
        return {}
    start = text.index("**Final Probability Forecasts by Horizon**")
    end_markers = [
        "**Most Likely Path**",
        "Most Likely Path",
    ]
    rest = text[start:]
    end_idx = len(rest)
    for em in end_markers:
        pos = rest.find(em)
        if pos != -1 and pos < end_idx:
            end_idx = pos
    section = rest[:end_idx]

    result: dict[str, dict[str, str]] = {}
    for label in HORIZON_LABELS:
        pat = (
            rf"\*\*{re.escape(label)}\*\*\s*:?\s*\n(.*?)(?="
            rf"\n\*\*(?:1 Week|1 Month|3 Months|6 Months|1 Year|18 Months|Most Likely Path)\*\*"
            rf"|\Z)"
        )
        m = re.search(pat, section, re.DOTALL)
        if not m:
            continue
        result[label] = parse_horizon_detail_block(m.group(1))

    # Fallback: some days emit six unlabeled probability blocks in horizon order.
    if not any(v.get("probability") for v in result.values()):
        blocks = re.split(r"\n(?=-\s*Probability:)", section)
        prob_blocks = [b for b in blocks if re.match(r"-\s*Probability:", b.strip())]
        if len(prob_blocks) >= len(HORIZON_LABELS):
            for label, block in zip(HORIZON_LABELS, prob_blocks):
                result[label] = parse_horizon_detail_block(block)

    return result


def parse_scenario_weights(text: str) -> tuple[str, str]:
    faster = ""
    prolonged = ""
    fm = re.search(
        r"\*\*Faster Normalization Case\*\*.*?(?:Scenario weight\s*~(\d+)%|weight\s*~(\d+)%)",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if fm:
        faster = fm.group(1) or fm.group(2) or ""
    pm = re.search(
        r"\*\*Prolonged Instability Case\*\*.*?(?:Scenario weight\s*~(\d+)%|weight\s*~(\d+)%)",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if pm:
        prolonged = pm.group(1) or pm.group(2) or ""
    return faster, prolonged


def parse_scenario_bodies(text: str) -> tuple[str, str]:
    faster = extract_between(
        text,
        "**Faster Normalization Case**",
        ["**Prolonged Instability Case**", "Prolonged Instability"],
    ).strip()
    prolonged = extract_between(
        text,
        "**Prolonged Instability Case**",
        ["**Red-Team Critique**", "Red-Team Critique"],
    ).strip()
    return faster, prolonged


def parse_red_team(text: str) -> str:
    return extract_between(
        text,
        "**Red-Team Critique**",
        ["**Critical Signals to Monitor**", "Critical Signals to Monitor"],
    ).strip()


def parse_critical_signals(text: str) -> str:
    return extract_between(
        text,
        "**Critical Signals to Monitor**",
        ["**Final Summary Table**", "Final Summary Table"],
    ).strip()


def parse_most_likely_path(text: str) -> str:
    return extract_between(
        text,
        "**Most Likely Path**",
        ["**Faster Normalization Case**", "Faster Normalization"],
    ).strip()


def parse_summary_table(text: str) -> list[dict[str, str]]:
    if "**Final Summary Table**" not in text and "Final Summary Table" not in text:
        return []
    block = extract_between(
        text,
        "**Final Summary Table**",
        ["This forecast remains"],
    )
    if not block.strip():
        block = extract_between(
            text,
            "**Final Summary Table**",
            [],
        )
    rows: list[dict[str, str]] = []
    for line in block.splitlines():
        line = line.strip()
        if "|" not in line:
            continue
        parts = [p.strip() for p in line.split("|")]
        while parts and parts[0] == "":
            parts.pop(0)
        while parts and parts[-1] == "":
            parts.pop()
        if len(parts) < 2:
            continue
        # Markdown separator: ---|--- or |---|---|
        if parts[0].startswith("---") or (
            len(parts) >= 1 and all(not p or set(p) <= {"-", " "} for p in parts)
        ):
            continue
        if parts[0].lower() == "horizon":
            continue
        row = {"horizon": parts[0], "probability": parts[1] if len(parts) > 1 else ""}
        if len(parts) > 2:
            row["gating"] = parts[2]
        if len(parts) > 3:
            row["upside"] = parts[3]
        if len(parts) > 4:
            row["downside"] = parts[4]
        rows.append(row)
    return rows


def conflict_day_from_snapshot(snapshot: str) -> str:
    m = re.search(r"~Day\s*(\d+)", snapshot, re.IGNORECASE)
    return m.group(1) if m else ""


def parse_file(path: Path) -> dict[str, Any]:
    text = normalize_forecast_text(_read_text(path))
    stem = path.stem  # grok_iran_forecast-20260328
    m = re.search(r"-(\d{8})$", stem)
    date_compact = m.group(1) if m else ""
    date_iso = (
        f"{date_compact[0:4]}-{date_compact[4:6]}-{date_compact[6:8]}"
        if len(date_compact) == 8
        else ""
    )

    snapshot = parse_snapshot(text)
    op_def = parse_operational_definition(text)
    evidence = parse_evidence_table(text)
    toward = parse_numbered_drivers(
        text,
        "**Key Drivers Toward Normalization**",
        "**Key Drivers Against Normalization**",
    )
    against = parse_numbered_drivers(
        text,
        "**Key Drivers Against Normalization**",
        "**Decomposed Sub-Forecasts**",
    )
    sub_forecasts = parse_sub_forecasts(text)
    horizon_details = parse_final_probability_sections(text)
    faster_w, prolonged_w = parse_scenario_weights(text)
    faster_body, prolonged_body = parse_scenario_bodies(text)
    red_team = parse_red_team(text)
    critical_signals = parse_critical_signals(text)
    most_likely = parse_most_likely_path(text)
    summary_rows = parse_summary_table(text)

    return {
        "file": str(path.name),
        "date_iso": date_iso,
        "date_compact": date_compact,
        "operational_definition": op_def,
        "snapshot": snapshot,
        "conflict_day": conflict_day_from_snapshot(snapshot),
        "evidence": evidence,
        "drivers_toward": toward,
        "drivers_against": against,
        "sub_forecasts": sub_forecasts,
        "horizon_details": horizon_details,
        "scenario_faster_weight": faster_w,
        "scenario_prolonged_weight": prolonged_w,
        "scenario_faster_body": faster_body,
        "scenario_prolonged_body": prolonged_body,
        "most_likely_path": most_likely,
        "red_team": red_team,
        "critical_signals": critical_signals,
        "summary_table": summary_rows,
    }


def rows_to_probabilities_csv(rows: list[dict[str, Any]], out_path: Path) -> None:
    fieldnames = [
        "date",
        "horizon",
        "probability",
        "base_rate_anchor",
        "confidence",
        "gating_factor",
        "upside_trigger",
        "downside_trigger",
    ]
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def write_all_csvs(parsed: list[dict[str, Any]]) -> None:
    STRUCTURED_DIR.mkdir(parents=True, exist_ok=True)

    prob_rows: list[dict[str, Any]] = []
    sub_rows: list[dict[str, Any]] = []
    ev_rows: list[dict[str, Any]] = []
    sc_rows: list[dict[str, Any]] = []
    dr_rows: list[dict[str, Any]] = []

    for p in parsed:
        d = p["date_iso"]
        for label in HORIZON_LABELS:
            det = p["horizon_details"].get(label, {})
            prob_rows.append(
                {
                    "date": d,
                    "horizon": label,
                    "probability": det.get("probability", ""),
                    "base_rate_anchor": det.get("base_rate_anchor", ""),
                    "confidence": det.get("confidence", ""),
                    "gating_factor": det.get("main_gating_factor", ""),
                    "upside_trigger": det.get("raise_forecast", ""),
                    "downside_trigger": det.get("lower_forecast", ""),
                }
            )
        for sf in p["sub_forecasts"]:
            sub_rows.append(
                {
                    "date": d,
                    "component": sf["component"],
                    **{k: sf.get(k, "") for k in HORIZON_KEYS},
                }
            )
        for ev in p["evidence"]:
            ev_rows.append(
                {
                    "date": d,
                    "evidence_item": ev["evidence_item"],
                    "source_type": ev["source_type"],
                    "impact": ev["impact"],
                    "confidence": ev["confidence"],
                    "status": ev["status"],
                }
            )
        sc_rows.append(
            {
                "date": d,
                "faster_weight": p["scenario_faster_weight"],
                "prolonged_weight": p["scenario_prolonged_weight"],
            }
        )
        for i, t in enumerate(p["drivers_toward"], start=1):
            dr_rows.append(
                {"date": d, "direction": "toward", "rank": i, "driver_text": t}
            )
        for i, t in enumerate(p["drivers_against"], start=1):
            dr_rows.append(
                {"date": d, "direction": "against", "rank": i, "driver_text": t}
            )

    rows_to_probabilities_csv(prob_rows, STRUCTURED_DIR / "probabilities.csv")

    with (STRUCTURED_DIR / "sub_forecasts.csv").open("w", newline="", encoding="utf-8") as f:
        fn = ["date", "component"] + HORIZON_KEYS
        w = csv.DictWriter(f, fieldnames=fn)
        w.writeheader()
        for row in sub_rows:
            w.writerow(row)

    with (STRUCTURED_DIR / "evidence_ledger.csv").open("w", newline="", encoding="utf-8") as f:
        fn = ["date", "evidence_item", "source_type", "impact", "confidence", "status"]
        w = csv.DictWriter(f, fieldnames=fn)
        w.writeheader()
        for row in ev_rows:
            w.writerow(row)

    with (STRUCTURED_DIR / "scenarios.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["date", "faster_weight", "prolonged_weight"])
        w.writeheader()
        for row in sc_rows:
            w.writerow(row)

    with (STRUCTURED_DIR / "drivers.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["date", "direction", "rank", "driver_text"])
        w.writeheader()
        for row in dr_rows:
            w.writerow(row)


def build_narratives_json(parsed: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for p in parsed:
        d = p["date_iso"]
        out[d] = {
            "snapshot": p["snapshot"],
            "most_likely_path": p["most_likely_path"],
            "faster_case": p["scenario_faster_body"],
            "prolonged_case": p["scenario_prolonged_body"],
            "red_team": p["red_team"],
            "critical_signals": p["critical_signals"],
            "operational_definition": p["operational_definition"],
            "scenario_faster_weight": p["scenario_faster_weight"],
            "scenario_prolonged_weight": p["scenario_prolonged_weight"],
            "horizon_details": p["horizon_details"],
            "summary_table": p["summary_table"],
        }
    return out


def html_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def generate_forecast_evolution_md(parsed: list[dict[str, Any]]) -> str:
    """Aggregate markdown for the Forecast evolution section (written to structured/)."""
    if not parsed:
        return "## Forecast evolution analysis\n\n_No forecast runs parsed._\n"

    first, last = parsed[0], parsed[-1]
    d0, d1 = first["date_iso"], last["date_iso"]
    lines: list[str] = [
        "## Gulf normality odds fall across all horizons",
        "",
        f"Automated first-to-latest deltas across **{len(parsed)}** runs from **{d0}** to **{d1}**.",
        "",
        "### Headline probabilities (first run → latest)",
        "",
    ]

    for label in HORIZON_LABELS:
        a = first["horizon_details"].get(label, {}).get("probability", "")
        b = last["horizon_details"].get(label, {}).get("probability", "")
        try:
            ia, ib = int(a), int(b)
            delta = ib - ia
            sign = "+" if delta >= 0 else ""
            lines.append(f"- **{label}:** {ia}% → {ib}% ({sign}{delta} pts)")
        except (ValueError, TypeError):
            lines.append(f"- **{label}:** {a!r} → {b!r}")

    fa, pa = first.get("scenario_faster_weight", ""), first.get(
        "scenario_prolonged_weight", ""
    )
    la, pb = last.get("scenario_faster_weight", ""), last.get(
        "scenario_prolonged_weight", ""
    )
    deltas_pts: list[tuple[str, int]] = []
    for label in HORIZON_LABELS:
        a = first["horizon_details"].get(label, {}).get("probability", "")
        b = last["horizon_details"].get(label, {}).get("probability", "")
        try:
            deltas_pts.append((label, int(b) - int(a)))
        except (ValueError, TypeError):
            pass
    if deltas_pts:
        biggest = max(deltas_pts, key=lambda t: abs(t[1]))
        net = sum(t[1] for t in deltas_pts)
        lines.extend(
            [
                "",
                "### Automated cross-run notes",
                "",
                f"- **Largest horizon move:** {biggest[0]} ({biggest[1]:+d} pts).",
                f"- **Net change across horizons (sum of Δ):** {net:+d} pts.",
                "",
            ]
        )

    lines.extend(
        [
            "### Scenario weights (faster vs prolonged instability)",
            "",
            f"- **First ({d0}):** faster ~{fa}% · prolonged ~{pa}%",
            f"- **Latest ({d1}):** faster ~{la}% · prolonged ~{pb}%",
            "",
        ]
    )

    return "\n".join(lines)


def build_html(
    parsed: list[dict[str, Any]],
    narratives: dict[str, Any],
    embedded_json: str,
    source_prompt: str,
    qual_md: str,
) -> str:
    js_path = Path(__file__).resolve().parent / "dashboard_client.js"
    client_js = _read_text(js_path)
    client_js = client_js.replace("__HORIZON_KEYS__", json.dumps(HORIZON_KEYS))
    client_js = client_js.replace("__HORIZON_LABELS__", json.dumps(HORIZON_LABELS))

    dates = [p["date_iso"] for p in parsed]
    date_min = dates[0] if dates else ""
    date_max = dates[-1] if dates else ""
    latest = parsed[-1] if parsed else None

    gen_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    prompt_escaped = html_escape(source_prompt)
    qual_escaped = html_escape(qual_md)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Persian Gulf normality odds fall from March to mid-November 2026</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/vega@5"></script>
  <script src="https://cdn.jsdelivr.net/npm/vega-lite@5"></script>
  <script src="https://cdn.jsdelivr.net/npm/vega-embed@6"></script>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/d3-milestones@2.0.0/build/d3-milestones.css">
  <script src="https://cdn.jsdelivr.net/npm/d3-milestones@2.0.0/build/d3-milestones.min.js"></script>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Space+Grotesk:wght@500;600&display=swap');
    body {{ font-family: 'Inter', system-ui, sans-serif; }}
    .heading-font {{ font-family: 'Space Grotesk', sans-serif; }}
    .evidence-positive {{ background-color: rgb(16 185 129 / 0.12); color: rgb(134 239 172); }}
    .evidence-negative {{ background-color: rgb(245 158 11 / 0.12); color: rgb(251 191 36); }}
    .evidence-mild {{ background-color: rgb(59 130 246 / 0.12); color: rgb(147 197 253); }}
    @media print {{
      body {{ background: white !important; color: black !important; }}
      .no-print {{ display: none !important; }}
      .print\\:bg-white {{ print-color-adjust: exact; background: white !important; }}
    }}
    .sticky-nav {{ backdrop-filter: blur(12px); }}
    .prose-snapshot p {{ margin-bottom: 0.75rem; }}
    .sr-only {{ position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); white-space: nowrap; border: 0; }}
    .date-calendar {{
      display: flex;
      gap: 1px;
      align-items: stretch;
      height: 44px;
      overflow: hidden;
      border-radius: 10px;
      background: #09090b;
    }}
    .date-calendar button {{
      flex: 1 1 0;
      min-width: 0;
      padding: 0;
      border: 0;
      cursor: pointer;
      position: relative;
      opacity: 0.92;
    }}
    .date-calendar button:hover {{ opacity: 1; filter: brightness(1.15); }}
    .date-calendar button[aria-selected="true"] {{
      outline: 2px solid #67e8f9;
      outline-offset: -2px;
      z-index: 1;
      opacity: 1;
    }}
    .date-calendar button.month-start::after {{
      content: attr(data-month);
      position: absolute;
      left: 2px;
      bottom: 2px;
      font-size: 8px;
      line-height: 1;
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      color: rgba(244,244,245,0.85);
      text-shadow: 0 0 4px rgba(0,0,0,0.9);
      pointer-events: none;
    }}
    .date-slider {{
      -webkit-appearance: none;
      appearance: none;
      height: 6px;
      border-radius: 999px;
      background: linear-gradient(90deg, #0d47a1, #00acc1, #43a047);
      outline: none;
    }}
    .date-slider::-webkit-slider-thumb {{
      -webkit-appearance: none;
      appearance: none;
      width: 18px;
      height: 18px;
      border-radius: 999px;
      background: #ecfeff;
      border: 2px solid #22d3ee;
      box-shadow: 0 0 0 4px rgba(34, 211, 238, 0.2);
      cursor: pointer;
    }}
    .date-slider::-moz-range-thumb {{
      width: 18px;
      height: 18px;
      border-radius: 999px;
      background: #ecfeff;
      border: 2px solid #22d3ee;
      cursor: pointer;
    }}
    .memo-body {{
      max-width: 52rem;
    }}
    .memo-body > h1 {{
      display: none;
    }}
    .memo-body > blockquote {{
      margin: 0 0 1.75rem;
      padding: 1.1rem 1.25rem;
      border-left: 3px solid #f59e0b;
      background: linear-gradient(90deg, rgba(245, 158, 11, 0.12), rgba(24, 24, 27, 0.4));
      border-radius: 0 1rem 1rem 0;
      color: #fafafa;
      font-size: 1.05rem;
      line-height: 1.55;
    }}
    .memo-body > blockquote p {{
      margin: 0;
    }}
    .memo-body > p:first-of-type {{
      font-size: 1.05rem;
      line-height: 1.65;
      color: #e4e4e7;
    }}
    .memo-body h2 {{
      font-family: 'Space Grotesk', sans-serif;
      font-size: 1.35rem;
      font-weight: 600;
      color: #f4f4f5;
      margin: 2.25rem 0 0.85rem;
      padding-top: 1.5rem;
      border-top: 1px solid #27272a;
      letter-spacing: -0.02em;
    }}
    .memo-body h2:first-of-type {{
      margin-top: 1.5rem;
    }}
    .memo-body h3 {{
      font-family: 'Space Grotesk', sans-serif;
      font-size: 0.95rem;
      font-weight: 600;
      color: #a1a1aa;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      margin: 1.5rem 0 0.75rem;
    }}
    .memo-body p {{
      margin: 0 0 1rem;
      line-height: 1.7;
      color: #d4d4d8;
    }}
    .memo-body ul {{
      margin: 0 0 1.25rem;
      padding: 0;
      list-style: none;
      display: grid;
      gap: 0.65rem;
    }}
    .memo-body li {{
      position: relative;
      padding: 0.85rem 1rem 0.85rem 1.1rem;
      background: rgba(24, 24, 27, 0.85);
      border: 1px solid #27272a;
      border-radius: 0.85rem;
      color: #d4d4d8;
      line-height: 1.55;
    }}
    .memo-body li strong:first-child {{
      color: #fbbf24;
      display: inline;
    }}
    .memo-body ol {{
      margin: 0 0 1.25rem;
      padding-left: 1.25rem;
      color: #d4d4d8;
      display: grid;
      gap: 0.75rem;
    }}
    .memo-body ol li {{
      background: transparent;
      border: 0;
      padding: 0;
      border-radius: 0;
    }}
    .memo-body table {{
      width: 100%;
      border-collapse: collapse;
      margin: 0.75rem 0 1.5rem;
      font-size: 0.85rem;
      font-variant-numeric: tabular-nums;
    }}
    .memo-body thead th {{
      text-align: center;
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 0.7rem;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      color: #a1a1aa;
      background: #09090b;
      border-bottom: 1px solid #3f3f46;
      padding: 0.65rem 0.5rem;
    }}
    .memo-body thead th:first-child {{
      text-align: left;
    }}
    .memo-body tbody td {{
      text-align: center;
      padding: 0.7rem 0.5rem;
      border-bottom: 1px solid #27272a;
      color: #e4e4e7;
    }}
    .memo-body tbody td:first-child {{
      text-align: left;
      color: #a1a1aa;
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 0.75rem;
    }}
    .memo-body tbody tr:last-child td {{
      color: #67e8f9;
      font-weight: 600;
      border-bottom: 0;
    }}
    .memo-body tbody tr:last-child td:first-child {{
      color: #67e8f9;
      font-weight: 500;
    }}
    .memo-body strong {{
      color: #fafafa;
      font-weight: 600;
    }}
    .memo-body > h2:last-of-type {{
      color: #67e8f9;
      border-top-color: #164e63;
    }}
    /* d3-milestones on dark briefing chrome */
    #chart-milestones {{
      margin-top: 0.5rem;
      padding: 0.75rem 0.25rem 0.25rem;
      overflow-x: auto;
    }}
    #chart-milestones .milestones {{
      color: #e4e4e7;
      font-family: Inter, system-ui, sans-serif;
    }}
    #chart-milestones .milestones__horizontal_line {{
      background-color: #3f3f46;
    }}
    #chart-milestones .milestones__group__bullet {{
      background-color: #f59e0b;
      border-color: #f59e0b;
    }}
    #chart-milestones .milestones__group__label {{
      color: #a1a1aa;
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 10px;
    }}
    #chart-milestones .milestones__group__label-text {{
      background: #18181b;
      border: 1px solid #3f3f46;
      border-radius: 0.65rem;
      color: #e4e4e7;
      font-size: 12px;
      line-height: 1.35;
      padding: 0.45rem 0.6rem;
      max-width: 11rem;
      cursor: pointer;
    }}
    #chart-milestones .milestones__group__label-text:hover {{
      border-color: #67e8f9;
      color: #ecfeff;
    }}
  </style>
</head>
<body class="bg-zinc-950 text-zinc-100 min-h-screen">
  <script type="application/json" id="forecast-data">{embedded_json}</script>

  <nav class="sticky-nav bg-zinc-950/90 border-b border-zinc-800 top-0 z-50 no-print">
    <div class="max-w-screen-2xl mx-auto px-4 md:px-8 py-3 flex flex-wrap items-center justify-between gap-2">
      <div class="flex items-center gap-2">
        <div class="w-7 h-7 bg-cyan-400 rounded-lg flex items-center justify-center text-zinc-950 font-bold text-xs">PG</div>
        <span class="heading-font text-lg font-semibold tracking-tight">GULF NORMALITY ODDS</span>
        <span class="text-cyan-300 text-xs hidden sm:inline">MAR–NOV 2026</span>
      </div>
      <div class="hidden md:flex items-center gap-6 text-xs font-medium">
        <a href="#trajectory" class="hover:text-cyan-300">TRAJECTORY</a>
        <a href="#heatmap" class="hover:text-cyan-300">GATES</a>
        <a href="#detail" class="hover:text-cyan-300">DAILY</a>
        <a href="#deltas" class="hover:text-cyan-300">FIRST→LATEST</a>
        <a href="#qualitative" class="hover:text-cyan-300">MEMO</a>
        <a href="#prompt-ref" class="hover:text-cyan-300">PROMPT</a>
      </div>
      <div class="text-[10px] uppercase tracking-wider font-mono text-zinc-500">{date_min} – {date_max}</div>
    </div>
  </nav>

  <header class="border-b border-zinc-800 bg-gradient-to-br from-zinc-900 to-black">
    <div class="max-w-screen-2xl mx-auto px-4 md:px-8 py-10 md:py-14">
      <div class="inline-flex items-center gap-2 bg-zinc-900 border border-zinc-700 rounded-full px-3 py-1 text-[10px] tracking-widest font-mono mb-4">
        <span class="w-2 h-2 bg-red-500 rounded-full animate-pulse"></span>
        ACTIVE CONFLICT
      </div>
      <h1 class="heading-font text-4xl md:text-6xl font-semibold tracking-tighter leading-tight mb-3">
        Persian Gulf normality odds fall from March through mid-November 2026
      </h1>
      <p class="text-zinc-400 max-w-3xl text-lg">
        Daily superforecasts of functional normality after the 2026 Iran War: 18-month odds drop from 80% to 62%; 6-month odds from 45% to 28%.
      </p>
      <div class="mt-6 flex flex-wrap gap-4 text-sm">
        <div class="bg-zinc-900/80 border border-zinc-700 rounded-xl px-4 py-2">
          <span class="text-zinc-500 text-xs uppercase">Runs</span>
          <span class="ml-2 font-mono text-cyan-300">{len(parsed)}</span>
        </div>
        <div class="bg-zinc-900/80 border border-zinc-700 rounded-xl px-4 py-2">
          <span class="text-zinc-500 text-xs uppercase">Latest</span>
          <span class="ml-2 font-mono text-cyan-300">{date_max or "—"}</span>
        </div>
        <div class="bg-zinc-900/80 border border-zinc-700 rounded-xl px-4 py-2" id="conflict-day-badge">
          <span class="text-zinc-500 text-xs uppercase">Conflict day (latest)</span>
          <span class="ml-2 font-mono text-amber-300">{latest.get("conflict_day", "—") if latest else "—"}</span>
        </div>
      </div>
    </div>
  </header>

  <section id="trajectory" class="max-w-screen-2xl mx-auto px-4 md:px-8 py-10 border-b border-zinc-800">
    <div class="text-xs font-mono uppercase text-cyan-400 mb-2">Trajectory</div>
    <h2 class="heading-font text-2xl md:text-3xl font-semibold mb-4">April and June lifts reverse; by mid-November every horizon sits below March</h2>
    <p class="text-zinc-400 text-sm max-w-3xl mb-6">Probability curves with vertical event markers. Timeline below uses the same key dates — click a label to open that day’s briefing.</p>
    <div id="chart-trajectory" class="w-full min-h-[380px]"></div>
    <div class="text-xs font-mono uppercase text-amber-300 mt-8 mb-2">Key events</div>
    <div id="chart-milestones" class="w-full min-h-[140px]"></div>
  </section>

  <section id="heatmap" class="max-w-screen-2xl mx-auto px-4 md:px-8 py-10 border-b border-zinc-800 bg-zinc-900/40">
    <div class="mb-4">
      <div class="text-xs font-mono uppercase text-cyan-400 mb-2">Gating components</div>
      <h2 class="heading-font text-2xl md:text-3xl font-semibold">At six months, insurance and transit stay well behind strike-pause odds</h2>
      <p class="text-zinc-500 text-sm mt-2 max-w-3xl">Same horizon, three gates. Absolute levels on the left; how many points each commercial gate trails strike-pause on the right.</p>
    </div>
    <div id="chart-heatmap" class="w-full grid grid-cols-1 lg:grid-cols-2 gap-6"></div>
  </section>

  <section id="detail" class="max-w-screen-2xl mx-auto px-4 md:px-8 py-10 border-b border-zinc-800">
    <div class="mb-6 space-y-4">
      <div class="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
        <div>
          <div class="text-xs font-mono uppercase text-cyan-400 mb-2">Daily briefing</div>
          <h2 class="heading-font text-2xl md:text-3xl font-semibold">Scrub the forecast calendar</h2>
          <p class="text-zinc-500 text-sm mt-1 max-w-xl">Each cell is a run day; color is that day's 6-month normality odds. Drag the slider or click a cell.</p>
        </div>
        <div class="flex items-center gap-2">
          <button type="button" id="date-prev" class="px-3 py-2 rounded-lg border border-zinc-600 bg-zinc-900 text-zinc-200 text-sm hover:border-cyan-500" aria-label="Previous forecast day">‹</button>
          <div class="text-right min-w-[9.5rem]">
            <div id="date-label" class="font-mono text-cyan-300 text-lg leading-tight">—</div>
            <div id="date-meta" class="text-[10px] uppercase tracking-wider text-zinc-500 font-mono">—</div>
          </div>
          <button type="button" id="date-next" class="px-3 py-2 rounded-lg border border-zinc-600 bg-zinc-900 text-zinc-200 text-sm hover:border-cyan-500" aria-label="Next forecast day">›</button>
        </div>
      </div>
      <div id="date-rail" class="bg-zinc-900/80 border border-zinc-700 rounded-2xl p-4 space-y-3">
        <div id="date-calendar" class="date-calendar" role="listbox" aria-label="Forecast calendar"></div>
        <input id="date-slider" type="range" min="0" max="0" value="0" class="date-slider w-full" aria-label="Forecast date slider" />
        <div class="flex justify-between text-[10px] font-mono text-zinc-500 uppercase tracking-wider">
          <span id="date-range-start">—</span>
          <span>6-month odds → cell color</span>
          <span id="date-range-end">—</span>
        </div>
      </div>
      <select id="date-select" class="sr-only" aria-hidden="true" tabindex="-1"></select>
    </div>

    <div id="detail-pane" class="space-y-10">
      <!-- injected -->
    </div>
  </section>

  <section id="deltas" class="max-w-screen-2xl mx-auto px-4 md:px-8 py-10 border-b border-zinc-800">
    <div class="text-xs font-mono uppercase text-cyan-400 mb-2">First → latest</div>
    <h2 class="heading-font text-2xl md:text-3xl font-semibold mb-4">18-month normality odds drop 18 points; every horizon ends lower</h2>
    <div class="overflow-x-auto">
      <table class="w-full text-sm border border-zinc-800 rounded-xl overflow-hidden">
        <thead class="bg-zinc-900 text-zinc-400 text-xs font-mono">
          <tr>
            <th class="text-left p-3">Horizon</th>
            <th class="text-center p-3">First</th>
            <th class="text-center p-3">Latest</th>
            <th class="text-center p-3">Δ</th>
            <th class="text-left p-3 min-w-[180px]">Sparkline</th>
          </tr>
        </thead>
        <tbody id="delta-table-body" class="divide-y divide-zinc-800"></tbody>
      </table>
    </div>
    <div id="spark-container" class="hidden"></div>
  </section>

  <section id="qualitative" class="max-w-screen-2xl mx-auto px-4 md:px-8 py-10 border-b border-zinc-800 bg-black/40">
    <div class="text-xs font-mono uppercase text-amber-300 mb-2">Longitudinal memo</div>
    <h2 class="heading-font text-2xl md:text-3xl font-semibold mb-2 max-w-3xl">Why the curve fell: settlements failed and commercial gates stayed binding</h2>
    <p class="text-zinc-400 text-sm md:text-base mb-6 max-w-2xl">242 daily runs · 18 Mar – 15 Nov 2026 · functional normality, not ceasefire alone</p>
    <div id="qualitative-body" class="memo-body bg-zinc-900/80 border border-zinc-700 rounded-2xl p-6 md:p-8 text-zinc-300"></div>
    <script type="text/template" id="qualitative-md">{qual_escaped}</script>
  </section>

  <section id="prompt-ref" class="max-w-screen-2xl mx-auto px-4 md:px-8 py-10">
    <details class="bg-zinc-900 border border-zinc-700 rounded-2xl p-4 md:p-6">
      <summary class="font-medium text-lg cursor-pointer select-none text-zinc-200">Source forecast prompt (grok_iran_forecast.md)</summary>
      <p class="mt-4 text-xs text-zinc-500 mb-2">Daily generation uses this prompt. Copied verbatim from the repo at build time.</p>
      <pre class="bg-black p-4 rounded-xl overflow-x-auto text-xs text-zinc-300 whitespace-pre-wrap font-mono max-h-[480px] overflow-y-auto"><code id="source-prompt-text">{prompt_escaped}</code></pre>
      <button type="button" id="copy-prompt-btn" class="mt-4 px-4 py-2 bg-cyan-900 text-cyan-200 rounded-xl text-sm hover:bg-cyan-800">Copy prompt</button>
    </details>
  </section>

  <footer class="border-t border-zinc-800 bg-zinc-950 py-8">
    <div class="max-w-screen-2xl mx-auto px-4 md:px-8 text-xs text-zinc-500 font-mono">
      <p>Generated <span id="gen-time">{gen_time}</span></p>
    </div>
  </footer>

  <script>
{client_js}
  </script>
</body>
</html>
"""


def write_coverage_report(parsed: list[dict[str, Any]], failed: list[dict[str, str]]) -> Path:
    """Write parse coverage diagnostics for the full extract."""
    STRUCTURED_DIR.mkdir(parents=True, exist_ok=True)
    missing_prob: list[str] = []
    missing_evidence: list[str] = []
    missing_sub: list[str] = []
    partial_horizons: list[dict[str, Any]] = []

    for p in parsed:
        d = p["date_iso"]
        present = [
            label
            for label in HORIZON_LABELS
            if p["horizon_details"].get(label, {}).get("probability")
        ]
        if len(present) < len(HORIZON_LABELS):
            missing_prob.append(d)
            partial_horizons.append(
                {
                    "date": d,
                    "found": present,
                    "missing": [h for h in HORIZON_LABELS if h not in present],
                }
            )
        if not p["evidence"]:
            missing_evidence.append(d)
        if not p["sub_forecasts"]:
            missing_sub.append(d)

    report = {
        "parsed_files": len(parsed),
        "parse_failures": failed,
        "missing_any_headline_probability": missing_prob,
        "partial_horizons": partial_horizons,
        "missing_evidence_rows": missing_evidence,
        "missing_sub_forecasts": missing_sub,
        "headline_probability_coverage": round(
            1.0 - (len(missing_prob) / len(parsed)) if parsed else 0.0, 4
        ),
    }
    out = STRUCTURED_DIR / "parse_coverage.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        f"Coverage: {len(parsed)} parsed; "
        f"missing probs={len(missing_prob)}; "
        f"missing evidence={len(missing_evidence)}; "
        f"missing sub-forecasts={len(missing_sub)}; "
        f"failures={len(failed)}"
    )
    return out


def main() -> int:
    files = sorted(FORECASTS_DIR.glob("grok_iran_forecast-*.md"))
    if not files:
        print("No forecast files found.", file=sys.stderr)
        return 1

    parsed: list[dict[str, Any]] = []
    failed: list[dict[str, str]] = []
    for path in files:
        try:
            parsed.append(parse_file(path))
        except Exception as e:
            print(f"Warning: failed to parse {path}: {e}", file=sys.stderr)
            failed.append({"file": path.name, "error": str(e)})

    parsed.sort(key=lambda x: x["date_iso"])
    write_coverage_report(parsed, failed)

    write_all_csvs(parsed)
    narratives = build_narratives_json(parsed)

    STRUCTURED_DIR.mkdir(parents=True, exist_ok=True)
    (STRUCTURED_DIR / "narratives.json").write_text(
        json.dumps(narratives, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # Build long-form data for charts
    prob_long: list[dict[str, Any]] = []
    by_date_horizon: dict[tuple[str, str], float] = {}
    for p in parsed:
        d = p["date_iso"]
        for label in HORIZON_LABELS:
            prob_str = p["horizon_details"].get(label, {}).get("probability", "")
            try:
                v = float(prob_str) if prob_str else float("nan")
            except ValueError:
                v = float("nan")
            by_date_horizon[(d, label)] = v

    for p in parsed:
        d = p["date_iso"]
        for label in HORIZON_LABELS:
            v = by_date_horizon.get((d, label), float("nan"))
            # prev
            prev = float("nan")
            idx = parsed.index(p)
            if idx > 0:
                pd = parsed[idx - 1]["date_iso"]
                prev = by_date_horizon.get((pd, label), float("nan"))
            prob_long.append(
                {
                    "date": d,
                    "horizon": label,
                    "probability": None if isinstance(v, float) and math.isnan(v) else v,
                    "prevProbability": None
                    if isinstance(prev, float) and math.isnan(prev)
                    else prev,
                }
            )

    sub_long: list[dict[str, Any]] = []
    for p in parsed:
        d = p["date_iso"]
        for sf in p["sub_forecasts"]:
            comp = sf["component"]
            for hk in HORIZON_KEYS:
                val = sf.get(hk)
                if val == "" or val is None:
                    continue
                sub_long.append(
                    {
                        "date": d,
                        "component": comp,
                        "horizonKey": hk,
                        "value": int(val),
                    }
                )

    events_path = ROOT / "analysis" / "key_events.json"
    key_events: list[dict[str, Any]] = []
    if events_path.exists():
        try:
            key_events = json.loads(_read_text(events_path))
        except json.JSONDecodeError:
            key_events = []

    embedded = {
        "dates": [p["date_iso"] for p in parsed],
        "narratives": narratives,
        "parsedByDate": {p["date_iso"]: p for p in parsed},
        "probLong": prob_long,
        "subLong": sub_long,
        "keyEvents": key_events,
    }

    source_prompt = (
        _read_text(SOURCE_PROMPT_PATH) if SOURCE_PROMPT_PATH.exists() else ""
    )

    evolution_md = generate_forecast_evolution_md(parsed)
    (STRUCTURED_DIR / "forecast_evolution.md").write_text(
        evolution_md, encoding="utf-8"
    )

    memo_path = ROOT / "analysis" / "memo_longitudinal.md"
    # Memo alone in the qualitative pane; first→latest deltas already cover machine notes.
    if memo_path.exists():
        qual_md = _read_text(memo_path)
    else:
        qual_md = evolution_md

    html = build_html(
        parsed,
        narratives,
        json.dumps(embedded, ensure_ascii=False),
        source_prompt,
        qual_md,
    )
    HTML_OUT.parent.mkdir(parents=True, exist_ok=True)
    HTML_OUT.write_text(html, encoding="utf-8")
    # GitHub Pages serves docs/index.html
    pages_index = ROOT / "docs" / "index.html"
    pages_index.parent.mkdir(parents=True, exist_ok=True)
    pages_index.write_text(html, encoding="utf-8")

    print(f"Wrote {STRUCTURED_DIR}/ (*.csv, narratives.json, forecast_evolution.md)")
    print(f"Wrote {HTML_OUT}")
    print(f"Wrote {pages_index}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
