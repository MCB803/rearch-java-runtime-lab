#!/usr/bin/env python3
"""Offline, opt-in Java pilot. All outputs remain non-publishable, including --full."""
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
import time
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
REPORT_SIZES = [1000, 5000, 10000, 50000, 100000, 500000, 1000000]
CONCURRENCY_SIZES = [16, 64, 256]
JVM_FLAGS = ["-Xms256m", "-Xmx256m", "-XX:+UseG1GC"]
LABEL = "LOCAL PILOT — NOT FOR PUBLICATION / YEREL PİLOT — YAYINLANMAZ"


def execute(command, **kwargs):
    return subprocess.run(command, text=True, capture_output=True, check=True, timeout=30, **kwargs)


def discover_jdk(major):
    variable = f"REARCH_JDK{major}_HOME"
    candidates = [Path(os.environ[variable])] if variable in os.environ else []
    if not candidates and platform.system() == "Darwin":
        probe = subprocess.run(["/usr/libexec/java_home", "-v", "1.8" if major == 8 else str(major)], text=True, capture_output=True)
        if probe.returncode == 0:
            candidates.append(Path(probe.stdout.strip()))
    if not candidates:
        for root in [Path("/usr/lib/jvm"), Path.home() / ".sdkman/candidates/java", Path.home() / "Library/Java/JavaVirtualMachines"]:
            if root.is_dir():
                for entry in root.iterdir():
                    candidates.extend([entry, entry / "Contents/Home"])
    for candidate in candidates:
        java, javac = candidate / "bin/java", candidate / "bin/javac"
        if not java.is_file() or not javac.is_file():
            continue
        try:
            details = execute([str(java), "-XshowSettings:properties", "-version"]).stderr
        except (OSError, subprocess.SubprocessError):
            continue
        match = re.search(r"java\.specification\.version\s*=\s*(\S+)", details)
        if match and match[1] == ("1.8" if major == 8 else str(major)):
            selected = {name: value for name, value in re.findall(r"^\s*(java\.runtime\.version|java\.vendor|os\.arch|java\.vm\.name)\s*=\s*(.+)$", details, re.M)}
            return {"home": str(candidate.resolve()), "properties": selected}
    raise RuntimeError(f"Java {major} JDK bulunamadı; {variable} ile mevcut JDK dizinini belirtin. Otomatik indirme yapılmaz.")


def matrix(full):
    jobs = []
    repetitions = 10 if full else 1
    for repeat in range(1, repetitions + 1):
        for size in REPORT_SIZES if full else [1000, 10000]:
            for jdk in [8, 25]:
                jobs.append(dict(task="report", jdk=jdk, executor="platform", size=size, limit=16, repeat=repeat))
        for task in ["io", "cpu"]:
            for size in CONCURRENCY_SIZES if full else [64]:
                # Same-limit controls separate runtime changes from concurrency-budget changes.
                for jdk, executor, limit in [(8, "platform", 16), (25, "platform", 16), (25, "virtual", 16), (25, "platform", 128), (25, "virtual", 128)]:
                    jobs.append(dict(task=task, jdk=jdk, executor=executor, size=size, limit=limit, repeat=repeat))
    random.Random(20261014).shuffle(jobs)
    return jobs


