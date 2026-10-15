#!/usr/bin/env python3
"""Reproduce in a new output directory; never overwrite the recorded publication."""
import argparse
import pathlib
import subprocess
import sys

IMAGE = 'php@sha256:1d2cf2b7d715b5b3aa959f0150ccbcc7b71e0181b637e443abf40a7fb56bf79a'
HERE = pathlib.Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('--output', type=pathlib.Path, required=True)
args = parser.parse_args()
output = args.output.resolve()
output.mkdir(parents=True, exist_ok=False)
base = ['docker', 'run', '--rm', '--network', 'none', '--platform', 'linux/arm64', '--cpus', '2',
        '--memory', '1g', '-v', f'{HERE}:/lab:ro', IMAGE, 'php', '-d', 'memory_limit=768M']
subprocess.run(base + ['/lab/test_harness.php'], check=True)
with (output / 'raw.jsonl').open('w') as raw:
    subprocess.run(base + ['/lab/benchmark.php'], check=True, stdout=raw)
subprocess.run([sys.executable, str(HERE / 'summarize.py'), '--directory', str(output)], check=True)
