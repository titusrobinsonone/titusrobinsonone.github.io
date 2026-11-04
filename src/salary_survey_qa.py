"""Salary Survey Data-Quality & Open-Text Pipeline.

Real-world source: the 2021 Ask a Manager Salary Survey (26,000+ self-reported
responses, collected through a public Google Form; republished by the
TidyTuesday project, 2021-05-18). See src/SALARY_QA_README.md for the method.

What it does, in order:
  1. Schema check and source preservation (every input row ends up in exactly
     one of clean / rejected, with a reason).
  2. Standardization: salary text to numbers, free-text currencies, 300+
     country spellings, U.S. states, experience bands.
  3. Rule-based QA with severities: duplicates, impossible / implausible
     salaries, currency-country conflicts, experience contradictions,
     multi-state answers and statistical outliers.
  4. Privacy: regex PII redaction on free text, plus a quasi-identifier
     (k-anonymity) check on job title + city + industry + age band.
  5. Open-ended coding: a market-research style codeframe applied to the
     "additional context on income" answers (multi-code).
  6. Impact: how much cleaning changes the answer (raw vs clean salary stats).

Standard library only (Python 3.10+).
"""
from __future__ import annotations

import argparse
import csv
import difflib
import json
import math
import re
import statistics
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------- schema ----
COLUMNS = {
    "Timestamp": "timestamp",
    "How old are you?": "age_band",
    "Industry": "industry",
    "Job title": "job_title",
    "Additional context on job title": "job_context",
    "Annual salary": "salary_raw",
    "Other monetary comp": "other_comp_raw",
    "Currency": "currency_raw",
    "Currency - other": "currency_other",
    "Additional context on income": "income_context",
    "Country": "country_raw",
    "State": "state_raw",
    "City": "city",
    "Overall years of professional experience": "exp_overall",
    "Years of experience in field": "exp_field",
    "Highest level of education completed": "education",
    "Gender": "gender",
    "Race": "race",
}
FREE_TEXT = ["job_title", "job_context", "income_context", "city", "currency_other"]

EXPERIENCE_ORDER = {
    "1 year or less": 0, "2 - 4 years": 1, "5-7 years": 2, "8 - 10 years": 3,
    "11 - 20 years": 4, "21 - 30 years": 5, "31 - 40 years": 6, "41 years or more": 7,
}
# Lower bound in years of each band, used to check age against experience.
EXPERIENCE_MIN_YEARS = {0: 0, 1: 2, 2: 5, 3: 8, 4: 11, 5: 21, 6: 31, 7: 41}
AGE_MAX_YEARS = {"under 18": 17, "18-24": 24, "25-34": 34, "35-44": 44,
                 "45-54": 54, "55-64": 64, "65 or over": 120}

