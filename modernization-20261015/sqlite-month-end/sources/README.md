# Month-end customer balances: 100,000 to 5,000,000 orders

This is a new, preregistered synthetic workload. It does not replace or selectively extend the earlier 200-customer/200,000-order experiment. `protocol.json` fixes the three sizes, 500 customer accounts, three query arms, two warmups and ten measured repetitions before the first full run.

The business task is a month-end open-order balance report for all 500 customers. The before and after arms execute **identical correlated SQL**, returning identical integer-cent balances in customer order. The only SQL access change is a covering index on `(customer_id, status, total_cents)`. A grouped-query rewrite is also retained as a control, including if it loses to the indexed correlated query.

Both run on SQLite 3.46.1 through PHP 8.4.26 in the same native arm64 official image: `php@sha256:1d2cf2b7d715b5b3aa959f0150ccbcc7b71e0181b637e443abf40a7fb56bf79a`. Host: Apple M3, Mac15,3, 8 cores, 24 GiB RAM, macOS 26.5.2 arm64, Docker Desktop engine 27.4.0. Each container receives a 2-CPU quota and 1 GiB RAM, PHP limit 768 MiB, OPcache/JIT off, and no network. No runtime/version or hardware difference is credited as a gain.

For each size, deterministic orders are streamed into two fresh independent in-memory databases; no multi-million-row PHP array is held. Each customer's status varies over its history. Both copies have the same input hash. A PHP aggregation computed during generation acts as a full-row oracle; Python independently reconstructs all balances after the run. Each of 108 samples includes all 500 output rows, their hash, wall duration, process CPU, run number, arm and warmup flag. All 90 measurements and all 18 warmups are retained.

The measured read region includes SQL execution and complete result materialization. It excludes process startup, data generation/loading, index construction, correctness checking and JSON serialization. Those setup times and SQLite page allocation before/after index creation are recorded separately. Database connections stay warm across repeated reads. Arm order rotates deterministically every round. These are warm in-memory reports; disk latency, network, customer production SLAs, ongoing writes, index maintenance under writes, monetary savings and energy use were not measured.

`hrtime(true)` supplies monotonic wall time; `getrusage()` supplies user + system process CPU. CPU instrumentation spans a few extra instructions. Ten-run medians are used; nearest-rank sample p95 is the sample maximum at n=10, not a production request-tail claim. Full table scans may dominate this constructed missing-index case; an already well-indexed system is expected to gain much less. No artificial waiting, minimum duration, target speedup or chosen winning repetitions is used.

Run on an arm64 Docker host with Python 3:

```sh
python3 run.py --output /tmp/rearch-month-end-new-run
REARCH_SQLITE_MONTH_END_DATA=/tmp/rearch-month-end-new-run python3 -m unittest discover -s . -p 'test_publication.py' -v
```

The output directory must be new. The immutable source copy, protocol, complete raw observations, query plans, summary, manifest, stdout/stderr and SHA-256 inventory are saved together. A failed correctness check aborts publication. The source comparison in acceptance tests detects code changes after measurement.

Primary mechanism references: [SQLite query planning](https://www.sqlite.org/queryplanner.html), [PHP monotonic timer](https://www.php.net/manual/en/function.hrtime.php), [PHP PDO statements](https://www.php.net/manual/en/pdo.prepared-statements.php), checked 15 October 2026. Numerical claims must be derived from the resulting `raw.jsonl`; this README intentionally does not predict them.
