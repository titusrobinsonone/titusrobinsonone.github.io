"""Demand & Inventory Lab — Titus Robinson's independent portfolio.

Standard-library, chronological demand forecasting and lost-sales inventory
simulation. All bundled demand is synthetic; no claimed workplace savings.
Run: python src/inventory_lab.py --output docs/assets
"""
from __future__ import annotations
import argparse
import csv
import json
import math
import random
import statistics
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

SEED = 20261028
WARMUP = 84
FIELDS = ['date', 'sku', 'demand', 'unit_cost', 'unit_margin']


def generate_demo(seed=SEED, days=224, skus=12):
    rng = random.Random(seed)
    result = []
    weekly = [0.82, 0.90, 0.96, 1.02, 1.22, 1.35, 0.73]
    for k in range(skus):
        base = 12 + k * 4
        for t in range(days):
            day = date(2026, 1, 1) + timedelta(days=t)
            promo = 1.45 if k % 3 == 0 and 126 <= t < 147 else 1
            mean = base * weekly[day.weekday()] * (1 + t * (0.001 if k % 2 else 0.0003)) * promo
            demand = max(0, round(rng.gauss(mean, mean * 0.22)))
            if k % 5 == 0 and rng.random() < 0.15:
                demand = 0
            result.append(dict(date=day.isoformat(), sku=f'SKU-{k+1:02}', demand=demand,
                               unit_cost=round(8 + k * 2.25, 2), unit_margin=round(4 + k * 1.2, 2)))
    return result


def validate(rows):
    grouped = defaultdict(list)
    seen = set()
    for raw in rows:
        d = date.fromisoformat(raw['date'])
        sku = str(raw['sku']).strip()
        units = float(raw['demand'])
        cost, margin = float(raw['unit_cost']), float(raw['unit_margin'])
        if not sku or not units.is_integer() or units < 0 or not all(math.isfinite(v) and v > 0 for v in (cost, margin)):
            raise ValueError('Demand must be a nonnegative integer; SKU, cost and margin must be valid.')
        if (sku, d) in seen:
            raise ValueError(f'Duplicate SKU/date: {sku} {d}')
        seen.add((sku, d))
        grouped[sku].append(dict(date=d.isoformat(), sku=sku, demand=int(units), unit_cost=cost, unit_margin=margin))
    if not grouped:
        raise ValueError('No demand rows.')
    calendar = None
    for sku, group in grouped.items():
        group.sort(key=lambda r: r['date'])
        dates = [date.fromisoformat(r['date']) for r in group]
        if len(dates) <= WARMUP or any((b-a).days != 1 for a, b in zip(dates, dates[1:])):
            raise ValueError('Each SKU needs more than 84 days and a continuous daily calendar.')
        if calendar is not None and dates != calendar:
            raise ValueError('All SKUs must use the same calendar.')
        if len({(r['unit_cost'], r['unit_margin']) for r in group}) != 1:
            raise ValueError('This simulation requires constant unit cost and margin per SKU.')
        calendar = dates
    return dict(sorted(grouped.items()))


def forecast(history, future_weekday, policy):
    """Only history passed by the caller is visible to this forecast."""
    if not history:
        raise ValueError('Forecast needs history.')
    recent = history[-28:]
    if policy == 'rolling':
        return statistics.mean(r['demand'] for r in recent)
    if policy != 'seasonal':
        raise ValueError('Unknown forecasting policy.')
    weekday = [r['demand'] for r in history[-56:] if date.fromisoformat(r['date']).weekday() == future_weekday]
    level = statistics.mean(weekday or [r['demand'] for r in recent])
    prior = history[-56:-28]
    trend = statistics.mean(r['demand'] for r in recent) / max(1, statistics.mean(r['demand'] for r in prior)) if prior else 1
    return level * min(1.25, max(0.8, trend))