# ------------------------------------------------------------ countries ----
CANONICAL_COUNTRIES = [
    "United States", "Canada", "United Kingdom", "Australia", "New Zealand",
    "Germany", "Ireland", "France", "Netherlands", "Spain", "Sweden",
    "Switzerland", "Belgium", "Japan", "Denmark", "South Africa", "Finland",
    "Israel", "India", "Malaysia", "Norway", "Austria", "Italy", "Singapore",
    "Brazil", "Mexico", "China", "Hong Kong", "Poland", "Czech Republic",
    "Portugal", "Philippines", "Argentina", "Taiwan", "South Korea",
    "Luxembourg", "Greece", "Romania", "Colombia", "Kuwait", "Nigeria",
    "Kenya", "Pakistan", "Thailand", "Vietnam", "Indonesia", "Chile",
    "Puerto Rico", "United Arab Emirates", "Saudi Arabia", "Turkey",
    "Hungary", "Croatia", "Estonia", "Latvia", "Lithuania", "Slovenia",
    "Slovakia", "Serbia", "Ukraine", "Russia", "Bulgaria", "Iceland", "Malta",
    "Cyprus", "Egypt", "Qatar", "Bangladesh", "Sri Lanka", "Costa Rica",
    "Panama", "Peru", "Uruguay", "Ecuador", "Jamaica", "Bermuda", "Cayman Islands",
    "Ghana", "Trinidad and Tobago", "Rwanda", "Afghanistan", "Cambodia", "Eritrea",
    "Cuba", "Somalia", "Sierra Leone", "Bahamas", "Congo", "Uganda", "Morocco",
    "Zimbabwe", "Jordan", "Isle of Man", "Jersey", "Cote d'Ivoire",
]
COUNTRY_ALIASES = {
    "us": "United States", "usa": "United States", "u s": "United States",
    "u s a": "United States", "america": "United States",
    "united states of america": "United States", "the united states": "United States",
    "the us": "United States", "united state": "United States",
    "united stated": "United States", "unites states": "United States",
    "us of a": "United States", "united sates": "United States",
    "unitedstates": "United States", "united statws": "United States",
    "uk": "United Kingdom", "u k": "United Kingdom", "england": "United Kingdom",
    "scotland": "United Kingdom", "wales": "United Kingdom",
    "northern ireland": "United Kingdom", "great britain": "United Kingdom",
    "britain": "United Kingdom", "england uk": "United Kingdom",
    "united kingdom of great britain and northern ireland": "United Kingdom",
    "the netherlands": "Netherlands", "holland": "Netherlands",
    "nz": "New Zealand", "aotearoa new zealand": "New Zealand",
    "korea": "South Korea", "republic of korea": "South Korea",
    "uae": "United Arab Emirates", "czechia": "Czech Republic",
    "hong kong sar": "Hong Kong", "canadá": "Canada", "canda": "Canada",
    "canad": "Canada", "csnada": "Canada", "canadw": "Canada",
    "brasil": "Brazil", "méxico": "Mexico", "panamá": "Panama",
    "nederland": "Netherlands", "nl": "Netherlands", "danmark": "Denmark",
    "luxemburg": "Luxembourg", "mainland china": "China", "the bahamas": "Bahamas",
    "nz": "New Zealand", "us": "United States", "uk": "United Kingdom",
}
FLAG_EMOJI = {"\U0001F1FA\U0001F1F8": "United States", "\U0001F1E8\U0001F1E6": "Canada",
              "\U0001F1EC\U0001F1E7": "United Kingdom"}
US_STATES = {
    "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado",
    "Connecticut", "Delaware", "District of Columbia", "Florida", "Georgia",
    "Hawaii", "Idaho", "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky",
    "Louisiana", "Maine", "Maryland", "Massachusetts", "Michigan", "Minnesota",
    "Mississippi", "Missouri", "Montana", "Nebraska", "Nevada", "New Hampshire",
    "New Jersey", "New Mexico", "New York", "North Carolina", "North Dakota",
    "Ohio", "Oklahoma", "Oregon", "Pennsylvania", "Rhode Island",
    "South Carolina", "South Dakota", "Tennessee", "Texas", "Utah", "Vermont",
    "Virginia", "Washington", "West Virginia", "Wisconsin", "Wyoming",
}

