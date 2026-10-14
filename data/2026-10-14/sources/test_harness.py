import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("pilot", Path(__file__).with_name("run.py"))
pilot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pilot)


class HarnessTests(unittest.TestCase):
    def test_full_matrix_has_seven_sizes_and_ten_independent_runs(self):
        jobs = pilot.matrix(True)
        for jdk in [8, 25]:
            rows = [job for job in jobs if job["task"] == "report" and job["jdk"] == jdk]
            self.assertEqual(len(rows), 70)
            for size in pilot.REPORT_SIZES:
                self.assertEqual(sorted(row["repeat"] for row in rows if row["size"] == size), list(range(1, 11)))
        self.assertEqual(len(jobs), 440)

    def test_smoke_is_explicitly_small(self):
        self.assertEqual(len(pilot.matrix(False)), 14)
        self.assertEqual(pilot.matrix(False), pilot.matrix(False))

    def test_platform_control_exists_for_every_virtual_limit(self):
        for task in ["cpu", "io"]:
            for limit in [16, 128]:
                variants = {job["executor"] for job in pilot.matrix(False) if job["task"] == task and job["jdk"] == 25 and job["limit"] == limit}
                self.assertEqual(variants, {"platform", "virtual"})

    def test_independent_cpu_oracle_matches_small_iterative_reference(self):
        expected = 0
        for index in range(3):
            value = index + 1
            for _ in range(20000):
                value = value * 48271 % 2147483647
            expected += value
        self.assertEqual(pilot.expected_checksum("cpu", 3), expected)

    def test_invalid_checksum_and_claim_flag_are_rejected(self):
        job = dict(task="io", executor="platform", size=2, limit=16)
        record = {**job, "checksum": 39, "publishable": False, "errors": 0, "p50Nanos": 1, "p95Nanos": 2, "p99Nanos": 3, "batches": 1, "operations": 2, "elapsedNanos": 4, "processCpuNanos": 1}
        pilot.validate(record, job)
        for altered in [{"checksum": 38}, {"publishable": True}, {"p95Nanos": 0}, {"operations": 1}, {"errors": 1}]:
            with self.assertRaises(ValueError):
                pilot.validate({**record, **altered}, job)


if __name__ == "__main__":
    unittest.main()
