# Hesap özeti laboratuvarı / Account-balance report lab

15 October 2026. ReArch Labs' own synthetic implementation and data. This is a reproducible code/query remediation experiment, not a customer result and not a PHP or database version migration benchmark.

## Business workload

A finance operator requests the open order balance of 200 customer accounts. Both implementations return the same ordered 200-row report, including customers with no open balance. The dataset grows through **1,000 / 3,000 / 10,000 / 30,000 / 60,000 / 100,000 / 200,000 orders**. Integer cents avoid floating-point reconciliation differences. Each input and full output has a SHA-256 hash.

The legacy patterns are deliberately explicit: repeating a full in-memory order scan for each customer, and running a correlated SQL report without the index its filters need. These patterns can appear in accumulated application code; age alone does not prove that any particular customer has them. There are no artificial delays, throttled old arms, emulated obsolete runtimes, network calls, or fabricated observations.

## Measured arms

| ID | Implementation | What changes |
| --- | --- | --- |
| `php-repeated-scan` | For each customer, scan the order array and add its open orders | Baseline repeated work |
| `php-one-pass` | Build balances with one pass, then render the 200 customers | Algorithm/data access; aggregate is rebuilt in every timed call |
| `sql-unindexed-correlated` | Correlated SUM for each customer, no supporting order index | SQL baseline |
| `sql-indexed-correlated` | **Identical SQL** with `(customer_id, status, total_cents)` covering index | Index only |
| `sql-indexed-grouped-control` | Group orders once and LEFT JOIN customers on the indexed database | Additional rewrite control; published even when it is slower than the indexed correlated query |

All five arms run under **PHP 8.4.26** and its **SQLite 3.46.1** PDO driver. PHP version and database engine do not change. The PHP and SQL gains are separate comparisons and must not be multiplied together or advertised as a PHP-version gain.

## Recorded result at 200,000 orders

Ten measured repetitions per arm, after two warmups:

| Comparison | Before median | After median | Before / after |
| --- | ---: | ---: | ---: |
| PHP report implementation | 1,265.123 ms | 8.487 ms | 149.07× |
| SQL index only, same query | 1,129.159 ms | 7.188 ms | 157.08× |
| SQL grouped rewrite control | — | 10.158 ms | Slower than the 7.188 ms indexed correlated arm |

The SQL improvement has a concrete tradeoff: the largest fixture's index took **77.557 ms once** to build and added **3,899,392 bytes**, from 3,932,160 to 7,831,552 SQLite allocated bytes. Index construction is **not** included in read latency. These index-build numbers are one observation per size, not ten-run medians. Query plans record `SCAN o` before and `SEARCH o USING COVERING INDEX ...` after. Ongoing writes and index maintenance were not benchmarked.

PHP process CPU fell from a median 1.2649005 to 0.008495 CPU-seconds for this report; SQL CPU fell from 1.1290045 to 0.007187 CPU-seconds. This is actual process resource use, not a measured electricity reduction, monthly bill, customer cost saving, or server-capacity forecast.

## Method and environment

