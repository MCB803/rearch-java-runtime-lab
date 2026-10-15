import hashlib
import struct
import unittest
import run


class HarnessTests(unittest.TestCase):
    def test_complete_fixed_matrix(self):
        plan = run.jobs()
        self.assertEqual(plan, run.jobs())
        self.assertEqual(len(plan), 108)
        self.assertTrue(all(row["warmup"] for row in plan[:18]))
        self.assertTrue(all(not row["warmup"] for row in plan[18:]))
        for size in run.SIZES:
            for arm in run.ARMS:
                self.assertEqual(sorted(row["repeat"] for row in plan if row["arm"] == arm and row["size"] == size and not row["warmup"]), list(range(1, 11)))

    def test_independent_oracle_examples(self):
        expected = [-1, (1000 + 7919 * 37 % 100000) * 2]
        result = run.oracle(2)
        self.assertEqual(result["resultHash"], hashlib.sha256(struct.pack("<qq", *expected)).hexdigest())
        self.assertEqual(result["missing"], 1)
        self.assertEqual(result["sumCents"], expected[1])

    def test_wrong_hash_and_omitted_index_cost_rejected(self):
        job = dict(arm="modern-dictionary", size=1000, repeat=1, warmup=False)
        record = dict(**job, **run.oracle(1000), errors=0, catalogSize=10000, elapsedNanos=1000,
                      processCpuNanos=0, allocatedBytes=1000, indexBuildNanos=500,
                      architecture="Arm64", runtimeVersion=".NET 10.0.0")
        run.validate(record, job)
        for key, value in [("resultHash", "wrong"), ("outputCount", 999), ("indexBuildNanos", 1001), ("architecture", "X64"), ("errors", 1)]:
            wrong = record.copy()
            wrong[key] = value
            with self.assertRaises(ValueError):
                run.validate(wrong, job)


if __name__ == "__main__":
    unittest.main()
