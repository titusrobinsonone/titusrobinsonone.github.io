"""Experiment Decision Studio — Titus Robinson's independent portfolio.

Reproducible synthetic fixed-horizon experiment with a conversion metric,
error-rate guardrail and sample-ratio-mismatch gate. Standard library only.
Run: python src/experiment_studio.py --output docs/assets
"""
from __future__ import annotations
import argparse
import csv
import json
import math
import random
from collections import Counter
from pathlib import Path
from statistics import NormalDist

SEED=20261028
Z95=NormalDist().inv_cdf(0.975)
Z_ONE_SIDED=NormalDist().inv_cdf(0.95)
SRM_ALPHA=0.001


def difference(control_success, control_n, treatment_success, treatment_n):
    if min(control_n,treatment_n)<=0 or not 0<=control_success<=control_n or not 0<=treatment_success<=treatment_n:
        raise ValueError('Invalid binomial counts.')
    a=control_success/control_n; b=treatment_success/treatment_n; delta=b-a
    se=math.sqrt(a*(1-a)/control_n+b*(1-b)/treatment_n)
    pooled=(control_success+treatment_success)/(control_n+treatment_n)
    pooled_se=math.sqrt(pooled*(1-pooled)*(1/control_n+1/treatment_n))
    p=math.erfc(abs(delta/pooled_se)/math.sqrt(2)) if pooled_se else (1 if delta==0 else 0)
    return dict(controlRate=a,treatmentRate=b,delta=delta,lower=delta-Z95*se,upper=delta+Z95*se,
                upperOneSided=delta+Z_ONE_SIDED*se,pValue=p,
                largeCounts=min(control_success,control_n-control_success,treatment_success,treatment_n-treatment_success)>=10)


def srm(control_n,treatment_n,expected_treatment=0.5):
    if min(control_n,treatment_n)<0 or control_n+treatment_n==0 or not 0<expected_treatment<1:
        raise ValueError('Invalid assignment counts.')
    total=control_n+treatment_n; e_b=total*expected_treatment; e_a=total-e_b
    statistic=(control_n-e_a)**2/e_a+(treatment_n-e_b)**2/e_b
    # Survival function of chi-square(1): erfc(sqrt(x/2)).
    return dict(statistic=statistic,pValue=math.erfc(math.sqrt(statistic/2)),expectedTreatment=expected_treatment,
                actualTreatment=treatment_n/total,passed=math.erfc(math.sqrt(statistic/2))>=SRM_ALPHA)


def decide(result,minimum_lift=0.002,maximum_error_increase=0.005):
    if not result['allocation']['passed']: return 'Investigate allocation'
    if not result['conversion']['largeCounts'] or not result['errors']['largeCounts']: return 'Insufficient data'
    if result['errors']['lower']>maximum_error_increase: return 'Stop: guardrail regression'
    if result['errors']['upperOneSided']>maximum_error_increase: return 'Inconclusive: guardrail risk'
    if result['conversion']['upper']<0: return 'Stop: conversion harm'
    if result['conversion']['lower']>=minimum_lift: return 'Ship candidate'
    return 'Inconclusive: practical lift'


def generate_demo(seed=SEED,n_per_variant=12000):
    rng=random.Random(seed); rows=[]
    for scenario in ('balanced','guardrail-regression'):
        for variant in ('control','treatment'):
            for i in range(n_per_variant):
                mobile=rng.random()<0.60
                p=(0.108 if mobile else 0.138)+(0.016 if variant=='treatment' else 0)
                error_p=(0.035 if scenario=='guardrail-regression' else 0.013) if variant=='treatment' else 0.012
                rows.append(dict(scenario=scenario,user_id=f'{scenario}-{variant}-{i:05}',variant=variant,
                                 device='Mobile' if mobile else 'Desktop',converted=int(rng.random()<p),
                                 error=int(rng.random()<error_p)))
    # Intentional telemetry loss, to demonstrate why the allocation gate matters.
    for row in list(rows):
        if row['scenario']=='balanced' and not (row['variant']=='treatment' and int(row['user_id'].split('-')[-1])%5==0):
            rows.append({**row,'scenario':'logging-loss','user_id':'loss-'+row['user_id']})
    return rows


def analyze(rows):
    groups={'control':[],'treatment':[]}; seen=set()
    for raw in rows:
        row=dict(raw); key=row.get('user_id')
        if not key or key in seen: raise ValueError('Each experimental unit must appear exactly once.')
        if row.get('variant') not in groups or str(row.get('converted')) not in ('0','1') or str(row.get('error')) not in ('0','1'):
            raise ValueError('Invalid variant or binary outcome.')
        seen.add(key); row['converted']=int(row['converted']);row['error']=int(row['error'])
        groups[row['variant']].append(row)
    a,b=groups['control'],groups['treatment']; na,nb=len(a),len(b)
    result=dict(counts=dict(control=na,treatment=nb),allocation=srm(na,nb),
                conversion=difference(sum(r['converted'] for r in a),na,sum(r['converted'] for r in b),nb),
                errors=difference(sum(r['error'] for r in a),na,sum(r['error'] for r in b),nb),
                segments=[])
    for device in sorted({r.get('device','Unknown') for r in rows}):
        for variant,group in groups.items():
            selected=[r for r in group if r.get('device','Unknown')==device]
            result['segments'].append(dict(device=device,variant=variant,users=len(selected),converted=sum(r['converted'] for r in selected),errors=sum(r['error'] for r in selected)))
    result['decision']=decide(result)
    return result


def export(output,rows=None):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    generated=rows is None
    rows=generate_demo() if generated else rows
    scenarios=[]
    for key in sorted({r['scenario'] for r in rows}):
        result=analyze([r for r in rows if r['scenario']==key]);result['id']=key;scenarios.append(result)
    data=dict(meta=dict(owner='Titus Robinson',synthetic=True,seed=SEED,analysis='fixed-horizon',
                        confidence=0.95,srmAlpha=SRM_ALPHA,minimumLift=0.002,maximumErrorIncrease=0.005,
                        rows=len(rows),unit='one user, one observation per scenario',
                        interval='unpooled normal approximation; large counts checked',
                        guardrail='one-sided 95% upper bound for treatment-minus-control error rate'),scenarios=scenarios)
    data['meta'].update(dataOrigin='generated_synthetic' if generated else 'user_supplied',synthetic=True if generated else None,seed=SEED if generated else None)
    with (output/'experiment-users.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['scenario','user_id','variant','device','converted','error']);writer.writeheader();writer.writerows(rows)
    (output/'experiment-data.json').write_text(json.dumps(data,separators=(',',':'),allow_nan=False))
    return data


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path);parser.add_argument('--output',type=Path,default=Path('out'))
    args=parser.parse_args()
    if args.input and args.input.resolve()==(args.output/'experiment-users.csv').resolve(): parser.error('Output would overwrite the source.')
    rows=list(csv.DictReader(args.input.open())) if args.input else None
    result=export(args.output,rows)
    for scenario in result['scenarios']:
        print(scenario['id'],scenario['counts'],scenario['decision'])