# ------------------------------------------------------------ currencies ----
CURRENCY_ALIASES = {
    "usd": "USD", "us dollars": "USD", "us dollar": "USD", "american dollars": "USD",
    "cad": "CAD", "canadian": "CAD", "gbp": "GBP", "eur": "EUR", "euro": "EUR",
    "aud": "AUD", "nzd": "NZD", "chf": "CHF", "sek": "SEK", "jpy": "JPY",
    "zar": "ZAR", "hkd": "HKD", "nok": "NOK", "dkk": "DKK", "myr": "MYR",
    "inr": "INR", "brl": "BRL", "br$": "BRL", "sgd": "SGD", "czk": "CZK",
    "cny": "CNY", "rmb": "CNY", "ils": "ILS", "mxn": "MXN", "pln": "PLN",
    "krw": "KRW", "ntd": "TWD", "twd": "TWD", "kwd": "KWD", "php": "PHP",
    "peso argentino": "ARS", "ars": "ARS", "thb": "THB", "idr": "IDR",
}
# Approximate 2021 annual-average USD value of one unit. Used ONLY for the
# all-currency view; headline salary findings use U.S. respondents paid in USD.
USD_PER_UNIT_2021 = {
    "USD": 1.0, "CAD": 0.798, "GBP": 1.376, "EUR": 1.183, "AUD": 0.751,
    "NZD": 0.705, "CHF": 1.094, "SEK": 0.117, "JPY": 0.0091, "ZAR": 0.0677,
    "HKD": 0.1287, "NOK": 0.1165, "DKK": 0.1591, "MYR": 0.2413, "INR": 0.0135,
    "BRL": 0.1854, "SGD": 0.7442, "CZK": 0.0461, "CNY": 0.155, "ILS": 0.3096,
    "MXN": 0.0493, "PLN": 0.2591, "KRW": 0.000874, "TWD": 0.0359,
    "KWD": 3.31, "PHP": 0.0201, "ARS": 0.0105, "THB": 0.0313, "IDR": 0.0000701,
}
HOME_CURRENCY = {
    "United States": "USD", "Canada": "CAD", "United Kingdom": "GBP",
    "Australia": "AUD", "New Zealand": "NZD", "Switzerland": "CHF",
    "Sweden": "SEK", "Japan": "JPY", "South Africa": "ZAR", "Hong Kong": "HKD",
    "Germany": "EUR", "Ireland": "EUR", "France": "EUR", "Netherlands": "EUR",
    "Spain": "EUR", "Belgium": "EUR", "Finland": "EUR", "Austria": "EUR",
    "Italy": "EUR", "Portugal": "EUR", "Luxembourg": "EUR", "Greece": "EUR",
}

# ------------------------------------------------------------------- PII ----
PII_PATTERNS = {
    "EMAIL": re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    "PHONE": re.compile(r"(?<!\d)(?:\+?\d{1,2}[ .-]?)?\(?\d{3}\)?[ .-]\d{3}[ .-]\d{4}(?!\d)"),
    "SSN": re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)"),
    "URL": re.compile(r"https?://\S+|www\.\S+"),
    "HANDLE": re.compile(r"(?<![\w.])@[A-Za-z_]\w{2,}"),
}
QUASI_IDENTIFIERS = ["job_title_norm", "city_norm", "industry_norm", "age_band"]
K_THRESHOLD = 5

