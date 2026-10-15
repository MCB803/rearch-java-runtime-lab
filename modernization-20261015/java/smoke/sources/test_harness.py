import copy
import unittest
import run


class ProtocolTests(unittest.TestCase):
    def test_full_matrix_keeps_controls_and_ten_repeats(self):
        jobs = run.jobs()
        self.assertEqual(len(jobs), 140)
        for arm in run.ARMS:
            for size in [16, 64, 256]:
                rows = [job for job in jobs if job["arm"] == arm and job["size"] == size and job["serviceCapacity"] == 64]
                self.assertEqual(sorted(row["repeat"] for row in rows), list(range(1, 11)))
        self.assertEqual(sum(job["serviceCapacity"] == 8 for job in jobs), 20)
        self.assertEqual(jobs, run.jobs())

    def test_runtime_control_changes_only_java(self):
        baseline, control = run.ARMS["legacy-java8"].copy(), run.ARMS["runtime-java25"].copy()
        del baseline["jdk"]
        del control["jdk"]
        self.assertEqual(baseline, control)

    def test_modern_platform_control_changes_only_executor(self):
        platform, virtual = run.ARMS["modern-platform-java25"].copy(), run.ARMS["modern-virtual-java25"].copy()
        del platform["executor"]
        del virtual["executor"]
        self.assertEqual(platform, virtual)

    def test_oracle_rejects_a_wrong_individual_order(self):
        job = dict(arm="legacy-java8", size=16, serviceCapacity=64, repeat=1)
        record = dict(implementation="legacy", executor="platform", limit=8, size=16,
                      outputs=run.expected_outputs(16), dependencyCalls=48, errors=0,
                      elapsedNanos=100, p50Nanos=50, p95Nanos=90, p99Nanos=95,
                      processCpuNanos=10, warmupBatches=1, peakPlatformThreads=10)
        run.validate(record, job)
        for key, value in [("dependencyCalls", 47), ("errors", 1), ("size", 15), ("p99Nanos", 101), ("executor", "virtual")]:
            changed = copy.deepcopy(record)
            changed[key] = value
            with self.assertRaises(ValueError):
                run.validate(changed, job)
        changed = copy.deepcopy(record)
        changed["outputs"][1] += 1
        with self.assertRaises(ValueError):
            run.validate(changed, job)

    def test_oracle_business_examples(self):
        self.assertEqual(run.expected_outputs(3), [-1, 10336, 10372])
        self.assertEqual(run.expected_outputs(32)[31], -1)


if __name__ == "__main__":
    unittest.main()
