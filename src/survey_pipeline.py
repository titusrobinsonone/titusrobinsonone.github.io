#!/usr/bin/env python3
"""Reproducible survey validation and BI export. Python standard library only.

The --generate-demo dataset is entirely synthetic and contains no client data.
See README.md for KPI definitions, validation rules and the demonstration scope.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import random
import statistics
import sys
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

SEED = 20261028
PERIOD_START = date(2026, 8, 3)
MARKETS = ("United States", "United Kingdom", "Canada", "Germany", "France", "Australia")
CHANNELS = ("Web", "Mobile", "Email")
FIELDS = (
    "response_id", "market", "channel", "submitted_at", "completed",
    "duration_seconds", "satisfaction_score",
)
OUTPUTS = (
    "survey_clean.csv", "survey_rejected.csv", "survey_summary.csv",
    "portfolio-data.json", "pipeline-run.txt",
)
REASON_LABELS = {
    "missing_id": "Missing response ID",
    "duplicate_id": "Duplicate response ID",
    "invalid_market": "Unrecognized market",
    "invalid_channel": "Unrecognized channel",
    "invalid_date": "Invalid submission date",
    "invalid_completed": "Invalid completion flag",
    "invalid_duration": "Invalid duration (outside 15–1,800 seconds)",
    "invalid_satisfaction_score": "Missing or invalid satisfaction score",
}


class PipelineError(ValueError):
    """A source or output problem the CLI can explain without a traceback."""


def generate_demo(seed: int = SEED) -> list[dict[str, str]]:
    """Generate 7,200 valid responses plus exactly 100 intentional defects."""
    rng = random.Random(seed)
    completion = (.91, .88, .90, .86, .87, .89)
    csat = (.79, .74, .83, .72, .70, .81)
    duration = (170, 180, 160, 200, 205, 175)
    rows: list[dict[str, str]] = []
    for week in range(12):
        for market_index, market in enumerate(MARKETS):
            for _ in range(100):
                channel = rng.choices(CHANNELS, weights=(.45, .35, .20), k=1)[0]
                channel_effect = {"Web": 0, "Mobile": -.035, "Email": .015}[channel]
                probability = completion[market_index] + channel_effect + .0025 * (week - 5.5)
                is_complete = rng.random() < probability
                score = ""
                if is_complete:
                    positive = csat[market_index] + {"Web": .01, "Mobile": -.04, "Email": .025}[channel] + .001 * (week - 5.5)
                    score = str(rng.choices((4, 5), weights=(.55, .45), k=1)[0] if rng.random() < positive else rng.choices((1, 2, 3), weights=(.12, .28, .60), k=1)[0])
                seconds = round(rng.gauss(duration[market_index] + (18 if channel == "Mobile" else 0), 37))
                seconds = max(90, min(360, seconds))
                day = PERIOD_START + timedelta(weeks=week, days=rng.randrange(7))
                submitted = datetime(day.year, day.month, day.day, rng.randrange(8, 23), rng.randrange(60), tzinfo=timezone.utc)
                rows.append({
                    "response_id": f"SYN-{len(rows) + 1:06d}",
                    "market": market, "channel": channel,
                    "submitted_at": submitted.isoformat().replace("+00:00", "Z"),
                    "completed": str(is_complete).lower(),
                    "duration_seconds": str(seconds), "satisfaction_score": score,
                })

    # Appending defects leaves the original valid row first for the duplicate rule.
    rows.extend(dict(row) for row in rows[:48])
    for i, row in enumerate(rows[100:124], 1):
        rows.append(dict(row, response_id=""))
    complete_examples = [row for row in rows[:7200] if row["completed"] == "true"]
    for i, row in enumerate(complete_examples[:18], 1):
        rows.append(dict(row, response_id=f"SYN-ERR-SCORE-{i:03d}", satisfaction_score="9"))
    for i, row in enumerate(rows[200:210], 1):
        rows.append(dict(row, response_id=f"SYN-ERR-DURATION-{i:03d}", duration_seconds="-5"))
    return rows


def write_csv(path: Path, fields: tuple[str, ...] | list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def read_source(path: Path) -> tuple[list[dict[str, str]], str]:
    try:
        source_bytes = path.read_bytes()
    except OSError as exc:
        raise PipelineError(f"Cannot read input CSV: {exc.strerror or exc}") from exc
    try:
        decoded = source_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise PipelineError("Input CSV must use UTF-8 text encoding.") from exc
    try:
        reader = csv.DictReader(io.StringIO(decoded), strict=True)
        header = reader.fieldnames
        if not header:
            raise PipelineError("Input CSV is empty; include the required header and at least one response.")
        if len(header) != len(set(header)):
            raise PipelineError("Input CSV has duplicate column names.")
        missing = sorted(set(FIELDS) - set(header))
        if missing:
            raise PipelineError("Input CSV is missing required columns: " + ", ".join(missing))
        rows = list(reader)
    except csv.Error as exc:
        raise PipelineError(f"Cannot parse input CSV: {exc}") from exc
    if not rows:
        raise PipelineError("Input CSV contains a header but no response rows.")
    return rows, hashlib.sha256(source_bytes).hexdigest()


def validate_rows(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """First valid row for an ID wins. Each rejected row has one primary reason."""
    clean: list[dict] = []
    rejected: list[dict] = []
    valid_ids: set[str] = set()
    for source_row, row in enumerate(rows, 2):
        normalized = {field: str(row.get(field) or "").strip() for field in FIELDS}
        identifier = normalized["response_id"]
        reason = None
        day = None
        is_complete = None
        seconds = None
        score = None
        if not identifier:
            reason = "missing_id"
        elif identifier in valid_ids:
            reason = "duplicate_id"
        elif normalized["market"] not in MARKETS:
            reason = "invalid_market"
        elif normalized["channel"] not in CHANNELS:
            reason = "invalid_channel"
        if reason is None:
            try:
                submitted = datetime.fromisoformat(normalized["submitted_at"].replace("Z", "+00:00"))
                if submitted.tzinfo is not None:
                    submitted = submitted.astimezone(timezone.utc)
                day = submitted.date()
            except ValueError:
                reason = "invalid_date"
        if reason is None:
            flag = normalized["completed"].lower()
            if flag not in ("true", "false", "1", "0"):
                reason = "invalid_completed"
            else:
                is_complete = flag in ("true", "1")
        if reason is None:
            try:
                seconds = int(normalized["duration_seconds"])
                if not 15 <= seconds <= 1800:
                    reason = "invalid_duration"
            except ValueError:
                reason = "invalid_duration"
        if reason is None:
            raw_score = normalized["satisfaction_score"]
            if raw_score:
                try:
                    score = int(raw_score)
                    if score not in (1, 2, 3, 4, 5):
                        reason = "invalid_satisfaction_score"
                except ValueError:
                    reason = "invalid_satisfaction_score"
            elif is_complete:
                reason = "invalid_satisfaction_score"
        if reason is not None:
            rejected.append(dict(normalized, source_row=source_row, reason=reason))
            continue
        valid_ids.add(identifier)
        clean.append({
            "id": identifier, "market": normalized["market"], "channel": normalized["channel"],
            "date": day.isoformat(), "week": (day - timedelta(days=day.weekday())).isoformat(),
            "completed": is_complete, "duration": seconds, "score": score,
        })
    return clean, rejected


def summarize(rows: list[dict]) -> dict:
    completed = [row for row in rows if row["completed"]]
    satisfied = sum(row["score"] >= 4 for row in completed)
    return {
        "responses": len(rows), "completed": len(completed),
        "completionRate": round(len(completed) / len(rows) * 100, 2) if rows else 0,
        "csat": round(satisfied / len(completed) * 100, 2) if completed else 0,
        "medianDuration": statistics.median(row["duration"] for row in completed) if completed else 0,
    }


def grouped(rows: list[dict], key: str, values: tuple[str, ...] | list[str]) -> list[dict]:
    return [{key: value, **summarize([row for row in rows if row[key] == value])} for value in values]


def run_pipeline(input_path: Path, output_dir: Path, *, synthetic_seed: int | None = None) -> dict:
    raw, source_hash = read_source(input_path)
    if input_path.resolve() in {(output_dir / name).resolve() for name in OUTPUTS}:
        raise PipelineError("Choose another output directory: this one would overwrite the input file.")
    clean, rejected = validate_rows(raw)
    if len(raw) != len(clean) + len(rejected):
        raise RuntimeError("Row reconciliation failed.")
    summary = summarize(clean)
    markets = grouped(clean, "market", MARKETS)
    weeks = sorted({row["week"] for row in clean})
    weekly = grouped(clean, "week", weeks)
    channels = grouped(clean, "channel", CHANNELS)
    quality_counts = Counter(row["reason"] for row in rejected)
    quality = [{"reason": reason, "label": REASON_LABELS[reason], "count": count}
               for reason, count in sorted(quality_counts.items(), key=lambda item: (-item[1], item[0]))]
    dates = sorted(row["date"] for row in clean)
    files = [*OUTPUTS]
    if synthetic_seed is not None:
        files.insert(0, "survey_raw.csv")
    data = {
        "meta": {
            "label": "Synthetic portfolio demonstration" if synthetic_seed is not None else "Supplied CSV analysis",
            "inputRows": len(raw), "cleanRows": len(clean), "rejectedRows": len(rejected),
            "seed": synthetic_seed, "periodStart": dates[0] if dates else None,
            "periodEnd": dates[-1] if dates else None, "inputSha256": source_hash,
            "quality": quality, "files": files,
        },
        "rows": clean, "summary": summary, "markets": markets,
        "weekly": weekly, "channels": channels,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    exported_clean = [{
        "response_id": row["id"], "market": row["market"], "channel": row["channel"],
        "submitted_at": row["date"], "completed": str(row["completed"]).lower(),
        "duration_seconds": row["duration"],
        "satisfaction_score": row["score"] if row["score"] is not None else "",
        "week": row["week"],
    } for row in clean]
    write_csv(output_dir / "survey_clean.csv", [*FIELDS, "week"], exported_clean)
    write_csv(output_dir / "survey_rejected.csv", [*FIELDS, "source_row", "reason"], rejected)
    exported_summary = [{
        "market": item["market"], "responses": item["responses"], "completed": item["completed"],
        "completion_rate_pct": item["completionRate"], "csat_pct": item["csat"],
        "median_duration_seconds": item["medianDuration"],
    } for item in markets]
    write_csv(output_dir / "survey_summary.csv", [
        "market", "responses", "completed", "completion_rate_pct", "csat_pct", "median_duration_seconds",
    ], exported_summary)
    (output_dir / "portfolio-data.json").write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    lines = [
        "SURVEY QUALITY → BI EXPORT",
        "Synthetic portfolio demonstration" if synthetic_seed is not None else "Supplied CSV analysis",
        f"[1/4] Loaded {len(raw):,} rows from {input_path.name}",
        f"[2/4] Validated {len(clean):,} usable rows; isolated {len(rejected):,} flagged rows",
    ]
    lines.extend(f"      {item['count']:>3}  {item['label']}" for item in quality)
    lines.extend([
        f"[3/4] Aggregated {len(markets)} markets, {len(weeks)} weeks and {len(channels)} channels",
        "[4/4] Exported clean CSV, rejected CSV, market summary and dashboard JSON",
        f"RECONCILED: {len(raw):,} input = {len(clean):,} clean + {len(rejected):,} flagged",
        f"COMPLETION: {summary['completionRate']:.2f}%  |  CSAT: {summary['csat']:.2f}%",
        f"MEDIAN COMPLETION TIME: {summary['medianDuration']:g} seconds",
        f"INPUT SHA-256: {source_hash}",
        "SUCCESS: source preserved; outputs ready for analysis",
    ])
    log = "\n".join(lines) + "\n"
    (output_dir / "pipeline-run.txt").write_text(log, encoding="utf-8")
    print(log, end="")
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--generate-demo", action="store_true", help="Create a fully synthetic, seeded 7,300-row input CSV")
    source.add_argument("--input", type=Path, help="An existing UTF-8 survey CSV")
    parser.add_argument("--output", type=Path, required=True, help="Directory for analysis outputs")
    parser.add_argument("--seed", type=int, default=SEED, help="Synthetic generation seed (default: 20261028)")
    args = parser.parse_args(argv)
    try:
        input_path = args.input
        if args.generate_demo:
            args.output.mkdir(parents=True, exist_ok=True)
            input_path = args.output / "survey_raw.csv"
            write_csv(input_path, FIELDS, generate_demo(args.seed))
        run_pipeline(input_path, args.output, synthetic_seed=args.seed if args.generate_demo else None)
    except (PipelineError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
