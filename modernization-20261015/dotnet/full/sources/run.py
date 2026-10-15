#!/usr/bin/env python3
"""Run the complete, fixed .NET catalog-import benchmark in an official SDK image."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import shutil
import statistics
import struct
import subprocess
import tempfile
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
ARMS = ["legacy-linear", "modern-dictionary", "modern-frozen"]
SIZES = [1000, 10000, 50000]
IMAGE = "mcr.microsoft.com/dotnet/sdk:10.0"


def now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def jobs():
    warmups = [dict(arm=arm, size=size, repeat=repeat, warmup=True)
               for repeat in [1, 2] for size in SIZES for arm in ARMS]
    measured = [dict(arm=arm, size=size, repeat=repeat, warmup=False)
                for repeat in range(1, 11) for size in SIZES for arm in ARMS]
    random.Random(20261015).shuffle(warmups)
    random.Random(20261016).shuffle(measured)
    return warmups + measured


def oracle(size):
    values = [-1 if i % 17 == 0 else (1000 + (((i * 7919) % 10000) * 37) % 100000) * (i % 5 + 1) for i in range(size)]
    digest = hashlib.sha256(b"".join(struct.pack("<q", value) for value in values)).hexdigest()
    return dict(resultHash=digest, outputCount=size, missing=sum(value == -1 for value in values), sumCents=sum(value for value in values if value >= 0))


def validate(record, job):
    for key, value in job.items():
        if record.get(key) != value:
            raise ValueError("Job mismatch: " + key)
    for key, value in oracle(job["size"]).items():
        if record.get(key) != value:
            raise ValueError("Independent output check failed: " + key)
    if record.get("errors") != 0 or record.get("catalogSize") != 10000:
        raise ValueError("Invalid business counters")
    if record["elapsedNanos"] <= 0 or record["processCpuNanos"] < 0 or record["allocatedBytes"] < 0:
        raise ValueError("Invalid performance counters")
    if not 0 <= record["indexBuildNanos"] <= record["elapsedNanos"]:
        raise ValueError("Invalid inclusive index timing")
    if record["architecture"] != "Arm64" or not record["runtimeVersion"].startswith(".NET 10."):
        raise ValueError("Unexpected measured runtime")


def summarize(records):
    points = []
    for size in SIZES:
        arms = []
        for arm in ARMS:
            rows = [r for r in records if r["size"] == size and r["arm"] == arm and not r["warmup"]]
            times = [r["elapsedNanos"] / 1e6 for r in rows]
            if rows:
                arms.append(dict(id=arm, runs=len(rows), medianMs=statistics.median(times), minMs=min(times), maxMs=max(times),
                                 medianCpuMs=statistics.median(r["processCpuNanos"] / 1e6 for r in rows),
                                 medianAllocatedBytes=statistics.median(r["allocatedBytes"] for r in rows),
                                 medianIndexBuildMs=statistics.median(r["indexBuildNanos"] / 1e6 for r in rows),
                                 operations=size, allOutputsVerified=True))
        points.append(dict(size=size, arms=arms))
    return dict(schemaVersion=1, kind="synthetic-measured-lab", measuredAt=now(), experiments=[dict(id="dotnet-catalog-import", pointUnit="rows", catalogSize=10000, points=points)])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--image", default=IMAGE, help="Existing official SDK image or pinned digest; no automatic pull")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    (output / "sources").mkdir()
    (output / "logs").mkdir()
    plan = jobs()
    image = json.loads(subprocess.check_output(["docker", "image", "inspect", args.image], text=True))[0]
    if image["Architecture"] != "arm64":
        raise RuntimeError("Expected native arm64 image")
    sources = [p for p in HERE.iterdir() if p.is_file() and p.suffix in [".py", ".cs", ".csproj", ".md"]]
    for path in sources:
        shutil.copy2(path, output / "sources" / path.name)
    manifest = dict(schemaVersion=1, status="running", startedAt=now(), jobs=plan,
                    plannedRuns=90, plannedWarmups=18, repetitionsPerPoint=10,
                    sourceSha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
                    image=dict(reference=args.image, id=image["Id"], repoDigests=image["RepoDigests"], architecture=image["Architecture"]),
                    container=dict(platform="linux/arm64", cpus=1, memoryBytes=805306368, network="none", runtimeEnvironment={"DOTNET_TieredCompilation": "0", "DOTNET_CLI_TELEMETRY_OPTOUT": "1"}),
                    host=dict(system=platform.system(), release=platform.release(), architecture=platform.machine(), logicalCpus=os.cpu_count()),
                    catalogSize=10000, pointSizes=SIZES,
                    inputContract="Catalog SKU-00000..09999; price cents=1000+(id*37)%100000. Import row i uses missing key if i%17=0 else SKU-(i*7919)%10000; quantity=i%5+1. Output is price*quantity or -1 for missing.",
                    outputContract="SHA-256 of every output as signed little-endian 64-bit integer, plus count/missing/sum; independently verified in Python for every warmup and measured run",
                    metricScope="End-to-end import includes building a new index and allocating output array for every batch. Input creation and output hashing are outside every arm. CPU and allocations measured over same operation. No network/delay injected.",
                    limitations=["Synthetic import, not a migrated customer application", "All arms use the same .NET10 runtime; no .NET Framework versus10 or version-only speed claim", "Dictionary is available on older .NET versions; improvement is algorithm/data-structure choice", "FrozenDictionary construction overhead is included and all controls retained even if slower", "Managed allocated bytes are cumulative allocation during operation, not peak memory/RSS or a monetary saving", "Shared Apple host, Docker VM and1CPUquota; no claim of production-machine isolation", "Two warmups per point, tiered compilation disabled; startup and long-term JIT behavior excluded", "No security, web request, database, or cloud-bill improvement measured"])
    write_json(output / "manifest.json", manifest)
    write_json(output / "plan.json", plan)
    records = []
    benchmark_name = "rearch-dotnet-catalog-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    process = None
    try:
        with tempfile.TemporaryDirectory(prefix="rearch-dotnet-") as temp:
            temp_path = Path(temp)
            for name in ["Program.cs", "CatalogBench.csproj"]:
                shutil.copy2(HERE / name, temp_path / name)
            common = ["docker", "run", "--rm", "--network", "none", "--platform", "linux/arm64", "--cpus", "1", "--memory", "768m", "-e", "DOTNET_CLI_TELEMETRY_OPTOUT=1", "-e", "DOTNET_TieredCompilation=0", "-e", "DOTNET_NOLOGO=1", "-v", str(temp_path) + ":/work", "-w", "/work"]
            build = subprocess.run([*common, args.image, "dotnet", "build", "CatalogBench.csproj", "-c", "Release", "-o", "out", "--nologo", "-p:NuGetAudit=false", "--ignore-failed-sources"], text=True, capture_output=True, timeout=120)
            (output / "logs/build.txt").write_text(build.stdout + build.stderr)
            if build.returncode:
                raise RuntimeError("Build failed; log retained")
            manifest["assemblySha256"] = hashlib.sha256((temp_path / "out/CatalogBench.dll").read_bytes()).hexdigest()
            shutil.copy2(output / "plan.json", temp_path / "plan.json")
            sdk = subprocess.check_output([*common, args.image, "dotnet", "--info"], text=True, timeout=20)
            (output / "logs/runtime.txt").write_text(sdk)
            manifest["hostLoadBefore"] = os.getloadavg()
            with (output / "logs/process-stderr.txt").open("w") as stderr:
                process = subprocess.Popen([*common, "--name", benchmark_name, args.image, "dotnet", "out/CatalogBench.dll", "plan.json"], text=True, stdout=subprocess.PIPE, stderr=stderr)
                for sequence, line in enumerate(process.stdout, 1):
                    with (output / "logs/process-stdout.jsonl").open("a") as log:
                        log.write(line)
                    record = json.loads(line)
                    if sequence > len(plan):
                        raise RuntimeError("Unexpected extra run")
                    validate(record, plan[sequence - 1])
                    record.update(sequence=sequence, recordedAt=now(), hostLoad=os.getloadavg())
                    records.append(record)
                    with (output / "raw.jsonl").open("a") as raw:
                        raw.write(json.dumps(record, separators=(",", ":")) + "\n")
                    print(f"[{sequence}/{len(plan)}] {'warmup' if record['warmup'] else 'measured'} {record['arm']} {record['size']}rows {record['elapsedNanos']/1e6:.3f}ms; hash verified", flush=True)
                code = process.wait(timeout=10)
                if code or len(records) != len(plan):
                    raise RuntimeError(f"Benchmark incomplete: exit={code}, records={len(records)}")
            manifest.update(status="completed", runtimeVersion=records[0]["runtimeVersion"], measuredOs=records[0]["osDescription"])
    except BaseException as error:
        manifest.update(status="failed", failure=type(error).__name__ + ": " + str(error))
        raise
    finally:
        if process is not None and process.poll() is None:
            subprocess.run(["docker", "rm", "-f", benchmark_name], text=True, capture_output=True, timeout=20)
            process.wait(timeout=20)
        manifest.update(finishedAt=now(), hostLoadAfter=os.getloadavg(), completedRuns=sum(not r["warmup"] for r in records), completedWarmups=sum(r["warmup"] for r in records))
        write_json(output / "manifest.json", manifest)
        if records:
            write_json(output / "summary.json", summarize(records))
            columns = [key for key in records[0] if key != "hostLoad"]
            with (output / "raw.csv").open("w", newline="") as file:
                writer = csv.DictWriter(file, fieldnames=columns)
                writer.writeheader()
                writer.writerows({key: row[key] for key in columns} for row in records)
        write_json(output / "SHA256.json", {str(p.relative_to(output)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(output.rglob("*")) if p.is_file() and p.name != "SHA256.json"})


if __name__ == "__main__":
    main()
