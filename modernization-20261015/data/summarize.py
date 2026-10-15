#!/usr/bin/env python3
"""Validate every raw run and derive all published numbers without hand editing."""
import csv
import argparse
import hashlib
import json
import math
import pathlib
import statistics

HERE = pathlib.Path(__file__).resolve().parent
ARM_IDS = ('php-repeated-scan', 'php-one-pass', 'sql-unindexed-correlated',
           'sql-indexed-correlated', 'sql-indexed-grouped-control')

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def distribution(values):
    ordered = sorted(values)
    return {'median': statistics.median(ordered), 'min': min(ordered), 'max': max(ordered),
            'p95NearestRank': ordered[math.ceil(len(ordered) * .95) - 1], 'n': len(ordered)}

def build(rows):
    env = rows[0]
    assert env['kind'] == 'environment'
    assert rows[-1]['kind'] == 'completion' and rows[-1]['allOutputsEquivalent']
    sizes = env['sizes']
    assert len(sizes) >= 3 and sorted(set(sizes)) == sizes
    assert env['runs'] >= 10
    fixtures = {r['size']: r for r in rows if r['kind'] == 'fixture'}
    measured = [r for r in rows if r['kind'] == 'sample' and not r['warmup']]
    warmups = [r for r in rows if r['kind'] == 'sample' and r['warmup']]
    assert len(measured) == len(sizes) * len(ARM_IDS) * env['runs']
    assert len(warmups) == len(sizes) * len(ARM_IDS) * env['warmups']
    points = []
    for size in sizes:
        arms = {}
        for arm in ARM_IDS:
            sample = [r for r in measured if r['size'] == size and r['arm'] == arm]
            assert sorted(r['run'] for r in sample) == list(range(env['runs']))
            assert all(r['outputSha256'] == fixtures[size]['outputSha256'] for r in sample)
            assert all(r['outputRows'] == env['customers'] for r in sample)
            assert all(math.isfinite(r['wallSeconds']) and r['wallSeconds'] > 0 for r in sample)
            arms[arm] = {'seconds': distribution([r['wallSeconds'] for r in sample]),
                         'cpuSeconds': distribution([r['cpuSeconds'] for r in sample])}
        points.append({'size': size, 'arms': arms, 'outputSha256': fixtures[size]['outputSha256'],
                       'indexBuildSeconds': fixtures[size]['indexBuildSeconds'],
                       'tableBytes': fixtures[size]['tableBytes'],
                       'withIndexBytes': fixtures[size]['withIndexBytes'],
                       'indexExtraBytes': fixtures[size]['indexExtraBytes']})
    experiments = []
    for id_, before, after, control in [
        ('php-report', 'php-repeated-scan', 'php-one-pass', None),
        ('sqlite-report', 'sql-unindexed-correlated', 'sql-indexed-correlated', 'sql-indexed-grouped-control'),
    ]:
        before_s = [p['arms'][before]['seconds']['median'] for p in points]
        after_s = [p['arms'][after]['seconds']['median'] for p in points]
        before_cpu = [p['arms'][before]['cpuSeconds']['median'] for p in points]
        after_cpu = [p['arms'][after]['cpuSeconds']['median'] for p in points]
        experiment = {'id': id_, 'beforeArm': before, 'afterArm': after, 'sizes': sizes,
                      'beforeSeconds': before_s, 'afterSeconds': after_s,
                      'beforeCpuSeconds': before_cpu, 'afterCpuSeconds': after_cpu,
                      'speedup': [b / a for b, a in zip(before_s, after_s)],
                      'runs': env['runs'], 'aggregation': 'median', 'allOutputsEquivalent': True}
        if control:
            experiment['controlArm'] = control
            experiment['controlSeconds'] = [p['arms'][control]['seconds']['median'] for p in points]
        experiments.append(experiment)
    security = next(r for r in rows if r['kind'] == 'security')
    security['summary'] = {}
    for arm in security['cases'][0]['arms']:
        cases = security['cases']
        attacks = [c for c in cases if c['adversarial']]
        security['summary'][arm] = {'passed': sum(c['arms'][arm]['passed'] for c in cases), 'total': len(cases),
            'adversarialPassed': sum(c['arms'][arm]['passed'] for c in attacks), 'adversarialTotal': len(attacks),
            'otherTenantRowsAcrossCases': sum(c['arms'][arm]['otherTenantRows'] for c in cases)}
    assert security['summary']['prepared-and-scoped']['passed'] == len(security['cases'])
    return {'schemaVersion': 1, 'measuredAt': env['startedAt'], 'completedAt': rows[-1]['finishedAt'],
            'environment': env, 'experiments': experiments, 'points': points, 'security': security,
            'sampleCounts': {'measured': len(measured), 'warmup': len(warmups)},
            'limitations': [
                'Controlled synthetic report, not a customer project or production SLA.',
                'PHP 8.4.26 runs both implementations; there is no measured PHP-version effect.',
                'SQLite 3.46.1 runs both SQL versions; this is not a database-engine/version migration.',
                'Warm in-memory reads, no network or disk I/O; serialization and dataset creation are excluded.',
                'PHP CLI OPcache/JIT are off for both arms; web server throughput was not measured.',
                'CPU time is measured process resource use; it is not a cloud bill or energy measurement.',
                'The index consumes extra space and incurs one-time construction and ongoing write costs; ongoing writes were not benchmarked.',
                '200 report customers are fixed across all sizes; closed/open status distribution is deterministic.',
                'Security results cover only the six published synthetic tests; runtime upgrades do not automatically fix query authorization.'
            ]}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', type=pathlib.Path, default=HERE)
    directory = parser.parse_args().directory.resolve()
    rows = [json.loads(line) for line in (directory / 'raw.jsonl').read_text().splitlines()]
    summary = build(rows)
    (directory / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    keys = ['size', 'arm', 'run', 'warmup', 'position', 'wallSeconds', 'cpuSeconds', 'outputSha256', 'outputRows']
    with (directory / 'raw.csv').open('w', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=keys)
        writer.writeheader()
        writer.writerows({k: r[k] for k in keys} for r in rows if r['kind'] == 'sample')
    (directory / 'query-plans.json').write_text(json.dumps([r for r in rows if r['kind'] == 'fixture'], indent=2) + '\n')
    (directory / 'security.json').write_text(json.dumps(summary['security'], indent=2) + '\n')
    print(json.dumps({'samples': summary['sampleCounts'], 'largestSize': summary['points'][-1]['size'],
        'experiments': [{k: e[k][-1] if isinstance(e[k], list) else e[k] for k in
                        ('id', 'beforeSeconds', 'afterSeconds', 'beforeCpuSeconds', 'afterCpuSeconds', 'speedup')}
                        for e in summary['experiments']], 'security': summary['security']['summary']}, indent=2))

if __name__ == '__main__':
    main()
