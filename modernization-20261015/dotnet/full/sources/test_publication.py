import csv
import hashlib
import json
from pathlib import Path
import unittest
import run

DATA = Path(__file__).resolve().parents[4] / "public/labs/modernization-20261015/dotnet/full"


class PublicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((DATA / "manifest.json").read_text())
        cls.records = [json.loads(line) for line in (DATA / "raw.jsonl").read_text().splitlines()]

    def test_complete_matrix_and_all_output_hashes(self):
        self.assertEqual(self.manifest["status"], "completed")
        self.assertEqual(self.manifest["completedRuns"], 90)
        self.assertEqual(self.manifest["completedWarmups"], 18)
        self.assertEqual(self.manifest["jobs"], run.jobs())
        self.assertEqual(len(self.records), 108)
        for sequence, (record, job) in enumerate(zip(self.records, run.jobs()), 1):
            self.assertEqual(record["sequence"], sequence)
            run.validate(record, job)

    def test_all_summary_values_recomputed(self):
        summary = json.loads((DATA / "summary.json").read_text())
        self.assertEqual(summary["experiments"], run.summarize(self.records)["experiments"])
        for point in summary["experiments"][0]["points"]:
            self.assertEqual(len(point["arms"]), 3)
            self.assertTrue(all(arm["runs"] == 10 for arm in point["arms"]))

    def test_source_and_data_hashes(self):
        for path, digest in json.loads((DATA / "SHA256.json").read_text()).items():
            self.assertEqual(hashlib.sha256((DATA / path).read_bytes()).hexdigest(), digest)
        for path, digest in self.manifest["sourceSha256"].items():
            self.assertEqual(hashlib.sha256((DATA / "sources" / path).read_bytes()).hexdigest(), digest)

    def test_csv_complete_and_stderr_empty(self):
        with (DATA / "raw.csv").open(newline="") as file:
            csv_rows = list(csv.DictReader(file))
        self.assertEqual(len(csv_rows), 108)
        for csv_row, raw in zip(csv_rows, self.records):
            self.assertEqual(int(csv_row["elapsedNanos"]), raw["elapsedNanos"])
            self.assertEqual(csv_row["resultHash"], raw["resultHash"])
        self.assertEqual((DATA / "logs/process-stderr.txt").read_text(), "")


if __name__ == "__main__":
    unittest.main()