def expected_checksum(task, size):
    if task == "report":
        return sum(
            (((index * 37 + 101) % 99999) + 1) * ((index % 7) * 12 + (index % 365) // 31 + 1)
            for index in range(size) if index % 5 != 0
        )
    if task == "io":
        return 17 * size * (size - 1) // 2 + 11 * size
    if task == "cpu":
        multiplier = pow(48271, 20000, 2147483647)
        return sum(((index + 1) * multiplier) % 2147483647 for index in range(size))
    raise ValueError("Unknown task")


def validate(record, job):
    for key in ["task", "executor", "size", "limit"]:
        if record.get(key) != job[key]:
            raise ValueError(f"Workload metadata mismatch: {key}")
    if record.get("checksum") != expected_checksum(job["task"], job["size"]):
        raise ValueError("Independent output checksum mismatch")
    if record.get("publishable") is not False or record.get("errors") != 0:
        raise ValueError("Missing non-publication flag or task failure")
    if not 0 < record["p50Nanos"] <= record["p95Nanos"] <= record["p99Nanos"]:
        raise ValueError("Invalid latency quantiles")
    if record["batches"] < 1 or record["elapsedNanos"] <= 0 or record["processCpuNanos"] < 0:
        raise ValueError("Invalid measurement counters")
    factor = 1 if job["task"] == "report" else job["size"]
    if record["operations"] != record["batches"] * factor:
        raise ValueError("Operation count mismatch")


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def hardware():
    result = {"system": platform.system(), "release": platform.release(), "architecture": platform.machine(), "logicalCpus": os.cpu_count()}
    if platform.system() == "Darwin":
        for key in ["machdep.cpu.brand_string", "hw.memsize", "hw.physicalcpu"]:
            probe = subprocess.run(["/usr/sbin/sysctl", "-n", key], text=True, capture_output=True)
            if probe.returncode == 0:
                result[key] = probe.stdout.strip()
    return result


def summarize(records):
    groups = {}
    for record in records:
        key = "/".join(str(record[name]) for name in ["task", "jdk", "executor", "limit", "size"])
        groups.setdefault(key, []).append(record)
    return [{"group": key, "runs": len(rows),
             "medianBatchSeconds": statistics.median(row["elapsedNanos"] / row["batches"] / 1e9 for row in rows),
             "medianOperationsPerSecond": statistics.median(row["operations"] / (row["elapsedNanos"] / 1e9) for row in rows),
             "medianRunP95Seconds": statistics.median(row["p95Nanos"] / 1e9 for row in rows),
             "publishable": False} for key, rows in sorted(groups.items())]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--smoke", action="store_true", help="14 short correctness runs; default")
    selection.add_argument("--full", action="store_true", help="440 fresh-JVM runs, including 7 data sizes × 10 repetitions × 2 JDKs; still a pilot")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--inspect", action="store_true", help="Show runtime discovery and planned run count without compiling/running")
    args = parser.parse_args()
    jdks = {major: discover_jdk(major) for major in [8, 25]}
    jobs = matrix(args.full)
    if args.inspect:
        print(json.dumps({"jdks": jdks, "plannedRuns": len(jobs), "label": LABEL}, indent=2, ensure_ascii=False))
        return
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = args.output or HERE.parents[2] / "artifacts" / f"java-lab-{'full' if args.full else 'smoke'}-{stamp}"
    output.mkdir(parents=True, exist_ok=False)
    classes = output / "classes"
    classes.mkdir()
    (output / "logs").mkdir()
    (output / "sources").mkdir()
    source = HERE / "OrderBench.java"
    source_hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(HERE.iterdir()) if path.is_file()}
    for name in source_hashes:
        shutil.copy2(HERE / name, output / "sources" / name)
    compile_result = execute([str(Path(jdks[8]["home"]) / "bin/javac"), "-source", "8", "-target", "8", "-d", str(classes), str(source)])
    (output / "logs/compile.txt").write_text(compile_result.stdout + compile_result.stderr)
    manifest = {"label": LABEL, "publishable": False, "status": "running", "startedAt": datetime.now(timezone.utc).isoformat(),
                "profile": "full-pilot" if args.full else "smoke", "hardware": hardware(), "jdks": jdks,
                "jvmFlags": JVM_FLAGS, "sourceSha256": source_hashes, "jobs": jobs,
                "warmupMilliseconds": 5000 if args.full else 100, "measurementMilliseconds": 1000 if args.full else 150,
                "dependency": {"jdk": 25, "bind": "127.0.0.1", "workers": 32, "configuredDelayMilliseconds": 20, "lifecycle": "fresh dependency server and port for each client JVM"},
                "environmentNotes": ["Shared developer workstation; desktop browser and the existing website development server remain running", "Other project agents were asked to avoid heavy build and test work during measurement", "No unrelated process is stopped; host load averages are recorded before and after every run"],
                "limitations": ["Synthetic newly written harness, not a migrated customer or upstream application", "Warmup stability not established", "Loopback dependency shares host CPU", "No isolated CPU quota", "No RSS, GC pause distribution, cost or security conclusions", "Installed JDK patch currency not approved for publication"]}
    write_json(output / "manifest.json", manifest)
    server = None
    server_log = None
    records = []
    try:
        for index, job in enumerate(jobs, 1):
            # A new port per client process prevents TIME_WAIT from an earlier run
            # exhausting the host's ephemeral range in a later independent run.
            server_log = (output / f"logs/dependency-{index:04d}.txt").open("w")
            server = subprocess.Popen([str(Path(jdks[25]["home"]) / "bin/java"), *JVM_FLAGS, "-cp", str(classes), "OrderBench", "serve"], stdout=subprocess.PIPE, stderr=server_log, text=True)
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as reader:
                future = reader.submit(server.stdout.readline)
                try:
                    port_line = future.result(timeout=10)
                except concurrent.futures.TimeoutError:
                    server.kill()
                    raise RuntimeError("Dependency startup timed out")
            port = int(port_line.strip())
            if not 1 <= port <= 65535:
                raise ValueError("Invalid dependency port")
            command = [str(Path(jdks[job["jdk"]]["home"]) / "bin/java"), *JVM_FLAGS, "-cp", str(classes), "OrderBench", job["task"], job["executor"], str(job["size"]), str(job["limit"]), str(port), str(manifest["warmupMilliseconds"]), str(manifest["measurementMilliseconds"])]
            started = time.monotonic()
            load_before = os.getloadavg()
            try:
                result = subprocess.run(command, text=True, capture_output=True, timeout=60)
            except subprocess.TimeoutExpired as error:
                write_json(output / f"logs/run-{index:04d}.json", {"command": command, "timedOut": True, "limitSeconds": 60, "stdout": (error.stdout or b"").decode(errors="replace") if isinstance(error.stdout, bytes) else error.stdout, "stderr": (error.stderr or b"").decode(errors="replace") if isinstance(error.stderr, bytes) else error.stderr})
                raise
            write_json(output / f"logs/run-{index:04d}.json", {"command": command, "returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr, "processElapsedSeconds": time.monotonic() - started})
            if result.returncode != 0:
                raise RuntimeError(f"Run {index} failed; full failure output retained in logs")
            record = json.loads(result.stdout)
            validate(record, job)
            record.update(job)
            record["sequence"] = index
            record["recordedAt"] = datetime.now(timezone.utc).isoformat()
            for window, before, after in zip([1, 5, 15], load_before, os.getloadavg()):
                record[f"hostLoad{window}mBefore"] = before
                record[f"hostLoad{window}mAfter"] = after
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill(); server.wait()
            server_log.close()
            server = None
            server_log = None
            records.append(record)
            with (output / "raw.jsonl").open("a") as raw:
                raw.write(json.dumps(record) + "\n")
            print(f"[{index}/{len(jobs)}] checksum OK: {job['task']} JDK{job['jdk']} {job['executor']}/{job['limit']} size={job['size']}", flush=True)
        manifest["status"] = "completed"
    except BaseException as error:
        manifest["status"] = "failed"
        manifest["failure"] = str(error)
        raise
    finally:
        if server is not None:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill(); server.wait()
        if server_log is not None:
            server_log.close()
        manifest["finishedAt"] = datetime.now(timezone.utc).isoformat()
        manifest["completedRuns"] = len(records)
        write_json(output / "manifest.json", manifest)
        write_json(output / "summary.json", {"label": LABEL, "publishable": False, "groups": summarize(records)})
        if records:
            with (output / "raw.csv").open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=list(records[0]))
                writer.writeheader(); writer.writerows(records)
        checksums = {str(path.relative_to(output)): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(output.rglob("*")) if path.is_file() and "classes" not in path.relative_to(output).parts}
        write_json(output / "SHA256.json", checksums)
    print(f"{LABEL}\nArtifacts: {output}")


if __name__ == "__main__":
    main()
