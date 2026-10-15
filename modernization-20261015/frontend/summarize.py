#!/usr/bin/env python3
"""Verify every browser sample and publish medians without trimming slow runs."""
from pathlib import Path
import argparse
import csv
import io
import hashlib
import json
import statistics

ROOT = Path(__file__).resolve().parent

def summarize(input_path=None, output_dir=None):
    input_path = Path(input_path or ROOT / 'completed.json').resolve()
    output_dir = Path(output_dir or ROOT / 'reproduced').resolve()
    raw_bytes = input_path.read_bytes()
    evidence = json.loads(raw_bytes)
    manifest = evidence['manifest']
    assert manifest['status'] == 'completed'
    assert manifest['protocol'] == 'invoice-dom-v1'
    assert manifest['sizes'] == [1000, 10000, 50000]
    assert manifest['runs'] == 10 and manifest['warmups'] == 2
    assert manifest['visibilityAtStart'] == 'visible'
    points = []
    for size in manifest['sizes']:
        oracle = [i + 1 for i in range(size) if i % 3 != 0]
        checksum = str(sum(identifier * (10000 + ((identifier - 1) * 3571) % 900000) for identifier in oracle))
        arms = {}
        for arm in ['legacy', 'virtualized']:
            samples = [s for s in evidence['samples'] if s['size'] == size and s['arm'] == arm]
            assert len(samples) == 12
            recorded = [s for s in samples if not s['warmup']]
            assert sorted(s['run'] for s in recorded) == list(range(1, 11))
            assert len([s for s in samples if s['warmup']]) == 2
            for sample in samples:
                assert sample['elapsedMs'] > 0
                assert sample['checksum'] == checksum
                assert sample['matchedCount'] == len(oracle)
                checks = sample['viewportChecks']
                assert checks['top'] and checks['bottom'] and checks['scrollHeight']
                assert checks['topIds'] == oracle[:14]
                assert checks['bottomIds'] == oracle[-14:]
                assert sample['renderedRows'] == (len(oracle) if arm == 'legacy' else 40)
            durations = [s['elapsedMs'] for s in recorded]
            arms[arm] = {'medianMs': statistics.median(durations), 'minMs': min(durations), 'maxMs': max(durations), 'resourceValue': recorded[0]['renderedRows'], 'matchedCount': len(oracle), 'checksum': checksum, 'runs': 10}
        points.append({'size': size, 'arms': arms})
    assert len(evidence['security']) == 6
    for check in evidence['security']:
        assert check['passed'] and check['afterText'] == check['input'] and check['afterElementCount'] == 0
    assert sum(check['beforeElementCount'] > 0 for check in evidence['security']) == 2
    summary = {'schemaVersion': 1, 'id': 'frontend-invoice-list', 'manifest': manifest, 'beforeArm': 'legacy', 'afterArm': 'virtualized', 'runs': 10, 'aggregation': 'median', 'allOutputsEquivalent': True, 'resource': 'rendered invoice DOM rows', 'points': points, 'security': evidence['security']}
    csv_buffer = io.StringIO(newline='')
    writer = csv.DictWriter(csv_buffer, fieldnames=['size', 'arm', 'run', 'warmup', 'elapsedMs', 'matchedCount', 'checksum', 'renderedRows'])
    writer.writeheader()
    writer.writerows({key: sample[key] for key in writer.fieldnames} for sample in evidence['samples'])
    names = ['benchmark.html', 'serve.py', 'summarize.py', 'test_collector.py', 'test_summarize.py', 'collector-hardening.json', 'README.md']
    package = {name: (ROOT / name).read_bytes() for name in names}
    package['completed.json'] = raw_bytes
    package['summary.json'] = (json.dumps(summary, indent=2) + '\n').encode()
    package['raw.csv'] = csv_buffer.getvalue().encode()
    hashes = {name: hashlib.sha256(body).hexdigest() for name, body in package.items()}
    package['SHA256.json'] = (json.dumps(hashes, indent=2) + '\n').encode()
    # Verify every destination before creating anything. A reproduced run must not
    # silently replace a different frozen evidence package or follow a symlink.
    for name, body in package.items():
        destination = output_dir / name
        if destination.is_symlink() or destination.resolve().parent != output_dir:
            raise ValueError(f'Unsafe output destination: {destination}')
        if destination.exists() and destination.read_bytes() != body:
            raise FileExistsError(f'Output differs: {destination}. Choose a new --output directory.')
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, body in package.items():
        destination = output_dir / name
        if not destination.exists():
            with destination.open('xb') as handle:
                handle.write(body)
    return {'samples': len(evidence['samples']), 'points': points, 'input': str(input_path), 'output': str(output_dir)}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=ROOT / 'completed.json', help='Completed collector JSON to verify (default: published completed.json beside this script).')
    parser.add_argument('--output', type=Path, default=ROOT / 'reproduced', help='New output directory (default: reproduced/ beside this script); different existing files are never overwritten.')
    args = parser.parse_args()
    print(json.dumps(summarize(args.input, args.output), indent=2))
