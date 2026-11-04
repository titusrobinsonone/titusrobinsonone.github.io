"""Build the static case-study report (docs/salary-qa.html) and assets from a
pipeline run. Standard library only.

    python src/salary_survey_qa.py --output out/salary_qa
    python src/make_salary_report.py --run out/salary_qa
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import random
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
ASSETS = DOCS / "assets" / "salary-qa"

# Hand review of a fixed random sample (seed 2026) of 100 code assignments.
# Indices into that sample that the reviewer judged WRONG, with the reason.
AUDIT_SEED = 2026
AUDIT_ERRORS = {
    11: "'presented with a contract' is an offer, not contract work",
    16: "per-hour shift bonus is shift pay, not hourly pay",
    18: "company sales goal bonus is a bonus, not commission",
    27: "overtime hours, not a schedule statement",
    31: "'not 40' negation leaked into the next sentence about stock",
    38: "'did not include superannuation' means excluded from the figure, not absent",
    61: "'does not include stock options' means excluded, not absent",
    79: "equity refresher text matched overtime pattern",
}


def bars(items: list[tuple[str, float]], unit: str = "", width: int = 640, color: str = "#2f5d50") -> str:
    """Horizontal bar chart as inline SVG (labels left, values right)."""
    if not items:
        return ""
    top = max(v for _, v in items) or 1
    row, label_w, pad = 26, 230, 70
    h = row * len(items) + 8
    out = [f'<svg viewBox="0 0 {width} {h}" role="img" class="chart">']
    for i, (label, v) in enumerate(items):
        y = i * row + 4
        w = (width - label_w - pad) * v / top
        out.append(f'<text x="{label_w - 8}" y="{y + 16}" text-anchor="end" class="lbl">{html.escape(label)}</text>')
        out.append(f'<rect x="{label_w}" y="{y + 3}" width="{w:.1f}" height="17" rx="2" fill="{color}"/>')
        out.append(f'<text x="{label_w + w + 6:.1f}" y="{y + 16}" class="val">{v:,.0f}{unit}</text>')
    out.append("</svg>")
    return "".join(out)


def write_audit(run_dir: Path) -> dict:
    with (run_dir / "open_end_codes.csv").open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    pairs = [(r["row_id"], c, r["text"]) for r in rows for c in r["codes"].split("; ") if c != "Uncoded"]
    random.seed(AUDIT_SEED)
    sample = random.sample(pairs, 100)
    with (ASSETS / "codeframe_audit.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["sample_index", "row_id", "code", "verdict", "note", "text"])
        for i, (rid, code, text) in enumerate(sample):
            bad = i in AUDIT_ERRORS
            w.writerow([i, rid, code, "wrong" if bad else "correct", AUDIT_ERRORS.get(i, ""), text])
    return {"sampled": 100, "correct": 100 - len(AUDIT_ERRORS)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=Path, default=ROOT / "out" / "salary_qa")
    args = ap.parse_args()
    ASSETS.mkdir(parents=True, exist_ok=True)
    rep = json.loads((args.run / "quality_report.json").read_text(encoding="utf-8"))
    audit = write_audit(args.run)
    rep["codeframe_audit"] = audit
    (ASSETS / "quality_report.json").write_text(json.dumps(rep, indent=2), encoding="utf-8")
    shutil.copy(args.run / "exceptions.csv", ASSETS / "exceptions.csv")
    shutil.copy(args.run / "rejected.csv", ASSETS / "rejected.csv")

    rules = [(r["rule"].replace("_", " "), r["rows"]) for r in rep["rules"]]
    codes = [(k, v) for k, v in rep["open_ends"]["codes"].items() if not k.endswith("(none)")]
    ind = [(r["industry"], r["median"]) for r in rep["us_industry_medians_n300"]]
    p, o, imp = rep["privacy"], rep["open_ends"], rep["impact_us_usd"]
    raw, clean = imp["raw"], imp["clean_excl_outliers"]
    pct_mean = 100 * (raw["mean"] - clean["mean"]) / raw["mean"]

    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Salary Survey Data Quality | Titus Robinson</title>
<meta name="description" content="Data-quality, privacy and open-text coding pipeline on the real 2021 Ask a Manager salary survey.">
<link rel="icon" href="assets/favicon.svg">
<style>
:root{{--ink:#1d2a26;--muted:#5d6b66;--line:#d9e0dc;--bg:#f7f8f6;--card:#fff;--accent:#2f5d50;--warn:#9a5b13}}
*{{box-sizing:border-box}}body{{margin:0;font:16px/1.55 -apple-system,Segoe UI,Roboto,Arial,sans-serif;color:var(--ink);background:var(--bg)}}
.wrap{{max-width:980px;margin:0 auto;padding:32px 16px 64px}}a{{color:var(--accent)}}
h1{{font:600 34px/1.15 Georgia,serif;margin:8px 0 10px}}h2{{font:600 22px Georgia,serif;margin:40px 0 8px}}
.kicker{{text-transform:uppercase;letter-spacing:.12em;font-size:12px;color:var(--muted)}}
.lede{{font-size:18px;color:var(--muted);max-width:760px}}
.stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin:24px 0}}
.stat{{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:14px 16px}}
.stat b{{display:block;font:600 28px Georgia,serif}}.stat span{{color:var(--muted);font-size:14px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:18px;margin:12px 0;overflow-x:auto}}
.chart{{width:100%;min-width:520px;height:auto}}.lbl{{font-size:12px;fill:var(--ink)}}.val{{font-size:12px;fill:var(--muted)}}
table{{border-collapse:collapse;width:100%;font-size:14px}}td,th{{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left}}
th{{color:var(--muted);font-weight:600}}td.n{{text-align:right;font-variant-numeric:tabular-nums}}
.note{{font-size:14px;color:var(--muted)}}
</style></head><body><main class="wrap">
<p class="kicker"><a href="index.html">Titus Robinson</a> · Real-world data project</p>
<h1>Cleaning 26,000 real salary survey answers, without losing a row.</h1>
<p class="lede">The 2021 Ask a Manager salary survey is a public Google Form with {rep['rows_in']:,} self-reported responses, typed by real people, in free text. This pipeline standardizes it, applies severity-graded QA rules, checks re-identification risk, codes the open-ended answers and shows how much cleaning changes the answer.</p>
<div class="stats">
<div class="stat"><b>{rep['rows_in']:,}</b><span>rows in; {rep['rows_clean']:,} clean + {rep['rows_rejected']:,} rejected, every row reconciles</span></div>
<div class="stat"><b>{rep['country']['distinct_raw_spellings']} → {rep['country']['distinct_after']}</b><span>country spellings standardized</span></div>
<div class="stat"><b>{p['full_release_pct_below_k']}%</b><span>of rows unique or near-unique (k&lt;{p['k_threshold']}) on title + city + industry + age</span></div>
<div class="stat"><b>{o['coverage_pct']}%</b><span>of {o['answered']:,} open-ended answers coded; {audit['correct']}/100 spot-checked codes correct</span></div>
</div>

<h2>1. What the raw data gets wrong</h2>
<p>Raw average salary for USD-paid respondents is <b>${raw['mean']:,}</b>, pulled up by entries such as ${raw['max']:,}. After cleaning and excluding robust outliers it is <b>${clean['mean']:,}</b> ({pct_mean:.1f}% lower). The median stays at ${clean['median']:,}, which is why the cleaned mean, not the raw one, belongs in a report.</p>
<div class="card">{bars(rules, "")}</div>
<p class="note">Rejects ({rep['rows_rejected']:,} rows) are duplicates, unparseable or missing currencies, zero salaries and salaries that are clearly typed in thousands or as hourly pay. Everything else is kept with a warning, so analysts decide, not the script. Full exception log: <a href="assets/salary-qa/exceptions.csv">exceptions.csv</a>.</p>

<h2>2. Privacy: anonymous is not the same as safe</h2>
<p>A regex scan for emails, phones, SSNs, URLs and handles found only {sum(p['pii_hits'].values())} URLs; the form did not ask for direct identifiers. The bigger risk is combinations. On job title + city + industry + age band, <b>{p['full_release_pct_below_k']}%</b> of rows fall in groups smaller than {p['k_threshold']}. Dropping city still leaves {p['drop_city_pct_below_k']}%. Releasing only industry + age band + country brings it down to <b>{p['coarse_pct_below_k']}%</b>.</p>
<table><tr><th>Release level</th><th class="n">Rows in groups &lt; {p['k_threshold']}</th></tr>
<tr><td>Job title + city + industry + age</td><td class="n">{p['full_release_pct_below_k']}%</td></tr>
<tr><td>Job title + industry + age (city dropped)</td><td class="n">{p['drop_city_pct_below_k']}%</td></tr>
<tr><td>Industry + age + country</td><td class="n">{p['coarse_pct_below_k']}%</td></tr></table>

<h2>3. What people say about their pay</h2>
<p>{o['answered']:,} respondents added context on income. A market-research style codeframe (multi-code, with negation handling so "no overtime" is not coded as overtime) codes {o['coverage_pct']}% of them. A hand review of 100 random code assignments judged {audit['correct']} correct; the misses and their reasons are in <a href="assets/salary-qa/codeframe_audit.csv">codeframe_audit.csv</a>.</p>
<div class="card">{bars(codes, "", color="#5b6f9a")}</div>

<h2>4. Cleaned result: U.S. median salary by industry</h2>
<p class="note">USD-paid respondents, outliers excluded, industries with 300+ answers. Self-selected readers of one blog; not a population estimate.</p>
<div class="card">{bars(ind, "", color="#2f5d50")}</div>

<h2>Method, limits and source</h2>
<p class="note">Source: Ask a Manager Salary Survey 2021, republished by the TidyTuesday project (2021-05-18). Respondents self-selected; currency conversion uses approximate 2021 average rates and is not used for the headline numbers. The codeframe is rule-based and transparent; it is a first pass that a coder would extend. Code, tests and full method: <a href="https://github.com/titusrobinsonone/titusrobinsonone.github.io/blob/main/src/SALARY_QA_README.md">GitHub</a>. Built by Titus Robinson with AI-assisted implementation.</p>
</main></body></html>"""
    (DOCS / "salary-qa.html").write_text(page, encoding="utf-8")

    with zipfile.ZipFile(DOCS / "assets" / "salary-qa-project.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for f in ["src/salary_survey_qa.py", "src/make_salary_report.py", "src/SALARY_QA_README.md",
                  "src/tests/test_salary_survey_qa.py"]:
            z.write(ROOT / f, f)
        z.write(ASSETS / "quality_report.json", "out/quality_report.json")
        z.write(ASSETS / "codeframe_audit.csv", "out/codeframe_audit.csv")
    print("wrote docs/salary-qa.html and docs/assets/salary-qa/*")


if __name__ == "__main__":
    main()
