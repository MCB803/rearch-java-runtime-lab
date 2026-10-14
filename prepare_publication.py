#!/usr/bin/env python3
"""Verify a complete frozen run and package it; never rerun or select measurements."""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import statistics
import zipfile


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def verify(source):
    manifest = json.loads((source / 'manifest.json').read_text())
    if manifest.get('status') != 'completed' or manifest.get('profile') != 'full-pilot':
        raise ValueError('Publication requires the completed full matrix; smoke or failed runs are rejected.')
    if manifest.get('completedRuns') != 440 or len(manifest.get('jobs', [])) != 440:
        raise ValueError('Incomplete run count.')
    if (manifest.get('warmupMilliseconds'), manifest.get('measurementMilliseconds')) != (5000, 1000):
        raise ValueError('Unexpected protocol windows.')
    if manifest.get('dependency', {}).get('configuredDelayMilliseconds') != 20:
        raise ValueError('Publication is bound to the amended 20 ms dependency protocol.')
    for name, expected in manifest['sourceSha256'].items():
        if sha(source / 'sources' / name) != expected:
            raise ValueError('Frozen source hash mismatch: ' + name)
    for name, expected in json.loads((source / 'SHA256.json').read_text()).items():
        if sha(source / name) != expected:
            raise ValueError('Artifact hash mismatch: ' + name)
    spec = importlib.util.spec_from_file_location('frozen_runner', source / 'sources/run.py')
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    if manifest['jobs'] != runner.matrix(True):
        raise ValueError('Matrix or fixed randomized order differs from frozen source.')
    rows = [json.loads(line) for line in (source / 'raw.jsonl').read_text().splitlines()]
    if len(rows) != len(manifest['jobs']):
        raise ValueError('Raw rows do not cover every planned job.')
    groups = defaultdict(list)
    for index, (row, job) in enumerate(zip(rows, manifest['jobs']), 1):
        runner.validate(row, job)
        if row.get('sequence') != index or any(row.get(key) != value for key, value in job.items()):
            raise ValueError('Missing, duplicated or reordered run.')
        log = json.loads((source / f'logs/run-{index:04d}.json').read_text())
        if log.get('returncode') != 0:
            raise ValueError('A process failed.')
        stdout = json.loads(log['stdout'])
        if any(row.get(key) != value for key, value in stdout.items()):
            raise ValueError('Raw measurement differs from process stdout.')
        if (source / f'logs/dependency-{index:04d}.txt').read_text().strip():
            raise ValueError('Dependency emitted an error; inspect before publication.')
        key = '/'.join(str(row[name]) for name in ['task', 'jdk', 'executor', 'limit', 'size'])
        groups[key].append(row)
    if len(groups) != 44 or any(len(values) != 10 for values in groups.values()):
        raise ValueError('All 44 arms require all 10 independent repetitions.')
    if any(sorted(row['repeat'] for row in values) != list(range(1, 11)) for values in groups.values()):
        raise ValueError('Duplicated repeat identifiers.')
    summary = json.loads((source / 'summary.json').read_text())
    if summary['groups'] != runner.summarize(rows):
        raise ValueError('Summary cannot be reproduced from every raw row.')
    return manifest, rows, groups


def distribution(values):
    q1, _, q3 = statistics.quantiles(values, n=4, method='inclusive')
    return dict(n=len(values), min=min(values), q1=q1, median=statistics.median(values), q3=q3, max=max(values))


def derived(groups):
    return {key: {
        'batchSeconds': distribution([row['elapsedNanos'] / row['batches'] / 1e9 for row in rows]),
        'operationsPerSecond': distribution([row['operations'] / (row['elapsedNanos'] / 1e9) for row in rows]),
        'perRunP95Seconds': distribution([row['p95Nanos'] / 1e9 for row in rows]),
    } for key, rows in sorted(groups.items())}


def redact(text, workspace):
    # Keep build/architecture evidence while removing identifying local path prefixes.
    return text.replace(str(workspace.resolve()), '$WORKSPACE').replace(str(Path.home()), '$HOME')


def copy_evidence(source, destination, workspace):
    changed = []
    for path in sorted(source.rglob('*')):
        relative = path.relative_to(source)
        if not path.is_file() or {'classes', '__pycache__'} & set(relative.parts):
            continue
        if relative.as_posix() == 'SHA256.json':
            continue  # A fresh checksum file covers the public, path-redacted copy.
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        # Text-mode I/O normalizes CSV CRLF to LF even without a redaction.
        # Preserve every byte except the explicit UTF-8 path-prefix replacement.
        original = path.read_bytes()
        cleaned = redact(original.decode('utf-8'), workspace).encode('utf-8')
        target.write_bytes(cleaned)
        if cleaned != original:
            changed.append(relative.as_posix())
    write_json(destination / 'ORIGINAL-SHA256.json', json.loads((source / 'SHA256.json').read_text()))
    return changed


