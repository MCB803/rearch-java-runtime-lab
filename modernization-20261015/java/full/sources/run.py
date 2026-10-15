#!/usr/bin/env python3
"""Reproduce all order-workflow arms; failures are retained and abort publication."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import re
import shutil
import statistics
import subprocess
import tempfile
import time
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
FLAGS = ["-Xms128m", "-Xmx128m", "-XX:+UseG1GC"]
ARMS = {
    "legacy-java8": dict(jdk=8, implementation="legacy", executor="platform", limit=8),
    "runtime-java25": dict(jdk=25, implementation="legacy", executor="platform", limit=8),
    "modern-platform-java25": dict(jdk=25, implementation="fanout", executor="platform", limit=64),
    "modern-virtual-java25": dict(jdk=25, implementation="fanout", executor="virtual", limit=64),
}


def now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def jdk(major):
    home = os.environ.get(f"REARCH_JDK{major}_HOME")
    if not home:
        home = subprocess.check_output(["/usr/libexec/java_home", "-v", "1.8" if major == 8 else str(major)], text=True).strip()
    details = subprocess.run([str(Path(home) / "bin/java"), "-XshowSettings:properties", "-version"], text=True, capture_output=True, check=True).stderr
    props = dict(re.findall(r"^\s*(java\.specification\.version|java\.runtime\.version|java\.vendor|os\.arch|java\.vm\.name)\s*=\s*(.+)$", details, re.M))
    if props.get("java.specification.version") != ("1.8" if major == 8 else str(major)):
        raise RuntimeError("Unexpected Java major version")
    return Path(home), props


def jobs(repeats=10, smoke=False):
    result = []
    for repeat in range(1, repeats + 1):
        for size in ([16] if smoke else [16, 64, 256]):
            for arm in ARMS:
                result.append(dict(arm=arm, size=size, serviceCapacity=64, repeat=repeat))
        if not smoke:
            for arm in ["legacy-java8", "modern-virtual-java25"]:
                result.append(dict(arm=arm, size=256, serviceCapacity=8, repeat=repeat))
    random.Random(20261015).shuffle(result)
    return result


def expected_outputs(size):
    # Independent Python oracle uses the business contract, not Java output/checksum.
    return [10000 + order * 17 + 300 + order % 13 * 19 if order * 7 % 31 else -1 for order in range(size)]


def validate(record, job):
    arm = ARMS[job["arm"]]
    for key in ["implementation", "executor", "limit"]:
        if record.get(key) != arm[key]:
            raise ValueError(f"Arm mismatch: {key}")
    if record.get("outputs") != expected_outputs(job["size"]):
        raise ValueError("Independent per-order result check failed")
    if record.get("size") != job["size"] or record.get("dependencyCalls") != job["size"] * 3 or record.get("errors") != 0:
        raise ValueError("Incomplete workload")
    if not 0 < record["p50Nanos"] <= record["p95Nanos"] <= record["p99Nanos"] <= record["elapsedNanos"]:
        raise ValueError("Invalid latency ordering")
    if record["processCpuNanos"] < 0 or record["warmupBatches"] < 1 or record["peakPlatformThreads"] < 1:
        raise ValueError("Invalid counters")


def summarize(records):
    experiments = []
    for capacity, identifier in [(64, "java-order-fanout"), (8, "java-dependency-bottleneck")]:
        points = []
        for size in sorted({row["size"] for row in records if row["serviceCapacity"] == capacity}):
            arms = []
            for arm in ARMS:
                rows = [row for row in records if row["serviceCapacity"] == capacity and row["size"] == size and row["arm"] == arm]
                if not rows:
                    continue
                times = [row["elapsedNanos"] / 1e6 for row in rows]
                arms.append(dict(id=arm, runs=len(rows), medianMs=statistics.median(times), minMs=min(times), maxMs=max(times),
                                 p95Ms=statistics.median(row["p95Nanos"] / 1e6 for row in rows),
                                 medianCpuMs=statistics.median(row["processCpuNanos"] / 1e6 for row in rows),
                                 peakPlatformThreads=statistics.median(row["peakPlatformThreads"] for row in rows),
                                 operations=size, dependencyCalls=size * 3, allOutputsVerified=True))
            points.append(dict(size=size, arms=arms))
        experiments.append(dict(id=identifier, pointUnit="orders", serviceCapacity=capacity, points=points))
    return dict(schemaVersion=1, measuredAt=now(), kind="synthetic-measured-lab", experiments=experiments)


def environment():
    result = dict(system=platform.system(), release=platform.release(), architecture=platform.machine(), logicalCpus=os.cpu_count())
    if platform.system() == "Darwin":
        for key in ["machdep.cpu.brand_string", "hw.memsize", "hw.physicalcpu"]:
            result[key] = subprocess.check_output(["/usr/sbin/sysctl", "-n", key], text=True).strip()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    (output / "logs").mkdir()
    (output / "sources").mkdir()
    runtimes = {major: jdk(major) for major in [8, 25]}
    source_files = [path for path in HERE.iterdir() if path.is_file() and path.suffix in [".java", ".py", ".md"]]
    source_hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in source_files}
    for path in source_files:
        shutil.copy2(path, output / "sources" / path.name)
    plan = jobs(1 if args.smoke else 10, args.smoke)
    manifest = dict(schemaVersion=1, status="running", startedAt=now(), profile="smoke" if args.smoke else "full",
                    hardware=environment(), jdks={str(major): props for major, (_, props) in runtimes.items()},
                    sourceSha256=source_hashes, jvmFlags=FLAGS, jobs=plan, warmupMinimumMs=100 if args.smoke else 2000,
                    repetitionsPerPoint=1 if args.smoke else 10, dependencyDelayMs=25,
                    dependencyContract="Three independent lookups per order: price cents, stock quantity, shipping cents. Same service code and delay in every arm. Each call uses a fresh loopback TCP socket; modeled dependency capacity is stated per experiment.",
                    outputContract="Per order: price + shipping when stock > 0; otherwise -1. All result arrays are independently verified in Python.",
                    environmentNotes=["Shared Apple developer workstation; desktop/browser/website may remain running", "Java and PHP/DB full measurement windows coordinated to avoid overlap", "Host load recorded for every run; no fixed CPU quota or memory RSS measurement"],
                    limitations=["Synthetic newly written legacy-pattern reproduction, not a customer migration", "25ms is a dependency model parameter, not measured third-party latency", "Primary comparison changes architecture and concurrency as well as runtime; runtime-only and same-concurrency platform controls are retained", "Virtual threads are not faster CPU threads; peakPlatformThreads counts JVM platform threads, not total virtual tasks", "p95Ms is median of per-run order completion p95, including batch queueing, not pooled p95", "No monetary cost, production traffic, security score or guaranteed improvement conclusion", "Installed Java 8 patch is old; this is not a comparison to current patched Java8", "Warmup stability and isolated production-hardware repeat remain outside this local experiment"])
    write_json(output / "manifest.json", manifest)
    records = []
    server = None
    try:
        with tempfile.TemporaryDirectory(prefix="rearch-java-workflow-") as temp:
            compile_result = subprocess.run([str(runtimes[8][0] / "bin/javac"), "-source", "8", "-target", "8", "-d", temp, str(HERE / "OrderWorkflow.java")], text=True, capture_output=True, timeout=30)
            (output / "logs/compile.txt").write_text(compile_result.stdout + compile_result.stderr)
            if compile_result.returncode:
                raise RuntimeError("Compilation failed")
            for sequence, job in enumerate(plan, 1):
                arm = ARMS[job["arm"]]
                with (output / f"logs/service-{sequence:03d}.txt").open("w") as service_log:
                    server = subprocess.Popen([str(runtimes[25][0] / "bin/java"), *FLAGS, "-cp", temp, "OrderWorkflow", "serve", str(job["serviceCapacity"]), "25"], text=True, stdout=subprocess.PIPE, stderr=service_log)
                    # Startup bounded separately without persisting local filesystem paths.
                    import select
                    if not select.select([server.stdout], [], [], 10)[0]:
                        raise RuntimeError("Dependency startup timeout")
                    port = int(server.stdout.readline().strip())
                    load_before = os.getloadavg()
                    command = [str(runtimes[arm["jdk"]][0] / "bin/java"), *FLAGS, "-cp", temp, "OrderWorkflow", arm["implementation"], arm["executor"], str(arm["limit"]), str(job["size"]), str(port), str(manifest["warmupMinimumMs"])]
                    result = subprocess.run(command, text=True, capture_output=True, timeout=40)
                    write_json(output / f"logs/run-{sequence:03d}.json", dict(returncode=result.returncode, stdout=result.stdout, stderr=result.stderr))
                    if result.returncode:
                        raise RuntimeError(f"Run {sequence} failed; complete output retained")
                    record = json.loads(result.stdout)
                    validate(record, job)
                    record.update(job)
                    record.update(sequence=sequence, recordedAt=now(), jdk=arm["jdk"], hostLoadBefore=load_before, hostLoadAfter=os.getloadavg())
                    records.append(record)
                    with (output / "raw.jsonl").open("a") as raw:
                        raw.write(json.dumps(record, separators=(",", ":")) + "\n")
                    server.terminate()
                    server.wait(timeout=5)
                    server = None
                    print(f"[{sequence}/{len(plan)}] {job['arm']} size={job['size']} capacity={job['serviceCapacity']} {record['elapsedNanos'] / 1e6:.2f}ms; all outputs correct", flush=True)
            manifest["status"] = "completed"
    except BaseException as error:
        manifest["status"] = "failed"
        manifest["failure"] = type(error).__name__ + ": " + str(error)
        raise
    finally:
        if server is not None:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()
        manifest.update(finishedAt=now(), completedRuns=len(records), plannedRuns=len(plan))
        write_json(output / "manifest.json", manifest)
        if records:
            write_json(output / "summary.json", summarize(records))
            columns = [key for key in records[0] if key not in ["outputs", "hostLoadBefore", "hostLoadAfter"]]
            with (output / "raw.csv").open("w", newline="") as file:
                writer = csv.DictWriter(file, fieldnames=columns)
                writer.writeheader()
                writer.writerows({key: row[key] for key in columns} for row in records)
        write_json(output / "SHA256.json", {str(path.relative_to(output)): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(output.rglob("*")) if path.is_file() and path.name != "SHA256.json"})


if __name__ == "__main__":
    main()