def simulate_sku(rows, policy, lead_days, buffer_z, warmup=WARMUP):
    if lead_days < 1 or buffer_z < 0 or warmup >= len(rows):
        raise ValueError('Invalid simulation settings.')
    history = rows[:warmup]
    first = date.fromisoformat(rows[warmup]['date'])
    initial = math.ceil(sum(forecast(history, (first + timedelta(days=i)).weekday(), policy) for i in range(lead_days+1))
                        + buffer_z * statistics.pstdev(r['demand'] for r in history[-28:]) * math.sqrt(lead_days+1))
    stock = initial
    pending = []
    trace = []
    abs_error = total_demand = fulfilled = units_held = lost_margin = 0
    for t in range(warmup, len(rows)):
        row = rows[t]
        today = date.fromisoformat(row['date'])
        before = stock
        arrivals = sum(q for due, q in pending if due == t)
        pending = [(due, q) for due, q in pending if due > t]
        stock += arrivals
        prediction = forecast(rows[:t], today.weekday(), policy)
        demand = row['demand']
        sold = min(stock, demand)
        stock -= sold
        total_demand += demand
        fulfilled += sold
        abs_error += abs(prediction-demand)
        units_held += stock
        lost_margin += (demand-sold) * row['unit_margin']
        # Review at day end: this day's observations are now available.
        known = rows[:t+1]
        target = math.ceil(sum(forecast(known, (today+timedelta(days=i)).weekday(), policy) for i in range(1, lead_days+2))
                           + buffer_z * statistics.pstdev(r['demand'] for r in known[-28:]) * math.sqrt(lead_days+1))
        position = stock + sum(q for _, q in pending)
        order = max(0, target-position)
        if order:
            pending.append((t+lead_days, order))
        trace.append(dict(date=row['date'], demand=demand, forecast=round(prediction, 2),
                          opening=before, arrivals=arrivals, sold=sold, lost=demand-sold,
                          closing=stock, ordered=order))
    days = len(trace)
    average_value = units_held / days * rows[0]['unit_cost']
    holding_cost = units_held * rows[0]['unit_cost'] * 0.25 / 365
    return dict(sku=rows[0]['sku'], demand=total_demand, fulfilled=fulfilled,
                lost=total_demand-fulfilled, fillRate=fulfilled/total_demand if total_demand else 1,
                averageInventoryValue=round(average_value, 2), holdingCost=round(holding_cost, 2),
                lostMargin=round(lost_margin, 2), totalCost=round(holding_cost+lost_margin, 2),
                absError=round(abs_error, 3), wape=abs_error/total_demand if total_demand else None,
                initialStock=initial, trace=trace)


def build(rows):
    grouped = validate(rows)
    scenarios = []
    for policy in ('rolling', 'seasonal'):
        for lead in (3, 7, 14):
            for buffer in (0, 1, 1.645, 2.326):
                results = [simulate_sku(r, policy, lead, buffer) for r in grouped.values()]
                demand = sum(r['demand'] for r in results)
                fulfilled = sum(r['fulfilled'] for r in results)
                scenarios.append(dict(id=f'{policy}-{lead}-{buffer}', policy=policy, leadDays=lead, buffer=buffer,
                    fillRate=fulfilled/demand, demand=demand, fulfilled=fulfilled, lost=demand-fulfilled,
                    averageInventoryValue=round(sum(r['averageInventoryValue'] for r in results), 2),
                    holdingCost=round(sum(r['holdingCost'] for r in results), 2),
                    lostMargin=round(sum(r['lostMargin'] for r in results), 2),
                    totalCost=round(sum(r['totalCost'] for r in results), 2),
                    wape=sum(r['absError'] for r in results)/demand, skus=results))
    first = next(iter(grouped.values()))
    return dict(meta=dict(owner='Titus Robinson', synthetic=True, seed=SEED, warmupDays=WARMUP,
                         testDays=len(first)-WARMUP, skuCount=len(grouped),
                         testStart=first[WARMUP]['date'], testEnd=first[-1]['date'],
                         annualHoldingRate=0.25, currency='USD', scenarioCount=len(scenarios)), scenarios=scenarios)


def export(output, rows=None):
    output = Path(output); output.mkdir(parents=True, exist_ok=True)
    generated = rows is None
    rows = generate_demo() if generated else rows
    result = build(rows)
    result['meta'].update(dataOrigin='generated_synthetic' if generated else 'user_supplied', synthetic=True if generated else None, seed=SEED if generated else None)
    with (output/'inventory-demand.csv').open('w', newline='') as f:
        writer=csv.DictWriter(f, fieldnames=FIELDS); writer.writeheader(); writer.writerows(rows)
    (output/'inventory-data.json').write_text(json.dumps(result, separators=(',', ':'), allow_nan=False))
    return result


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, help='Optional CSV with date,sku,demand,unit_cost,unit_margin')
    parser.add_argument('--output', type=Path, default=Path('out'))
    args=parser.parse_args()
    if args.input and args.input.resolve()==(args.output/'inventory-demand.csv').resolve():
        parser.error('Choose an output directory that does not overwrite the source CSV.')
    rows=list(csv.DictReader(args.input.open())) if args.input else None
    result=export(args.output, rows)
    print(json.dumps(result['meta'], indent=2))
    print('Saved 24 explicit scenarios. Evaluate trade-offs; no policy is selected on the held-out sample.')