def checksum_tree(root):
    return {path.relative_to(root).as_posix(): sha(path) for path in sorted(root.rglob('*'))
            if path.is_file() and not {'.git', '__pycache__'} & set(path.relative_to(root).parts)
            and path.relative_to(root).as_posix() != 'SHA256.json'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--failed-run', type=Path, required=True)
    parser.add_argument('--repository', type=Path, required=True)
    parser.add_argument('--public', type=Path, required=True)
    parser.add_argument('--repo-url', required=True)
    args = parser.parse_args()
    if not args.repo_url.startswith('https://github.com/'):
        raise ValueError('A real, separately published repository URL is required.')
    manifest, rows, groups = verify(args.run)
    repo = args.repository
    repo.mkdir(parents=True, exist_ok=True)
    dataset = repo / 'data/2026-10-14'
    if dataset.exists():
        raise ValueError('Refusing to overwrite a public data package.')
    changed = copy_evidence(args.run, dataset, Path.cwd())
    failed = repo / 'data/failed-initial-attempt'
    failed_changed = copy_evidence(args.failed_run, failed, Path.cwd())
    stats = derived(groups)
    write_json(dataset / 'distributions.json', stats)
    primary = {str(jdk): stats[f'report/{jdk}/platform/16/1000000']['batchSeconds'] for jdk in [8, 25]}
    review = {
        'scope': 'Measured synthetic runtime/executor study; not a customer result or a migrated historic application',
        'status': 'complete-dataset-integrity-verified',
        'reviewer': 'Automated independent checksum and source/log consistency review; editorial review by the site publication workflow',
        'reviewedAt': datetime.now(timezone.utc).isoformat(),
        'repoUrl': args.repo_url,
        'rawAutomationFlag': 'Original publishable:false flags are preserved. They prevent the runner from granting publication approval; this separate record documents the narrower reviewed scope.',
        'checks': {'freshJvmRuns': len(rows), 'groups': len(groups), 'runsPerGroup': 10, 'checksumMatches': len(rows), 'processFailures': 0, 'dependencyErrors': 0, 'discardedRunsInCompletedMatrix': 0},
        'primaryMetric': {'preselected': True, 'task': 'report', 'records': 1000000, 'aggregation': 'median of per-JVM elapsedNanos/batches', 'unit': 'seconds', 'distributions': primary},
        'failedAttempt': {'includedInPrimaryDataset': False, 'directory': '../failed-initial-attempt', 'reason': 'Initial 2 ms protocol exhausted TCP ephemeral ports at process 3. Protocol amended before restarting the entire fixed-order matrix.'},
        'redaction': {'rule': 'Only identifying absolute home/workspace prefixes are replaced by $HOME/$WORKSPACE. Workload values, times, counts, checksums and runtime build strings remain unchanged.', 'changedFiles': changed, 'failedAttemptChangedFiles': failed_changed},
        'compiledBytecodeSha256': {path.name: sha(path) for path in sorted((args.run / 'classes').glob('*.class'))},
        'runtimeBinarySha256': {major: {name: sha(Path(details['home']) / name) for name in ['release', 'bin/java', 'bin/javac', 'lib/server/libjvm.dylib', 'jre/lib/server/libjvm.dylib', 'lib/server/libjvm.so', 'jre/lib/amd64/server/libjvm.so'] if (Path(details['home']) / name).is_file()} for major, details in manifest['jdks'].items()},
        'runtimeScopeReview': 'The frozen manifest did not approve patch currency. This publication does not claim currency: it names the exact installed old/new builds and limits conclusions to them.',
        'originalRawJsonlSha256': sha(args.run / 'raw.jsonl'),
        'publicRawJsonlSha256': sha(dataset / 'raw.jsonl'),
        'originalRawCsvSha256': sha(args.run / 'raw.csv'),
        'publicRawCsvSha256': sha(dataset / 'raw.csv'),
        'originalManifestSha256': sha(args.run / 'manifest.json'),
        'backgroundActivity': 'The coordinating agent reports source reading, very brief unit checks and browser-based Cloudflare/Resend account setup during measurement. No heavy build, typecheck or E2E suite was started. The host was not dedicated or idle; OS/browser background activity was not separately isolated.',
        'load1m': {'min': min(min(row['hostLoad1mBefore'], row['hostLoad1mAfter']) for row in rows), 'max': max(max(row['hostLoad1mBefore'], row['hostLoad1mAfter']) for row in rows)},
        'limitations': [item for item in manifest['limitations'] if item != 'Installed JDK patch currency not approved for publication'] + ['Different JDK patch vintages: results compare these exact installed builds, not an isolated major-version effect.', 'No inferential confidence interval or universal Java speedup claim.', 'Human implementation hours were not tracked; automation wall-clock time is not human work time.'],
    }
    if (review['originalRawJsonlSha256'] != review['publicRawJsonlSha256'] or
            review['originalRawCsvSha256'] != review['publicRawCsvSha256']):
        raise ValueError('Raw numeric data unexpectedly changed during packaging.')
    write_json(dataset / 'publication-review.json', review)
    for name in ['prepare_publication.py', 'test_publication.py', 'build_case_content.py']:
        shutil.copy2(Path(__file__).with_name(name), repo / name)
    shutil.copy2(Path(__file__).with_name('PUBLICATION_SCOPE.md'), repo / 'PUBLICATION_SCOPE.md')
    write_json(repo / 'SHA256.json', checksum_tree(repo))
    args.public.mkdir(parents=True, exist_ok=False)
    for filename in ['raw.csv', 'raw.jsonl', 'manifest.json', 'summary.json', 'distributions.json', 'publication-review.json']:
        shutil.copy2(dataset / filename, args.public / filename)
    archive = args.public / 'rearch-java-runtime-lab-2026-10-14.zip'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as bundle:
        for relative in checksum_tree(repo):
            bundle.write(repo / relative, 'rearch-java-runtime-lab/' + relative)
        bundle.write(repo / 'SHA256.json', 'rearch-java-runtime-lab/SHA256.json')
    write_json(args.public / 'SHA256.json', checksum_tree(args.public))
    print(json.dumps({'runs':len(rows), 'groups':len(groups), 'primarySeconds':primary, 'publicRawUnchanged':True, 'archiveBytes':archive.stat().st_size}, indent=2))


if __name__ == '__main__':
    main()
