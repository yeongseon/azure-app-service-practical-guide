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
import sys
import time
import urllib.error
import urllib.request

sys.dont_write_bytecode = True

LAB = "snat-exhaustion"

#: Probes per phase. The contract's baseline and recovery assertions
#: expect every probe in those phases to succeed.
PROBES_PER_PHASE = 50

#: Concurrent workers used to create connection pressure. Exhaustion is a
#: function of sockets held in TIME_WAIT, so pressure must be concurrent
#: rather than merely repeated.
LOAD_WORKERS = 32

#: Seconds to hold pressure before probing under load.
LOAD_SECONDS = 45

#: Seconds to wait after pressure is removed before probing recovery.
#: Ports in TIME_WAIT are not reusable immediately.
RECOVERY_SETTLE_SECONDS = 90


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
            return {"at": started, "status": response.status}
    except urllib.error.HTTPError as exc:
        # The server answered. That is an HTTP failure, not a transport one.
        return {"at": started, "status": exc.code}
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        reason = getattr(exc, "reason", exc)
        return {"at": started, "transport_error": str(reason)}


def probe_phase(url: str, count: int = PROBES_PER_PHASE) -> list[dict]:
    return [probe(url) for _ in range(count)]


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


def execute(app: str, destination: str, output: pathlib.Path) -> pathlib.Path:
    identifier = run_id()
    directory = output / identifier
    directory.mkdir(parents=True, exist_ok=False)

    outbound = f"https://{app}.azurewebsites.net/outbound"

    (directory / "run.json").write_text(json.dumps({
        "run_id": identifier,
        "started_at": now(),
        "app": app,
        "scenario": LAB,
        "outbound_url": outbound,
    }, indent=2))

    for phase, probes in (("baseline", probe_phase(outbound)),):
        (directory / phase).mkdir()
        (directory / phase / "probes.json").write_text(json.dumps(probes, indent=2))

    pressure = apply_pressure(outbound, LOAD_SECONDS, LOAD_WORKERS)
    (directory / "pressure.json").write_text(json.dumps(pressure, indent=2))
    (directory / "load").mkdir()
    (directory / "load" / "probes.json").write_text(
        json.dumps(probe_phase(outbound), indent=2))

    # Probed while the app is still under the same conditions, so a failing
    # destination cannot be mistaken for exhaustion after the fact.
    (directory / "destination-health.json").write_text(json.dumps(
        probe(destination), indent=2))

    time.sleep(RECOVERY_SETTLE_SECONDS)
    (directory / "recovery").mkdir()
    (directory / "recovery" / "probes.json").write_text(
        json.dumps(probe_phase(outbound), indent=2))

    (directory / "run-complete.json").write_text(json.dumps({"ended_at": now()}, indent=2))
    return directory


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("app")
    parser.add_argument("--destination", required=True,
                        help="URL the workload calls, probed directly for its own health")
    parser.add_argument("--output", required=True,
                        help="Private evidence directory outside the repository")
    args = parser.parse_args()
    try:
        directory = execute(args.app, args.destination, pathlib.Path(args.output))
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"RUN_DIR={directory}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