# ------------------------------------------------------------- codeframe ----
# Market-research style codeframe for "additional context on income".
# One answer can carry several codes. Patterns are deliberately readable.
CODEFRAME = {
    "Bonus / incentive": r"\bbonus|incentive|profit[- ]?shar|\bstipend",
    "Equity / stock": r"\bequity\b|\bstock|\brsus?\b|\bshares?\b|\boptions?\b|\bespp\b",
    "Commission / sales": r"commission|\bsales\b|\bquota\b",
    "Overtime / shift pay": r"overtime|\bot\b|shift diff|differential|on[- ]call|\bholiday pay",
    "Hourly / part-time / contract": r"hourly|\bper hour\b|an hour\b|/hr\b|/hour\b|part[- ]time|\bcontract(or|ing)?\s*(position|role|employee|worker|basis|job)?\b(?!\s*(ratification|negotiat))|freelanc|\b\d{1,3}\s*%\s*fte\b|self[- ]employ",
    "Hours / schedule": r"\bhours? (a|per) (week|day)|hrs?/(week|wk)|\b\d{2}(\.\d)?\s*hours\b|full[- ]time (is|for)|work(ing)? (through|over) lunch|\bexempt\b",
    "Side income / second job": r"second job|side (job|gig|hustle|business)|\bgig\b|adjunct|additional (job|course|class)|consult",
    "Benefits / pension": r"benefit|pension|superannuation|401k|401\(k\)|retirement|rrsp|health insurance|\bhsa\b|\bpto\b|vacation|tuition|loan repayment",
    "Raise / pay change": r"\braises?\b|promot|recent(ly)? (got|received)|pay cut|salary (increase|cut)|\bcola\b|merit (increase|raise)s?|step increase|furlough",
    "Public sector / union scale": r"\bunion\b|collective bargaining|government (entity|agency|employee|job|worker|position|salar)|\bwork(s|ing)? for (the |a )?(state|city|county|federal|government)|\bfederal\b|\bstate (employee|job|university|agency)|civil serv|pay (scale|grid|band)|\bgs[- ]?(\d|scale)|general schedule|public (sector|info)",
    "Tips / gratuity": r"\btips?\b|gratuit",
    "Underpaid / pay fairness": r"underpaid|under paid|below market|pay gap|not paid enough|undervalued",
    "Currency / location / remote": r"exchange rate|currency|cost of living|\bcol\b|remote|relocat|another country|\blocation\b",
}
_CODE_RE = {name: re.compile(pat, re.I) for name, pat in CODEFRAME.items()}
# "no overtime", "not eligible for bonus", "without benefits": the answer is
# ABOUT the topic but says it is absent. Those go to a separate "(none)" code.
_NEGATION = re.compile(r"\b(no|not|never|without|none|n't|nor)\b(\W+\w+){0,3}\W*$", re.I)


# ============================================================ functions =====
def norm_key(text: str) -> str:
    text = (text or "").strip().lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_money(text: str) -> float | None:
    """'55,000' -> 55000.0; '$72k' -> 72000.0; '' / junk -> None."""
    if text is None:
        return None
    s = str(text).strip().lower().replace(",", "").replace("$", "").replace("£", "").replace("€", "")
    s = s.replace(" ", "")
    if not s:
        return None
    mult = 1.0
    if s.endswith("k"):
        mult, s = 1000.0, s[:-1]
    try:
        value = float(s) * mult
    except ValueError:
        return None
    return value if math.isfinite(value) else None


def normalize_country(raw: str) -> tuple[str | None, str]:
    """Return (canonical country or None, method)."""
    for flag_chars, canon in FLAG_EMOJI.items():
        if flag_chars in (raw or ""):
            return canon, "flag_emoji"
    key = norm_key(raw)
    if not key:
        return None, "missing"
    if key in COUNTRY_ALIASES:
        return COUNTRY_ALIASES[key], "alias"
    for c in CANONICAL_COUNTRIES:
        if key == c.lower():
            return c, "exact"
    # Answers like "US, but remote" or "UK for U.S. company": take the
    # country mentioned FIRST, so the respondent's own location wins.
    found = []
    for alias, canon in COUNTRY_ALIASES.items():
        m = re.search(rf"\b{re.escape(alias)}\b", key)
        if m:
            found.append((m.start(), -len(alias), canon))
    for c in CANONICAL_COUNTRIES:
        m = re.search(rf"\b{re.escape(c.lower())}\b", key)
        if m:
            found.append((m.start(), -len(c), c))
    if found:
        return min(found)[2], "contains"
    state = next((st for st in US_STATES if key == st.lower()), None)
    if state:
        return "United States", "us_state_as_country"
    match = difflib.get_close_matches(key, [c.lower() for c in CANONICAL_COUNTRIES] + list(COUNTRY_ALIASES), n=1, cutoff=0.85)
    if match:
        m = match[0]
        return COUNTRY_ALIASES.get(m) or next(c for c in CANONICAL_COUNTRIES if c.lower() == m), "fuzzy"
    return None, "unresolved"


