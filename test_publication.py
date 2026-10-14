import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('publication', Path(__file__).with_name('prepare_publication.py'))
publication = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publication)


class PublicationTests(unittest.TestCase):
    def test_failed_partial_and_smoke_datasets_cannot_publish(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for status, profile, runs in [('failed', 'full-pilot', 2), ('running', 'full-pilot', 439), ('completed', 'smoke', 14), ('completed', 'full-pilot', 439)]:
                (root / 'manifest.json').write_text(json.dumps({'status': status, 'profile': profile, 'completedRuns': runs}))
                with self.assertRaises(ValueError):
                    publication.verify(root)

    def test_distribution_retains_slow_outliers_and_all_ten_runs(self):
        result = publication.distribution([1, 2, 3, 4, 5, 6, 7, 8, 9, 1000])
        self.assertEqual(result['n'], 10)
        self.assertEqual(result['min'], 1)
        self.assertEqual(result['median'], 5.5)
        self.assertEqual(result['max'], 1000)

    def test_path_redaction_preserves_runtime_and_numeric_evidence(self):
        source = f'{Path.home()}/project/run.py {Path.home()}/jdk/bin/java 25.0.3+9-LTS 1.8.0_432-b06 137 4.2'
        cleaned = publication.redact(source, Path.home() / 'project')
        self.assertEqual(cleaned, '$WORKSPACE/run.py $HOME/jdk/bin/java 25.0.3+9-LTS 1.8.0_432-b06 137 4.2')

    def test_evidence_copy_keeps_raw_csv_line_endings_and_values_byte_exact(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, destination = root / 'original', root / 'public'
            source.mkdir()
            raw = b'jdk,size,elapsedNanos\r\n8,1000000,1000001234\r\n25,1000000,1000002345\r\n'
            (source / 'raw.csv').write_bytes(raw)
            (source / 'manifest.json').write_bytes((f'{{"home":"{Path.home()}/jdk"}}\r\n').encode())
            (source / 'SHA256.json').write_text(json.dumps({'raw.csv': publication.sha(source / 'raw.csv')}))
            changed = publication.copy_evidence(source, destination, root)
            self.assertEqual((destination / 'raw.csv').read_bytes(), raw)
            self.assertEqual(publication.sha(destination / 'raw.csv'), publication.sha(source / 'raw.csv'))
            self.assertEqual((destination / 'manifest.json').read_bytes(), b'{"home":"$HOME/jdk"}\r\n')
            self.assertEqual(changed, ['manifest.json'])


if __name__ == '__main__':
    unittest.main()
