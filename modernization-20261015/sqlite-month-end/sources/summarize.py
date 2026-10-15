#!/usr/bin/env python3
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from statistics import median

HERE = Path(__file__).resolve().parent
ARMS = ['sql-unindexed-correlated', 'sql-indexed-correlated', 'sql-indexed-grouped-control']

def distribution(values):
    v = sorted(values)
    return dict(median=median(v), min=min(v), max=max(v), p95NearestRank=v[math.ceil(.95*len(v))-1], n=len(v))

def build(raw, protocol):
    env = raw[0]
    assert env['kind'] == 'environment' and env['sizes'] == protocol['sizes']
    assert env['runs'] == 10 and env['warmups'] == 2 and env['customers'] == 500
    assert raw[-1]['kind'] == 'completion' and raw[-1]['allOutputsEquivalent']
    samples = [r for r in raw if r['kind'] == 'sample']
    assert len(samples) == 108
    fixtures = {r['size']: r for r in raw if r['kind'] == 'fixture'}
    points = []
    for size in protocol['sizes']:
        fixture = fixtures[size]
        assert len(fixture['expectedRows']) == 500
        assert hashlib.sha256(json.dumps(fixture['expectedRows'],separators=(',',':')).encode()).hexdigest() == fixture['outputSha256']
        arms = []
        for arm in ARMS:
            group = [r for r in samples if r['size'] == size and r['arm'] == arm]
            assert sorted(r['run'] for r in group) == list(range(-2,10))
            for r in group:
                assert r['warmup'] == (r['run'] < 0)
                assert r['rows'] == fixture['expectedRows'] and r['outputRows'] == 500
                assert r['outputSha256'] == fixture['outputSha256']
                assert r['wallSeconds'] > 0 and r['cpuSeconds'] >= 0
            measured = [r for r in group if not r['warmup']]
            arms.append(dict(id=arm,runs=10,seconds=distribution([r['wallSeconds'] for r in measured]),cpuSeconds=distribution([r['cpuSeconds'] for r in measured])))
        points.append(dict(size=size,arms=arms,indexBuildSeconds=fixture['indexBuildSeconds'],indexExtraBytes=fixture['indexExtraBytes'],tableBytes=fixture['tableBytes'],withIndexBytes=fixture['withIndexBytes'],loadSeconds=fixture['loadSeconds'],outputSha256=fixture['outputSha256']))
    return dict(schemaVersion=1,id='sqlite-month-end',measuredAt=env['startedAt'],completedAt=raw[-1]['finishedAt'],environment=env,points=points,runs=10,aggregation='median',baselineId=ARMS[0],modernId=ARMS[1],controlId=ARMS[2],measuredSamples=90,warmupSamples=18,allOutputsEquivalent=True)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--directory',type=Path,required=True);args=parser.parse_args()
    directory=args.directory
    raw=[json.loads(line) for line in (directory/'raw.jsonl').read_text().splitlines()]
    protocol=json.loads((HERE/'protocol.json').read_text())
    summary=build(raw,protocol)
    (directory/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    fields=['size','arm','run','warmup','position','wallSeconds','cpuSeconds','outputSha256','outputRows']
    with (directory/'raw.csv').open('w',newline='') as file:
        writer=csv.DictWriter(file,fieldnames=fields);writer.writeheader();writer.writerows({k:r[k] for k in fields} for r in raw if r['kind']=='sample')
    (directory/'query-plans.json').write_text(json.dumps([r for r in raw if r['kind']=='fixture'],indent=2)+'\n')
    print(json.dumps({'samples':90,'points':[{'size':p['size'],'medians':{a['id']:a['seconds']['median'] for a in p['arms']}} for p in summary['points']]},indent=2))

if __name__=='__main__':main()
