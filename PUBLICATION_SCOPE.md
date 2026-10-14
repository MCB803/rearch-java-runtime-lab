# Publication scope · 14 October 2026

This study can support a narrowly described, measured **synthetic runtime and executor laboratory case**. It does not satisfy a claim that a historical application or customer's software was migrated. The owner requested real measurement and launch; the publication workflow explicitly selected this smaller scope rather than relabeling the previous Access fixture.

The complete matrix was started only after the report at **1,000,000 records** was fixed as the primary metric. That selection is recorded in the README copied into the measured run's `sources/` folder before compilation. All seven report sizes and all thirty I/O/CPU control groups are retained alongside the primary result.

Acceptance for this scope:

1. The entire fixed-order matrix completes: 440 fresh JVM processes, 44 groups, ten repetitions in each group.
2. Every Java result agrees with the independent Python oracle. Per-process stdout, raw rows and calculated summaries agree. No failed or slow repetition is removed from the completed matrix.
3. All source hashes, exact installed runtime builds, hardware, JVM flags, windows, host-load observations and protocol changes remain available.
4. The failed first attempt remains available separately. Its results are not pooled with the amended experiment. Smoke outputs are not performance evidence.
5. Public copies remove identifying local path prefixes only. Numeric raw data stays byte-for-byte unchanged; original and public hashes are recorded.
6. Publication text names the shared workstation and different patch vintages. It makes no production-capacity, customer, monetary saving, security-improvement or universal Java speedup claim.
7. The before/after media show the real result viewer. They are not fabricated screenshots of a historic application.
8. Recorded automation wall time is distinguished from human effort. Human hours are unknown and represented as null.
9. The public repository contains the complete source and reproducibility commands, an MIT license, the successful raw dataset, the failed attempt and the separate publication review.
10. The data-volume replay uses measured durations unchanged. No synthetic extrapolation, stretched timing or job-to-human-user relabeling is introduced.

The runner's `publishable: false` is retained in every raw file: an automated run cannot approve its own publication. `publication-review.json` separately reports the complete-dataset integrity checks and the limited scope approved by the publication workflow. This does not retroactively turn the smoke test into a publishable benchmark, or assert that the fixed five-second warmup establishes full JIT steady state.

The public report is an exploratory, reproducible measurement on this workstation. Production sizing and investment decisions need the actual application's workload and operating conditions.