- Apple M3, Mac15,3, 8 host CPU cores, 24 GiB RAM, macOS 26.5.2 arm64.
- Docker Desktop engine 27.4.0, Linux aarch64; native architecture, no x86 emulation. Container quota 2 CPUs / 1 GiB RAM; PHP memory limit 768 MiB. The PHP workload is single process/single threaded.
- Official PHP image pinned to `php@sha256:1d2cf2b7d715b5b3aa959f0150ccbcc7b71e0181b637e443abf40a7fb56bf79a`.
- CLI OPcache/JIT off for both PHP arms. The experiment does not benchmark web server throughput, PHP-FPM pools, or a version upgrade.
- For each size, two fresh independent SQLite `:memory:` databases receive identical rows. One retains the unindexed schema; the other receives the index. Connections are reused across warmups and measurements at that size. Both are warm in-memory read workloads, not cold storage experiments.
- Two warmups and ten retained measurements for each of seven sizes and five arms: **70 warmup + 350 measured samples**. A deterministic rotation changes arm order each round. All samples, including min/max and the slower grouped control, are published; none are removed.
- Timed regions contain report computation/query execution **and result materialization**. They exclude fixture construction, database loading, index creation, process startup, hashing, and JSON serialization. PHP aggregate allocation is included each time.
- `hrtime(true)` records monotonic wall duration. `getrusage()` records process user + system CPU. CPU timing includes slightly more instrumentation than wall timing, so CPU can be a few microseconds larger.
- Complete ordered results are compared with an independent SQL GROUP BY/LEFT JOIN oracle on every run; a mismatch terminates publication. Report correctness is also tested with hand-written totals, a closed order, and an empty customer.
- `p95NearestRank` is the nearest-rank sample p95, which with ten runs is the maximum. It is not request-tail latency under production traffic.
- The generator is deterministic: 200 customer IDs distributed by a coprime modular sequence, three quarters open orders, integer order values. Status is correlated with the deterministic customer assignment, leaving 50 customers with no open orders; both report paths must retain those zero-balance customers. No realistic distribution claim is made.
- Java benchmark execution was coordinated to start only after this measurement ended. Other normal OS background activity was not completely eliminated.

## Security replay and its control

`security.json` contains every one of **six** fixed local cases against 12 self-owned synthetic invoices from two tenants. The intentionally unsafe SQL exists only inside the CLI lab source; it is not an application endpoint. Normal lookup, unknown reference and legitimate apostrophe are included alongside two SQL injection inputs and a direct other-tenant reference.

| Implementation | All cases passed | Three adversarial cases blocked correctly |
| --- | ---: | ---: |
| Concatenated SQL, missing tenant scope | 2 / 6 | 0 / 3 |
| Prepared parameters only (control) | 5 / 6 | 2 / 3 |
| Prepared parameters **and** authenticated tenant scope | 6 / 6 | 3 / 3 |

The normal `T1-001` lookup returns invoice 1 in all arms. The `T2-001` lookup still exposes invoice 7 when parameters are added without authorization, which is why that control remains visible. The final arm takes tenant 1 from the lab's fixed authenticated context, rather than a client-provided tenant. These are code/security-design improvements; upgrading PHP does not automatically repair authorization or concatenated SQL. Six passing lab checks are not a general security certification, dependency scan, penetration test, or proof of zero vulnerabilities.

## Reproduce and validate

Requires Docker with the native arm64 PHP image and Python 3. On non-arm64 hosts the command may emulate; results would not be directly comparable and must be labeled separately.

```sh
python3 run.py --output /tmp/rearch-data-rerun-unique
python3 summarize.py
python3 -m unittest discover -s . -p 'test_*.py' -v
docker run --rm --network none --platform linux/arm64 --cpus 2 --memory 1g \
  -v "$PWD:/lab:ro" \
  php@sha256:1d2cf2b7d715b5b3aa959f0150ccbcc7b71e0181b637e443abf40a7fb56bf79a \
  php -d memory_limit=768M /lab/test_harness.php
```

The rerun requires a new directory and leaves this recorded publication unchanged. The container has no network access. PHP tests check actual report results and the security control; Python tests reconstruct summaries, reject a missing/tampered sample, and independently replay security queries through Python's SQLite driver.

`raw.jsonl` retains environment, input/output hashes, every timing, query plans, index costs, all security outcomes, and successful completion. `raw.csv` is the timing-only export. `summary.json` is generated entirely from raw observations. `SHA256.json` verifies the publication, including source and raw evidence; it excludes itself.

## Primary references

- [PHP PDO prepared statements](https://www.php.net/manual/en/pdo.prepared-statements.php): parameter handling and statement reuse. This does not supply tenant authorization.
- [PHP hrtime](https://www.php.net/manual/en/function.hrtime.php): monotonic high-resolution timer.
- [SQLite query planner](https://www.sqlite.org/queryplanner.html): scans, composite indexes and covering indexes.

References checked 15 October 2026. They explain the mechanisms; all numerical results above come from this lab's raw measurements, not from vendor claims.