def resolve_currency(currency_raw: str, currency_other: str, country: str | None) -> tuple[str | None, str]:
    cur = (currency_raw or "").strip()
    if cur == "AUD/NZD":
        if country == "New Zealand":
            return "NZD", "split_by_country"
        if country == "Australia":
            return "AUD", "split_by_country"
        return "AUD", "split_default"
    if cur and cur != "Other":
        return cur, "listed"
    key = norm_key(currency_other)
    if key in CURRENCY_ALIASES:
        return CURRENCY_ALIASES[key], "other_text"
    if country in HOME_CURRENCY and key:
        return None, "other_unparseable"
    return None, "unresolved"


def redact_pii(text: str) -> tuple[str, Counter]:
    hits: Counter = Counter()
    out = text or ""
    for label, pattern in PII_PATTERNS.items():
        out, n = pattern.subn(f"[{label}]", out)
        if n:
            hits[label] += n
    return out, hits


def code_open_end(text: str) -> list[str]:
    """Multi-code one answer. A topic mentioned only in negated form
    ("no bonus") is coded "<topic> (none)" instead of the topic itself."""
    if not text or not text.strip():
        return []
    codes = []
    for name, rx in _CODE_RE.items():
        positive = negated = False
        for m in rx.finditer(text):
            if _NEGATION.search(text[max(0, m.start() - 40):m.start()]):
                negated = True
            else:
                positive = True
        if positive:
            codes.append(name)
        elif negated:
            codes.append(f"{name} (none)")
    return codes


def robust_z(values: list[float]) -> tuple[float, float]:
    """Median and MAD-based scale of log salaries."""
    med = statistics.median(values)
    mad = statistics.median(abs(v - med) for v in values) or 1e-9
    return med, 1.4826 * mad


def k_anonymity(rows: list[dict], keys: list[str]) -> Counter:
    return Counter(tuple(r[k] for k in keys) for r in rows)


def summarize(values: list[float]) -> dict:
    if not values:
        return {"n": 0}
    v = sorted(values)
    q = statistics.quantiles(v, n=4)
    return {"n": len(v), "mean": round(statistics.fmean(v)), "median": round(statistics.median(v)),
            "p25": round(q[0]), "p75": round(q[2]), "max": round(v[-1]), "min": round(v[0])}


