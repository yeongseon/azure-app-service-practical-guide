#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import importlib
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path


def load_matplotlib_pyplot():
    try:
        return importlib.import_module("matplotlib.pyplot")
    except ImportError as exc:
        raise SystemExit(
            "matplotlib is required. Install with: pip install matplotlib"
        ) from exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate lab charts from artifacts")
    parser.add_argument("--artifacts-dir", required=True, help="Artifacts directory")
    parser.add_argument(
        "--output-dir", default="artifacts/charts", help="Chart output directory"
    )
    return parser.parse_args()


def parse_iso(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def load_json(path: Path):
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def chart_cpu_memory(artifacts_dir: Path, output_dir: Path) -> bool:
    plt = load_matplotlib_pyplot()
    summary_csv = artifacts_dir / "raw" / "metrics" / "metrics-summary.csv"
    plan_json = artifacts_dir / "raw" / "metrics" / "plan-metrics.json"

    points = []
    if summary_csv.exists():
        with summary_csv.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                if row.get("resource_type") != "plan":
                    continue
                metric = row.get("metric")
                if metric not in {"CpuPercentage", "MemoryPercentage"}:
                    continue
                points.append(
                    (row.get("timestamp", ""), metric, row.get("average", ""))
                )
    elif plan_json.exists():
        payload = load_json(plan_json)
        for metric_entry in (payload or {}).get("value", []):
            metric_name = (metric_entry.get("name") or {}).get("value", "")
            for series in metric_entry.get("timeseries", []):
                for point in series.get("data", []):
                    points.append(
                        (
                            point.get("timeStamp", ""),
                            metric_name,
                            point.get("average", ""),
                        )
                    )

    if not points:
        print("[generate-charts] skip cpu-memory-timeline.png (missing source data)")
        return False

    merged: dict[str, dict[str, float | None]] = {}
    for ts, metric, value in points:
        try:
            if ts not in merged:
                merged[ts] = {"CpuPercentage": None, "MemoryPercentage": None}
            merged[ts][metric] = float(value)
        except (TypeError, ValueError):
            continue

    timestamps = sorted(merged.keys(), key=parse_iso)
    cpu = [merged[t]["CpuPercentage"] for t in timestamps]
    memory = [merged[t]["MemoryPercentage"] for t in timestamps]

    plt.figure(figsize=(10, 6), dpi=150)
    plt.plot(timestamps, cpu, label="CPU %")
    plt.plot(timestamps, memory, label="Memory %")
    plt.title("CPU and Memory Timeline")
    plt.xlabel("Time")
    plt.ylabel("Percentage")
    plt.legend()
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(output_dir / "cpu-memory-timeline.png")
    plt.close()
    return True


def chart_http_status_distribution(artifacts_dir: Path, output_dir: Path) -> bool:
    plt = load_matplotlib_pyplot()
    kql_file = artifacts_dir / "raw" / "kql" / "http-logs.json"
    payload = load_json(kql_file)
    if not payload:
        print(
            "[generate-charts] skip http-status-distribution.png (missing source data)"
        )
        return False

    rows = []
    tables = payload.get("tables") or []
    if tables and tables[0].get("rows"):
        columns = [c.get("name") for c in tables[0].get("columns", [])]
        for row in tables[0].get("rows", []):
            rows.append(dict(zip(columns, row)))

    if not rows:
        print("[generate-charts] skip http-status-distribution.png (no KQL rows)")
        return False

    counts = defaultdict(lambda: defaultdict(int))
    for row in rows:
        ts = str(row.get("TimeGenerated", ""))
        status = str(row.get("ScStatus", "unknown"))
        counts[ts][status] += 1

    timestamps = sorted(counts.keys(), key=parse_iso)
    statuses = sorted({status for ts in timestamps for status in counts[ts].keys()})

    plt.figure(figsize=(10, 6), dpi=150)
    for status in statuses:
        series = [counts[ts].get(status, 0) for ts in timestamps]
        plt.plot(timestamps, series, label=f"HTTP {status}")

    plt.title("HTTP Status Distribution Over Time")
    plt.xlabel("Time")
    plt.ylabel("Count")
    plt.legend()
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(output_dir / "http-status-distribution.png")
    plt.close()
    return True


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return float("nan")
    ordered = sorted(values)
    idx = int(round((len(ordered) - 1) * pct))
    return ordered[idx]


def chart_response_time_timeline(artifacts_dir: Path, output_dir: Path) -> bool:
    plt = load_matplotlib_pyplot()
    summary_csv = artifacts_dir / "raw" / "http" / "http-summary.csv"
    if not summary_csv.exists():
        print("[generate-charts] skip response-time-timeline.png (missing source data)")
        return False

    rows = []
    with summary_csv.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            try:
                rows.append((row["timestamp"], float(row["time_total"])))
            except (KeyError, TypeError, ValueError):
                continue

    if not rows:
        print("[generate-charts] skip response-time-timeline.png (no valid rows)")
        return False

    rows.sort(key=lambda item: parse_iso(item[0]))
    timestamps = []
    p50_values = []
    p95_values = []
    p99_values = []
    running = []

    for ts, value in rows:
        running.append(value)
        timestamps.append(ts)
        p50_values.append(percentile(running, 0.50))
        p95_values.append(percentile(running, 0.95))
        p99_values.append(percentile(running, 0.99))

    plt.figure(figsize=(10, 6), dpi=150)
    plt.plot(timestamps, p50_values, label="p50")
    plt.plot(timestamps, p95_values, label="p95")
    plt.plot(timestamps, p99_values, label="p99")
    plt.title("Response Time Timeline (p50/p95/p99)")
    plt.xlabel("Time")
    plt.ylabel("Seconds")
    plt.legend()
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(output_dir / "response-time-timeline.png")
    plt.close()
    return True


def chart_event_timeline(artifacts_dir: Path, output_dir: Path) -> bool:
    plt = load_matplotlib_pyplot()
    metrics_csv = artifacts_dir / "raw" / "metrics" / "metrics-summary.csv"
    deploy_json = artifacts_dir / "raw" / "deploy-output.json"

    if not metrics_csv.exists():
        print("[generate-charts] skip event-timeline.png (missing metrics data)")
        return False

    cpu_points = []
    with metrics_csv.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if (
                row.get("resource_type") == "plan"
                and row.get("metric") == "CpuPercentage"
            ):
                try:
                    cpu_points.append(
                        (row.get("timestamp", ""), float(row.get("average", "")))
                    )
                except ValueError:
                    continue

    if not cpu_points:
        print("[generate-charts] skip event-timeline.png (no CPU points)")
        return False

    cpu_points.sort(key=lambda item: parse_iso(item[0]))
    timestamps = [p[0] for p in cpu_points]
    values = [p[1] for p in cpu_points]

    events = []
    deploy_payload = load_json(deploy_json)
    if deploy_payload:
        deploy_ts = (deploy_payload.get("properties") or {}).get("timestamp")
        if deploy_ts:
            events.append((deploy_ts, "deploy"))

    trigger_marker = artifacts_dir / "raw" / "trigger-event.txt"
    fix_marker = artifacts_dir / "raw" / "fix-event.txt"
    if trigger_marker.exists():
        events.append((trigger_marker.read_text(encoding="utf-8").strip(), "trigger"))
    if fix_marker.exists():
        events.append((fix_marker.read_text(encoding="utf-8").strip(), "fix"))

    plt.figure(figsize=(10, 6), dpi=150)
    plt.plot(timestamps, values, label="CPU %", color="tab:blue")

    for ts, label in events:
        if ts:
            plt.axvline(ts, linestyle="--", alpha=0.7, label=label)

    handles, labels = plt.gca().get_legend_handles_labels()
    dedup = dict(zip(labels, handles))
    plt.legend(dedup.values(), dedup.keys())
    plt.title("Event Timeline with Metrics Overlay")
    plt.xlabel("Time")
    plt.ylabel("CPU %")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(output_dir / "event-timeline.png")
    plt.close()
    return True


def main() -> None:
    args = parse_args()
    artifacts_dir = Path(args.artifacts_dir).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    generated = 0
    generated += int(chart_cpu_memory(artifacts_dir, output_dir))
    generated += int(chart_http_status_distribution(artifacts_dir, output_dir))
    generated += int(chart_response_time_timeline(artifacts_dir, output_dir))
    generated += int(chart_event_timeline(artifacts_dir, output_dir))

    print(f"[generate-charts] generated {generated} chart(s) in {output_dir}")


if __name__ == "__main__":
    main()
