"""Subscription Revenue Forensics — Titus Robinson's independent portfolio.

Builds an auditable monthly recurring revenue bridge with SQLite window
functions. Bundled events are synthetic contract changes, not real revenue.
Run: python src/revenue_forensics.py --output docs/assets
"""
from __future__ import annotations
import argparse
import csv
import json
import random
import re
import sqlite3
from collections import Counter
from pathlib import Path

SEED=20261028
FIELDS=['event_id','customer_id','effective_month','mrr_cents','segment','sequence']


def month_range(start, end):
    y,m=map(int,start.split('-')); result=[]
    while f'{y:04}-{m:02}' <= end:
        result.append(f'{y:04}-{m:02}'); m+=1
        if m==13: y+=1; m=1
    return result


def generate_demo(seed=SEED, customers=360):
    rng=random.Random(seed); months=month_range('2025-01','2026-09'); events=[]
    for i in range(customers):
        start=rng.randrange(15); segment='SMB' if i%4 else 'Mid-market'
        current=0; plan=rng.choice([2900,7900,14900] if segment=='SMB' else [29900,59900,99900])
        for j in range(start,len(months)):
            change=False
            if j==start: current=plan; change=True
            elif current==0:
                if rng.random()<0.12: current=plan; change=True
            else:
                draw=rng.random()
                if draw<0.035: current=0; change=True
                elif draw<0.095: current+=rng.choice([1000,2500,5000]); change=True
                elif draw<0.13: current=max(1000,current-1500); change=True
            if change:
                events.append(dict(event_id=f'EVT-{len(events)+1:05}',customer_id=f'ACCT-{i+1:04}',
                    effective_month=months[j],mrr_cents=current,segment=segment,sequence=len(events)+1))
    events += [dict(r) for r in events[:15]]
    for i in range(4): events.append(dict(event_id=f'BAD-{i}',customer_id='ACCT-0001',effective_month='2026-09',mrr_cents=-500,segment='Mid-market',sequence=90000+i))
    for i in range(3): events.append(dict(event_id=f'MISSING-{i}',customer_id='',effective_month='2026-09',mrr_cents=7900,segment='SMB',sequence=91000+i))
    return events


def validate(rows):
    valid=[]; rejected=[]; seen=set(); segments={}; order_keys=set()
    for raw in rows:
        reason=None; row=dict(raw)
        try:
            if not str(row.get('event_id','')).strip() or not str(row.get('customer_id','')).strip(): reason='missing_identifier'
            elif row['event_id'] in seen: reason='duplicate_event_id'
            elif not re.fullmatch(r'20\d\d-(0[1-9]|1[0-2])',row['effective_month']): reason='invalid_month'
            elif not re.fullmatch(r'\d+',str(row['mrr_cents'])): reason='invalid_mrr'
            elif row['segment'] not in ('SMB','Mid-market'): reason='invalid_segment'
            elif not re.fullmatch(r'\d+',str(row['sequence'])): reason='invalid_sequence'
            elif row['customer_id'] in segments and segments[row['customer_id']]!=row['segment']: reason='segment_changed'
            elif (row['customer_id'],row['effective_month'],int(row['sequence'])) in order_keys: reason='ambiguous_sequence'
        except (KeyError, TypeError, ValueError): reason='invalid_schema'
        if reason:
            rejected.append({**row,'reason':reason}); continue
        row['mrr_cents']=int(row['mrr_cents']); row['sequence']=int(row['sequence'])
        seen.add(row['event_id']); segments[row['customer_id']]=row['segment']
        order_keys.add((row['customer_id'],row['effective_month'],row['sequence']))
        valid.append(row)
    if not valid: raise ValueError('No valid contract events.')
    return valid,rejected


def model(rows, end_month='2026-09'):
    valid,rejected=validate(rows)
    start=min(r['effective_month'] for r in valid)
    if end_month<max(r['effective_month'] for r in valid): raise ValueError('End month precedes an event.')
    db=sqlite3.connect(':memory:'); db.row_factory=sqlite3.Row
    db.executescript('CREATE TABLE events(event_id TEXT PRIMARY KEY,customer_id TEXT,effective_month TEXT,mrr_cents INTEGER,segment TEXT,sequence INTEGER); CREATE TABLE months(month TEXT PRIMARY KEY);')
    db.executemany('INSERT INTO events VALUES(?,?,?,?,?,?)',[[r[f] for f in FIELDS] for r in valid])
    db.execute('CREATE INDEX account_event_order ON events(customer_id,effective_month DESC,sequence DESC)')
    db.executemany('INSERT INTO months VALUES(?)',[(m,) for m in month_range(start,end_month)])
    db.executescript(Path(__file__).with_name('revenue_model.sql').read_text())
    bridges=[dict(r) for r in db.execute('SELECT * FROM revenue_bridge ORDER BY month,segment')]
    for row in bridges:
        row['residual']=row['closing']-(row['opening']+row['new']+row['reactivation']+row['expansion']-row['contraction']-row['churn'])
        if row['residual']!=0: raise AssertionError('Revenue bridge failed to reconcile.')
    retention=[dict(r) for r in db.execute('SELECT * FROM cohort_retention ORDER BY cohort,segment,month')]
    ledger=[dict(r) for r in db.execute('SELECT * FROM movements WHERE customer_id IN (SELECT customer_id FROM accounts ORDER BY customer_id LIMIT 12) ORDER BY customer_id,month')]
    data=dict(meta=dict(owner='Titus Robinson',synthetic=True,seed=SEED,currency='USD',unit='integer cents',
                       inputEvents=len(rows),acceptedEvents=len(valid),rejectedEvents=len(rejected),
                       customers=db.execute('SELECT COUNT(*) FROM accounts').fetchone()[0],
                       months=len(month_range(start,end_month)),start=start,end=end_month,
                       rejectionReasons=dict(Counter(r['reason'] for r in rejected)),
                       reconciledBridges=len(bridges),maxAbsoluteResidual=max(abs(r['residual']) for r in bridges)),
              bridges=bridges,cohorts=retention,ledger=ledger)
    return data,db,rejected


def export(output, rows=None):
    output=Path(output); output.mkdir(parents=True,exist_ok=True)
    generated=rows is None
    rows=generate_demo() if generated else rows
    data,db,rejected=model(rows)
    data['meta'].update(dataOrigin='generated_synthetic' if generated else 'user_supplied',synthetic=True if generated else None,seed=SEED if generated else None)
    for filename,records,fields in [('revenue-events.csv',rows,FIELDS),('revenue-rejected.csv',rejected,FIELDS+['reason']),
                                    ('revenue-bridge.csv',data['bridges'],list(data['bridges'][0]))]:
        with (output/filename).open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(records)
    (output/'revenue-data.json').write_text(json.dumps(data,separators=(',',':'),allow_nan=False))
    db.close()
    return data


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path);parser.add_argument('--output',type=Path,default=Path('out'))
    args=parser.parse_args()
    if args.input and args.input.resolve()==(args.output/'revenue-events.csv').resolve(): parser.error('Output would overwrite the source.')
    rows=list(csv.DictReader(args.input.open())) if args.input else None
    result=export(args.output,rows)
    print(json.dumps(result['meta'],indent=2))