# ============================================================== pipeline ====
def run(input_path: Path, output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    with input_path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        missing = [c for c in COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"schema check failed, missing columns: {missing}")
        raw_rows = [{COLUMNS[k]: (v or "").strip() for k, v in row.items() if k in COLUMNS} for row in reader]

    exceptions: list[dict] = []

    def flag(row: dict, rule: str, severity: str, field: str, value: str) -> None:
        exceptions.append({"row_id": row["row_id"], "rule": rule, "severity": severity,
                           "field": field, "value": str(value)[:120]})
        if severity == "reject":
            row["_reject"].append(rule)
        else:
            row["_warn"].append(rule)

    country_methods: Counter = Counter()
    pii_hits: Counter = Counter()
    pii_rows = 0

    for i, r in enumerate(raw_rows, start=2):  # row_id = line number in the source CSV
        r["row_id"] = i
        r["_reject"], r["_warn"] = [], []

        # --- standardize -------------------------------------------------
        r["country"], method = normalize_country(r["country_raw"])
        country_methods[method] += 1
        if r["country"] is None:
            flag(r, "country_unresolved", "warn", "country_raw", r["country_raw"])

        r["currency"], cur_method = resolve_currency(r["currency_raw"], r["currency_other"], r["country"])
        if r["currency"] is None:
            flag(r, "currency_unresolved", "reject", "currency_other", r["currency_other"] or r["currency_raw"])

        r["salary"] = parse_money(r["salary_raw"])
        r["other_comp"] = parse_money(r["other_comp_raw"]) if r["other_comp_raw"] else 0.0
        if r["salary"] is None:
            flag(r, "salary_unparseable", "reject", "salary_raw", r["salary_raw"])
        elif r["salary"] <= 0:
            flag(r, "salary_zero_or_negative", "reject", "salary_raw", r["salary_raw"])

        try:
            r["ts"] = datetime.strptime(r["timestamp"], "%m/%d/%Y %H:%M:%S")
        except ValueError:
            r["ts"] = None
            flag(r, "timestamp_unparseable", "warn", "timestamp", r["timestamp"])

        # --- consistency rules -------------------------------------------
        eo, ef = EXPERIENCE_ORDER.get(r["exp_overall"]), EXPERIENCE_ORDER.get(r["exp_field"])
        if eo is not None and ef is not None and ef > eo:
            flag(r, "field_exp_exceeds_overall", "warn", "exp_field", f"{r['exp_field']} > {r['exp_overall']}")
        age_max = AGE_MAX_YEARS.get(r["age_band"])
        if age_max is not None and eo is not None and EXPERIENCE_MIN_YEARS[eo] > age_max - 14:
            flag(r, "experience_exceeds_age", "warn", "exp_overall", f"{r['exp_overall']} at age {r['age_band']}")

        if r["country"] == "United States":
            states = [s.strip() for s in r["state_raw"].split(",") if s.strip()]
            if not states:
                flag(r, "us_state_missing", "warn", "state_raw", "")
            elif len(states) > 1:
                flag(r, "us_multiple_states", "warn", "state_raw", r["state_raw"])
            elif states[0] not in US_STATES:
                flag(r, "us_state_invalid", "warn", "state_raw", r["state_raw"])
        elif r["country"] and r["state_raw"]:
            flag(r, "state_given_outside_us", "warn", "state_raw", r["state_raw"])

        home = HOME_CURRENCY.get(r["country"] or "")
        if home and r["currency"] and r["currency"] != home and r["currency"] != "USD":
            flag(r, "currency_country_conflict", "warn", "currency", f"{r['currency']} in {r['country']}")
        elif home and home != "USD" and r["currency"] == "USD":
            flag(r, "usd_outside_us", "warn", "currency", f"USD in {r['country']}")

        # --- salary plausibility (annual, in the stated currency) --------
        if r["salary"] and r["salary"] > 0 and r["currency"] in USD_PER_UNIT_2021:
            r["salary_usd"] = r["salary"] * USD_PER_UNIT_2021[r["currency"]]
            if r["salary_usd"] < 1_000:
                flag(r, "salary_likely_in_thousands_or_hourly", "reject", "salary_raw", r["salary_raw"])
            elif r["salary_usd"] < 10_000:
                flag(r, "salary_below_10k_usd", "warn", "salary_raw", r["salary_raw"])
            elif r["salary_usd"] > 5_000_000:
                flag(r, "salary_above_5m_usd", "reject", "salary_raw", r["salary_raw"])
        else:
            r["salary_usd"] = None

        # --- normalized keys for duplicates / privacy ---------------------
        r["job_title_norm"] = norm_key(r["job_title"])
        r["city_norm"] = norm_key(r["city"])
        r["industry_norm"] = norm_key(r["industry"])

        # --- PII redaction on free text ---------------------------------
        row_hit = False
        for f in FREE_TEXT:
            red, hits = redact_pii(r[f])
            if hits:
                row_hit = True
                pii_hits.update(hits)
                flag(r, "pii_redacted", "warn", f, ", ".join(sorted(hits)))
            r[f + "_redacted"] = red
        pii_rows += row_hit

    # --- duplicates (all answers identical, timestamp ignored) -----------
    seen: dict[tuple, int] = {}
    answer_keys = [c for c in COLUMNS.values() if c != "timestamp"]
    for r in raw_rows:
        sig = tuple(norm_key(r[k]) for k in answer_keys)
        if sig in seen:
            flag(r, "duplicate_submission", "reject", "row", f"same answers as row {seen[sig]}")
        else:
            seen[sig] = r["row_id"]

    # --- statistical outliers within currency (log scale, MAD) ----------
    by_cur: dict[str, list[dict]] = defaultdict(list)
    for r in raw_rows:
        if not r["_reject"] and r["salary_usd"]:
            by_cur[r["currency"]].append(r)
    for cur, group in by_cur.items():
        if len(group) < 30:
            continue
        logs = [math.log(g["salary"]) for g in group]
        med, scale = robust_z(logs)
        for g, lv in zip(group, logs):
            z = (lv - med) / scale
            if abs(z) > 4:
                flag(g, "salary_robust_outlier", "warn", "salary_raw", f"{g['salary_raw']} {cur} (z={z:.1f})")

    clean = [r for r in raw_rows if not r["_reject"]]
    rejected = [r for r in raw_rows if r["_reject"]]

    # --- privacy: quasi-identifier uniqueness on clean rows --------------
    groups = k_anonymity(clean, QUASI_IDENTIFIERS)
    at_risk = sum(n for n in groups.values() if n < K_THRESHOLD)
    unique = sum(1 for n in groups.values() if n == 1)
    # Generalized release: drop city, keep job title + industry + age band.
    gen_keys = ["job_title_norm", "industry_norm", "age_band"]
    gen_groups = k_anonymity(clean, gen_keys)
    gen_at_risk = sum(n for n in gen_groups.values() if n < K_THRESHOLD)
    # Coarser: industry + age band + country.
    coarse_keys = ["industry_norm", "age_band", "country"]
    coarse_groups = k_anonymity(clean, coarse_keys)
    coarse_at_risk = sum(n for n in coarse_groups.values() if n < K_THRESHOLD)

    # --- open-ended coding ----------------------------------------------
    answered = [r for r in clean if r["income_context_redacted"].strip()]
    code_counts: Counter = Counter()
    coded_rows = []
    uncoded = 0
    for r in answered:
        codes = code_open_end(r["income_context_redacted"])
        code_counts.update(codes)
        if not codes:
            uncoded += 1
        coded_rows.append({"row_id": r["row_id"], "codes": "; ".join(codes) or "Uncoded",
                           "text": r["income_context_redacted"][:300]})

    # --- impact of cleaning on the answer ---------------------------------
    # Same population before and after: everyone who said they are paid in USD.
    us_raw = [parse_money(r["salary_raw"]) for r in raw_rows if r["currency_raw"] == "USD"]
    us_raw = [v for v in us_raw if v is not None]
    us_clean = [r["salary"] for r in clean if r["currency"] == "USD"]
    us_clean_no_outliers = [r["salary"] for r in clean if r["currency"] == "USD"
                            and "salary_robust_outlier" not in r["_warn"]]
    by_industry: dict[str, list[float]] = defaultdict(list)
    for r in clean:
        if r["currency"] == "USD" and r["country"] == "United States" and "salary_robust_outlier" not in r["_warn"]:
            by_industry[r["industry"].strip() or "(blank)"].append(r["salary"])
    top_industries = sorted(((k, summarize(v)) for k, v in by_industry.items() if len(v) >= 300),
                            key=lambda kv: -kv[1]["median"])

    rule_counts = Counter((e["rule"], e["severity"]) for e in exceptions)
    report = {
        "source": "Ask a Manager Salary Survey 2021 (via TidyTuesday 2021-05-18)",
        "rows_in": len(raw_rows),
        "rows_clean": len(clean),
        "rows_rejected": len(rejected),
        "rows_with_warnings": sum(1 for r in clean if r["_warn"]),
        "reconciles": len(clean) + len(rejected) == len(raw_rows),
        "rules": [{"rule": k[0], "severity": k[1], "rows": v} for k, v in rule_counts.most_common()],
        "country": {
            "distinct_raw_spellings": len({r["country_raw"].strip().lower() for r in raw_rows}),
            "distinct_after": len({r["country"] for r in raw_rows if r["country"]}),
            "methods": dict(country_methods),
        },
        "industry_distinct_raw": len({r["industry"].strip().lower() for r in raw_rows}),
        "privacy": {
            "pii_hits": dict(pii_hits), "rows_with_pii": pii_rows,
            "k_threshold": K_THRESHOLD,
            "full_release_rows_below_k": at_risk,
            "full_release_unique_rows": unique,
            "full_release_pct_below_k": round(100 * at_risk / max(len(clean), 1), 1),
            "drop_city_rows_below_k": gen_at_risk,
            "drop_city_pct_below_k": round(100 * gen_at_risk / max(len(clean), 1), 1),
            "coarse_rows_below_k": coarse_at_risk,
            "coarse_pct_below_k": round(100 * coarse_at_risk / max(len(clean), 1), 1),
        },
        "open_ends": {
            "answered": len(answered), "coded": len(answered) - uncoded, "uncoded": uncoded,
            "coverage_pct": round(100 * (len(answered) - uncoded) / max(len(answered), 1), 1),
            "codes": dict(code_counts.most_common()),
        },
        "impact_us_usd": {
            "raw": summarize(us_raw), "clean": summarize(us_clean),
            "clean_excl_outliers": summarize(us_clean_no_outliers),
        },
        "us_industry_medians_n300": [{"industry": k, **v} for k, v in top_industries],
    }

    # --- write outputs ---------------------------------------------------
    clean_fields = ["row_id", "timestamp", "age_band", "industry", "job_title", "job_context_redacted",
                    "salary", "other_comp", "currency", "salary_usd", "income_context_redacted",
                    "country", "state_raw", "city", "exp_overall", "exp_field", "education", "gender", "race", "warnings"]
    with (output_dir / "clean.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=clean_fields, extrasaction="ignore")
        w.writeheader()
        for r in clean:
            w.writerow({**r, "warnings": "; ".join(sorted(set(r["_warn"]))),
                        "salary_usd": round(r["salary_usd"], 2) if r["salary_usd"] else ""})
    with (output_dir / "rejected.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["row_id", "reasons", "salary_raw", "currency_raw", "currency_other", "country_raw"], extrasaction="ignore")
        w.writeheader()
        for r in rejected:
            w.writerow({**r, "reasons": "; ".join(sorted(set(r["_reject"])))})
    with (output_dir / "exceptions.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["row_id", "rule", "severity", "field", "value"])
        w.writeheader()
        w.writerows(exceptions)
    with (output_dir / "open_end_codes.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["row_id", "codes", "text"])
        w.writeheader()
        w.writerows(coded_rows)
    (output_dir / "quality_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--input", type=Path, default=Path("data/ask_a_manager_2021.csv"))
    ap.add_argument("--output", type=Path, default=Path("out/salary_qa"))
    args = ap.parse_args()
    report = run(args.input, args.output)
    p = report["privacy"]
    print(f"rows in {report['rows_in']:,} | clean {report['rows_clean']:,} | rejected {report['rows_rejected']:,} | reconciles {report['reconciles']}")
    print(f"countries: {report['country']['distinct_raw_spellings']} spellings -> {report['country']['distinct_after']}")
    print(f"privacy: {p['full_release_pct_below_k']}% of rows below k={p['k_threshold']} on title+city+industry+age; "
          f"{p['drop_city_pct_below_k']}% after dropping city; {p['coarse_pct_below_k']}% at industry+age+country")
    o = report["open_ends"]
    print(f"open-ends: {o['answered']:,} answers, {o['coverage_pct']}% coded")
    i = report["impact_us_usd"]
    print(f"US/USD mean: raw {i['raw']['mean']:,} -> clean {i['clean_excl_outliers']['mean']:,} (median {i['clean_excl_outliers']['median']:,})")


if __name__ == "__main__":
    main()
