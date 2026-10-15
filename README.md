# ReArch Labs · Java 8 / Java 25 runtime experiment

## Additional implementation experiments · 15 October 2026

The [modernization laboratory index](modernization-20261015/README.md) adds six completed experiments: [Java order integration](modernization-20261015/java/README.md), [PHP report computation](modernization-20261015/data/README.md), [SQLite report indexing](modernization-20261015/data/README.md), [.NET catalog matching](modernization-20261015/dotnet/README.md), [browser invoice-list rendering](modernization-20261015/frontend/README.md), and [SQLite month-end reporting across up to five million records](modernization-20261015/sqlite-month-end/sources/README.md).

These investigate implementation and data-access changes in different synthetic workflows. Their gains are not substitutes for the same-bytecode runtime comparison below. The original 440-run experiment, its raw measurements and its approximately 0.3% primary difference remain unchanged. In the new Java workflow, an unchanged-code runtime arm and a platform-thread concurrency control separate the effects of the changes; the PHP, SQLite and .NET experiments keep their respective runtime versions fixed.

## Original runtime experiment

A newly written synthetic workload, the same Java 8 bytecode, and two installed native arm64 runtimes. This repository contains the harness and every raw measurement from the completed, reviewed matrix. It does not contain customer data or claim a historical application migration.

## Reproduce

Requirements: Python 3 (standard library only), a Java 8 JDK, a Java 25 JDK. No downloads, dependencies, containers, paid resources or public network services are needed. All I/O uses a temporary server bound to `127.0.0.1`.

From the repository root:

```sh
python3 -m unittest discover -s docs/labs/java-modernization -p 'test_*.py' -v
python3 docs/labs/java-modernization/run.py --inspect
python3 docs/labs/java-modernization/run.py --smoke --output artifacts/smoke-local
```

For the complete 440 fresh-JVM matrix (roughly 45–50 minutes):

```sh
python3 docs/labs/java-modernization/run.py --full --output artifacts/full-local
```

The output directory must not already exist. `REARCH_JDK8_HOME` and `REARCH_JDK25_HOME` select existing JDK installations. No system settings or unrelated processes are changed.

## Measured environment

The completed dataset used one shared **Apple M3 workstation, 8 cores, 24 GiB RAM, Darwin 25.5.0, native arm64**. Exact runtimes: Amazon Corretto **1.8.0_432-b06** and **25.0.3+9-LTS**, running the same bytecode compiled once with Java 8. Both clients used `-Xms256m -Xmx256m -XX:+UseG1GC`. The older Java 8 patch is not described as current; patch and major-version effects are not isolated.

The loopback dependency ran on Java 25 with **32 platform workers** and a configured **20 ms sleep per request**, using a fresh server/port for each client JVM. It shares the workstation CPU; it is not an external production service. A browser and development server remained open. One-minute host load ranged from **2.56 to 21.14**; every before/after observation is in the raw rows. See [the manifest](data/2026-10-14/manifest.json) and [publication review](data/2026-10-14/publication-review.json).

## What is compared

- Order report: 7 record counts × 10 independent JVM runs × 2 runtimes.
- Blocking loopback I/O and CPU control: batch sizes 16, 64 and 256 × 10 runs × five arms: Java 8 platform/16, Java 25 platform/16, Java 25 virtual/16, Java 25 platform/128 and Java 25 virtual/128. The final number is the concurrent-job permit budget, not a human-user count.
- Every run checks the exact output against an independent Python oracle.
- Five seconds of warmup and at least one second of measurement per fresh JVM. These windows do not establish full JIT steady state.
- The primary metric was fixed before the complete results were available: median batch duration of the report over 1,000,000 generated orders.

These are batch jobs, not simultaneous human users. Platform and virtual threads are compared at the same concurrency budgets to separate executor choice from a larger work budget. A desktop runtime experiment cannot establish production infrastructure cost, customer latency, security improvement or a universal Java migration benefit.

The runner marks all raw output `publishable: false` because automation does not grant publication approval. A separately reviewed complete dataset may be described with its scope and limitations; the original measurements and flags are preserved. No smoke data is used as a performance claim.

The initial complete-matrix attempt stopped at the third process because a 2 ms dependency exhausted macOS ephemeral TCP ports. That attempt is retained separately. Before the replacement run, every arm changed to a 20 ms controlled dependency delay and a fresh dependency server/port per client JVM. The 5s/1s windows, workload, JVM flags, matrix and fixed job order were retained. Failed-attempt measurements are not pooled with the replacement run.

See [the frozen protocol](docs/labs/java-modernization/README.md). The complete results are in [RESULTS.md](RESULTS.md), the raw dataset in [data/2026-10-14](data/2026-10-14), and the explicit publication scope in [PUBLICATION_SCOPE.md](PUBLICATION_SCOPE.md).

## Completed dataset

All 440 planned fresh-JVM runs completed with equal outputs and no process or dependency errors. At the preselected 1,000,000-record report point, median duration was **1.891159 ms** on Corretto 8u432 and **1.885570 ms** on Corretto 25.0.3. Every other point, all control arms and min/max distributions remain available.

The approximately 0.3% primary difference has overlapping run ranges and is not a material migration benefit by itself. This exploratory workstation study makes no statistical-significance claim.

The full matrix took 48.75 minutes of automation wall time; human working hours were not tracked. The result-viewer images are screenshots of this measured dataset, not fabricated historical application screens.

The frozen protocol README retains its pre-run preparation status and future-work notes as measurement provenance. Current acceptance is described in PUBLICATION_SCOPE.md and data/2026-10-14/publication-review.json. Original pilot flags remain false; this separate review approves only the stated synthetic runtime/executor scope, not a customer migration or universal speedup.
