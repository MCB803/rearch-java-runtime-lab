# Complete results · 14 October 2026

440 fresh JVM runs; all 44 groups have ten repetitions. No completed-matrix outliers were removed. Each batch duration is elapsedNanos/batches. Per-run p95 is a separate measure, not this batch duration.

Group keys are `task / Java major / executor / concurrent-job permit budget / size`. For `report`, size is the number of generated order records; the report is single-threaded and does not use the executor/permit fields. For `io` and `cpu`, size is the number of jobs submitted together, not a human-user count. Compare platform and virtual arms at the same budget; changing 16 to 128 also changes the configuration. The 32-worker dependency remains shared and bounded.

| Group | n | Median batch ms | Min ms | Max ms |
| --- | ---: | ---: | ---: | ---: |
| cpu/25/platform/128/16 | 10 | 0.258386 | 0.252547 | 0.351214 |
| cpu/25/platform/128/256 | 10 | 2.586660 | 2.414088 | 2.757551 |
| cpu/25/platform/128/64 | 10 | 0.696346 | 0.671145 | 1.137282 |
| cpu/25/platform/16/16 | 10 | 0.253630 | 0.240509 | 0.282277 |
| cpu/25/platform/16/256 | 10 | 2.618744 | 2.439468 | 4.397104 |
| cpu/25/platform/16/64 | 10 | 0.731186 | 0.660037 | 0.898924 |
| cpu/25/virtual/128/16 | 10 | 0.235465 | 0.231270 | 0.279491 |
| cpu/25/virtual/128/256 | 10 | 2.477463 | 2.389467 | 2.723509 |
| cpu/25/virtual/128/64 | 10 | 0.683751 | 0.648751 | 0.753955 |
| cpu/25/virtual/16/16 | 10 | 0.232383 | 0.229906 | 0.250331 |
| cpu/25/virtual/16/256 | 10 | 2.497411 | 2.429857 | 2.646646 |
| cpu/25/virtual/16/64 | 10 | 0.651633 | 0.627028 | 0.685959 |
| cpu/8/platform/16/16 | 10 | 0.250809 | 0.243616 | 0.271100 |
| cpu/8/platform/16/256 | 10 | 2.499851 | 2.413733 | 2.865716 |
| cpu/8/platform/16/64 | 10 | 0.690485 | 0.655649 | 0.793534 |
| io/25/platform/128/16 | 10 | 31.256466 | 25.528824 | 32.147415 |
| io/25/platform/128/256 | 10 | 220.082658 | 198.103757 | 221.332825 |
| io/25/platform/128/64 | 10 | 60.785087 | 51.694854 | 61.689225 |
| io/25/platform/16/16 | 10 | 31.098427 | 26.787135 | 32.210388 |
| io/25/platform/16/256 | 10 | 438.212653 | 400.249889 | 456.936264 |
| io/25/platform/16/64 | 10 | 114.673713 | 102.658354 | 119.196389 |
| io/25/virtual/128/16 | 10 | 31.106123 | 25.979681 | 31.770366 |
| io/25/virtual/128/256 | 10 | 221.106179 | 197.909292 | 231.897883 |
| io/25/virtual/128/64 | 10 | 60.938828 | 51.573190 | 62.115056 |
| io/25/virtual/16/16 | 10 | 30.891831 | 30.355924 | 32.785769 |
| io/25/virtual/16/256 | 10 | 430.668535 | 399.016639 | 448.168194 |
| io/25/virtual/16/64 | 10 | 115.549574 | 103.690721 | 120.281028 |
| io/8/platform/16/16 | 10 | 31.601590 | 30.515121 | 32.539417 |
| io/8/platform/16/256 | 10 | 454.719750 | 403.454111 | 501.552792 |
| io/8/platform/16/64 | 10 | 119.495336 | 101.924288 | 128.439849 |
| report/25/platform/16/1000 | 10 | 0.002028 | 0.001997 | 0.002112 |
| report/25/platform/16/10000 | 10 | 0.019123 | 0.018906 | 0.019413 |
| report/25/platform/16/100000 | 10 | 0.188546 | 0.177775 | 0.192070 |
| report/25/platform/16/1000000 | 10 | 1.885570 | 1.847547 | 1.919677 |
| report/25/platform/16/5000 | 10 | 0.009582 | 0.009468 | 0.010829 |
| report/25/platform/16/50000 | 10 | 0.094554 | 0.089464 | 0.096468 |
| report/25/platform/16/500000 | 10 | 0.945333 | 0.918494 | 1.088696 |
| report/8/platform/16/1000 | 10 | 0.002035 | 0.001995 | 0.002209 |
| report/8/platform/16/10000 | 10 | 0.019108 | 0.019009 | 0.019771 |
| report/8/platform/16/100000 | 10 | 0.189190 | 0.186374 | 0.216961 |
| report/8/platform/16/1000000 | 10 | 1.891159 | 1.875471 | 1.910492 |
| report/8/platform/16/5000 | 10 | 0.009633 | 0.009059 | 0.009849 |
| report/8/platform/16/50000 | 10 | 0.094800 | 0.093792 | 0.098847 |
| report/8/platform/16/500000 | 10 | 0.952238 | 0.919768 | 1.128951 |

All raw measurements and distribution summaries are in data/2026-10-14. The initial failed 2 ms attempt is retained separately and not pooled.
