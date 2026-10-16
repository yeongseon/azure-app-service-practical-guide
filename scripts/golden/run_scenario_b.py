#!/usr/bin/env python3
"""Execute Scenario B and persist the probe records its contract needs.

Nothing previously wrote per-phase probe records or probed the
destination's own health, so the five fields this contract asserts on had
no source and a Golden run could only return INCONCLUSIVE.

The runner drives three phases against `/outbound`, the unpooled path,
and records every probe as raw data: a status code when an HTTP round
trip completed, or a transport error when no response was obtained. It
classifies nothing -- `collect_scenario_b.py` applies the lab's shared
classifier so the collector and the workload cannot disagree about the
same response.

It also probes the destination directly. That is the discriminating
observation: without it, connection-level failures are equally consistent
with port exhaustion and with the destination simply being down, and the
hypothesis cannot be separated from that alternative.

Usage:
    python3 scripts/golden/run_scenario_b.py <app> \
        --destination <url> --output <dir outside the repository>

Exit codes: 0 captured, 2 the run could not be completed.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime
import json
import pathlib
import secrets
import socket
import sys
import time
import urllib.error
import urllib.request
import urllib.parse

sys.dont_write_bytecode = True

LAB = "snat-exhaustion"

#: Probes per phase. The contract's baseline and recovery assertions expect
#: every probe in those phases to succeed, and read this constant rather
#: than repeating the number, so the two cannot drift.
#:
#: A first live run measured the real cost: one probe to the unpooled path
#: fans out into roughly forty outbound calls, so fifty probes per phase was
#: about six thousand requests across three phases and did not finish inside
#: a window that could be supervised. Twelve keeps the phases meaningful
#: while making a run completable.
APP_WORKERS = 4
PROBES_PER_PHASE = 3

#: Concurrent workers used to create connection pressure. Exhaustion is a
#: function of sockets held in TIME_WAIT, so pressure must be concurrent
#: rather than merely repeated.
LOAD_WORKERS = 32

#: Seconds to hold pressure before probing under load.
LOAD_SECONDS = 45

#: Seconds to wait after pressure is removed before probing recovery.
#: Ports in TIME_WAIT are not reusable immediately.
RECOVERY_SETTLE_SECONDS = 90


class RunConfigurationError(Exception):
    pass


class DestinationPreflightError(Exception):
    pass


def now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def run_id() -> str:
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{secrets.token_hex(6)}"


def probe(url: str, timeout: int = 30) -> dict:
    """One probe, recorded as raw outcome data.

    A completed round trip records its status whatever that status is. A
    connection that could not be established or completed records the
    transport error instead. The distinction is the experiment: port
    exhaustion surfaces below HTTP, and folding it into an HTTP failure
    would discard the only signal that discriminates the hypothesis.
    """
    started = now()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            record = {"at": started, "status": response.status}
            if response.headers.get_content_type() == "application/json":
                body = json.loads(response.read())
                required = {"success", "failure", "transportFailure"}
                if required <= set(body):
                    record["inner"] = {
                        "success": body["success"],
                        "failure": body["failure"],
                        "transport_failure": body["transportFailure"],
                    }
                    record["target"] = body.get("target")
            return record
    except urllib.error.HTTPError as exc:
        # The server answered. That is an HTTP failure, not a transport one.
        return {"at": started, "status": exc.code}
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        reason = getattr(exc, "reason", exc)
        return {"at": started, "transport_error": str(reason)}


def probe_phase(url: str, count: int = PROBES_PER_PHASE) -> list[dict]:
    with concurrent.futures.ThreadPoolExecutor(max_workers=count) as pool:
        return list(pool.map(probe, [url] * count))


def apply_pressure(url: str, seconds: int, workers: int) -> dict:
    """Hold concurrent outbound connections open for a while.

    The return value is a record of what was attempted, not a judgement
    about whether exhaustion occurred. Whether it did is decided by the
    probes and the declared assertions.
    """
    deadline = time.monotonic() + seconds
    attempts = 0
    started = now()
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        while time.monotonic() < deadline:
            futures = [pool.submit(probe, url, 15) for _ in range(workers)]
            for future in concurrent.futures.as_completed(futures):
                future.result()
                attempts += 1
    return {"started_at": started, "ended_at": now(), "attempts": attempts,
            "workers": workers, "seconds": seconds}


def execute(app: str, destination: str, output: pathlib.Path,
            source_commit: str | None = None) -> pathlib.Path:
    destination_url = urllib.parse.urlsplit(destination)
    tested_host = f"{app}.azurewebsites.net".casefold()
    hostname = destination_url.hostname
    if hostname is None:
        raise RunConfigurationError(
            "destination must be an independently hosted lab-controlled endpoint")
    destination_addresses = {
        item[4][0] for item in socket.getaddrinfo(hostname, destination_url.port or 443)
    }
    tested_addresses = {
        item[4][0] for item in socket.getaddrinfo(tested_host, 443)
    }
    if hostname.casefold() == tested_host or destination_addresses & tested_addresses:
        raise RunConfigurationError(
            "destination must be an independently hosted lab-controlled endpoint")
    identifier = run_id()
    directory = output / identifier
    directory.mkdir(parents=True, exist_ok=False)

    app_base = f"https://{app}.azurewebsites.net"
    query = urllib.parse.urlencode({"target": destination, "calls": 5})
    outbound = app_base + "/outbound?" + query
    pooled = app_base + "/outbound-fixed?" + query

    (directory / "run.json").write_text(json.dumps({
        "run_id": identifier,
        "started_at": now(),
        "app": app,
        "resource_id": f"/sites/{app}",
        "scenario": LAB,
        "runner_source_commit": source_commit,
        "outbound_url": outbound,
        "pooled_url": pooled,
        "destination": destination,
    }, indent=2))

    preflight = probe(destination)
    preflight.update({"run_id": identifier, "target": destination})
    (directory / "destination-preflight.json").write_text(json.dumps(preflight, indent=2))
    if preflight.get("status") != 200:
        raise DestinationPreflightError(
            "independent destination preflight did not return HTTP 200")

    def capture_phase(name: str) -> None:
        phase_dir = directory / name
        phase_dir.mkdir()
        started_at = now()
        unpooled = [dict(item, run_id=identifier, target=destination)
                    for item in probe_phase(outbound)]
        pooled_records = [dict(item, run_id=identifier, target=destination)
                          for item in probe_phase(pooled)]
        ended_at = now()
        (phase_dir / "phase.json").write_text(json.dumps({
            "run_id": identifier,
            "started_at": started_at,
            "ended_at": ended_at,
            "unpooled_probe_count": len(unpooled),
            "pooled_probe_count": len(pooled_records),
        }, indent=2))
        (phase_dir / "unpooled-probes.json").write_text(json.dumps(unpooled, indent=2))
        (phase_dir / "pooled-probes.json").write_text(json.dumps(pooled_records, indent=2))

    capture_phase("baseline")

    pressure = apply_pressure(outbound, LOAD_SECONDS, LOAD_WORKERS)
    pressure["status"] = pressure.get("status", "unavailable")
    (directory / "port-pressure.json").write_text(json.dumps(pressure, indent=2))
    requested = urllib.parse.urlsplit(destination)
    outbound_query = urllib.parse.parse_qs(urllib.parse.urlsplit(outbound).query)
    bound_destination = outbound_query.get("target", [None])[0]
    (directory / "app-target.json").write_text(json.dumps({
        "requested_destination": destination,
        "outbound_destination": bound_destination,
        "matches_requested_destination": bound_destination == destination
        and bool(requested.scheme and requested.netloc),
    }, indent=2))
    capture_phase("load")

    # Probed while the app is still under the same conditions, so a failing
    # destination cannot be mistaken for exhaustion after the fact.
    destination_health = probe(destination)
    destination_health.update({"run_id": identifier, "target": destination})
    (directory / "destination-health.json").write_text(json.dumps(
        destination_health, indent=2))

    time.sleep(RECOVERY_SETTLE_SECONDS)
    capture_phase("recovery")

    (directory / "run-complete.json").write_text(json.dumps({"ended_at": now()}, indent=2))
    return directory


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("app")
    parser.add_argument(
        "--destination", required=True,
        help=("Independently hosted lab-controlled URL that returns HTTP 200. "
              "The tested app's own hostname is rejected."))
    parser.add_argument("--output", required=True,
                        help="Private evidence directory outside the repository")
    parser.add_argument("--source-commit", required=True,
                        help="Full repository commit used for this capture")
    args = parser.parse_args()
    try:
        directory = execute(args.app, args.destination, pathlib.Path(args.output),
                            args.source_commit)
    except (OSError, RunConfigurationError, DestinationPreflightError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"RUN_DIR={directory}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
