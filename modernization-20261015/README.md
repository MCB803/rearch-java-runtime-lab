# ReArch Labs · implementation modernization laboratory

15 October 2026. Six completed experiments cover separate business operations, including a larger SQLite report measured at 100,000, 1,000,000 and 5,000,000 order records. All planned measurements and warmups are retained in their evidence packages.

These are newly written synthetic workloads with reproducible source, exact output checks, recorded controls and every measured repetition. They are not customer case studies. The original [440-run Java runtime study](../README.md#original-runtime-experiment) and its [results](../RESULTS.md) are preserved. That study asks what changes when the same code uses a different runtime; these workloads investigate concrete changes to how an operation is implemented.

## Experiment index

| Experiment | Business operation and comparison | Status | Evidence |
| --- | --- | --- | --- |
| Java order integration | Price, stock and shipping lookups: sequential work versus bounded parallel work. Includes unchanged Java 25 code, equivalent platform concurrency and constrained-dependency controls. | Completed | [Result and scope](java/README.md) · [source and protocol](java/full/sources/README.md) · [raw runs](java/full/raw.jsonl) |
| PHP report computation | The same 200-customer balance report: scan all orders per customer versus aggregate once. Same PHP runtime. | Completed | [Method and results](data/README.md) · [source](data/benchmark.php) · [raw runs](data/raw.jsonl) |
| SQLite report indexing | The same report and SQL: no supporting index versus a covering index. A grouped-query alternative remains as a control. Same database engine. | Completed | [Method and results](data/README.md) · [query plans](data/query-plans.json) · [raw runs](data/raw.jsonl) |
| .NET catalog matching | Match prepared import rows to 10,000 products: repeated `List.Find` versus a new `Dictionary` per batch. `FrozenDictionary` is retained as a control. Same .NET 10 runtime. | Completed | [Result and scope](dotnet/README.md) · [source and protocol](dotnet/full/sources/README.md) · [raw runs](dotnet/full/raw.jsonl) |
| Browser invoice list | Filter an invoice dataset and produce its initial viewport: full DOM rows versus a moving window. Same browser and result set. | Completed | [Method and scope](frontend/README.md) · [browser source](frontend/benchmark.html) · [all observations](frontend/completed.json) |
| Larger SQLite month-end report | A separate 500-customer workload at 100,000, 1,000,000 and 5,000,000 order records. Identical correlated SQL before/after a covering index, plus a grouped-query control. | Completed | [Protocol and source](sqlite-month-end/sources/README.md) · [all 90 measurements and 18 warmups](sqlite-month-end/raw.jsonl) · [summary and index cost](sqlite-month-end/summary.json) |

The two PHP/SQLite report comparisons share one evidence package and must not have their ratios multiplied together. The month-end report is a separate experiment, not an extrapolation of the smaller report.

## What the measurements mean

- Java's principal comparison changes workflow, concurrency and runtime together. Its unchanged-code arm isolates the runtime comparison. The identical dependency model applies to every arm; its configured latency is not a measurement of an internet service. Virtual threads are not presented as faster CPU instructions.
- PHP and SQLite gains measure code and access-pattern changes on fixed versions. The SQLite read timer excludes index construction; the package records its separate one-time construction observation and storage cost. Write performance is outside that experiment.
- .NET measures the matching stage with input rows already in memory, including a newly built index in every timed batch. CSV reading, network and database writes are excluded. Allocation bytes are cumulative managed allocation, not peak memory or RSS. The slower FrozenDictionary control and the small-load allocation tradeoff remain visible.
- Browser timings cover filtering, DOM work, layout and a two-frame boundary. They are not Core Web Vitals INP, server latency or an entire application's user journey. DOM-row count is not a memory measurement. The separate output-encoding checks have their own limited scope.
- PHP's six local query/access checks include a prepared-statement-only control that still fails cross-tenant authorization. Passing these fixed tests is not a general security certification.
- These shared-workstation results do not establish a customer's speedup, hosting bill, electricity saving, production capacity or universal version-upgrade benefit. Workload and environment remain part of each result.

## Reproduction and evidence integrity

Each linked protocol lists its runtime, input model, timer boundary, repetitions, controls and commands. Java requires installed Java 8/25 JDKs and Python 3. PHP/SQLite and .NET require the recorded native arm64 Docker images and Python 3. The browser fixture requires a visible browser and its local Python collector. A rerun should use a new output directory and retain the complete result matrix; exact durations will vary between environments.

The source packages were copied byte-for-byte from the completed public evidence. Each `SHA256.json` records its package's sources, raw data, summaries and logs. To verify those recorded files, run this from the repository root:

```sh
python3 - <<'PY'
from pathlib import Path
import hashlib
import json

base = Path('modernization-20261015')
checked = 0
for manifest in sorted(base.rglob('SHA256.json')):
    for name, expected in json.loads(manifest.read_text()).items():
        path = manifest.parent / name
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise SystemExit(f'Hash mismatch: {path}')
        checked += 1
print(f'Verified {checked} recorded files')
PY
```

Java's completed smoke package is retained as preliminary provenance; the published comparison uses `java/full/`. The browser collector received separately documented post-measurement input/path hardening; [its record](frontend/collector-hardening.json) distinguishes that change from the unchanged measured browser fixture. No measurement values were replaced by the collector hardening.
