#!/usr/bin/env python3
"""Select and delete only run-owned or expired Golden E2E resource groups."""
from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
import json
import re
import subprocess
import sys
import time
from pathlib import Path


OWNER = "golden-e2e"
REPOSITORY = "yeongseon/azure-app-service-practical-guide"
RUN_ID_RE = re.compile(r"^[0-9]+-[1-9][0-9]*$")
TTL_HOURS_RE = re.compile(r"^(?:[1-9]|[1-6][0-9]|7[0-2])$")
GROUP_PREFIX = "rg-golden-e2e-"


class CleanupError(Exception):
    """A resource did not satisfy the cleanup ownership boundary."""


def _timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise CleanupError("ttl must include a timezone")
    return parsed


def parse_ttl_hours(value: str) -> int:
    if not TTL_HOURS_RE.fullmatch(value):
        raise CleanupError("ttl_hours must be a decimal integer from 1 through 72")
    return int(value)


def require_owned_name(name: str, run_id: str) -> None:
    if not RUN_ID_RE.fullmatch(run_id) or name != f"{GROUP_PREFIX}{run_id}":
        raise CleanupError("resource group name is not bound to this Golden E2E run")


def expired_owned_groups(
    resources: Sequence[Mapping[str, str | Mapping[str, str]]],
    now: datetime,
    active_run_id: str | None = None,
) -> tuple[str, ...]:
    selected: list[str] = []
    for resource in resources:
        name = resource.get("name")
        tags = resource.get("tags")
        if not isinstance(name, str) or not isinstance(tags, Mapping):
            continue
        owner = tags.get("owner")
        repository = tags.get("repository")
        run_id = tags.get("run-id")
        ttl = tags.get("ttl")
        if (
            owner != OWNER
            or repository != REPOSITORY
            or not isinstance(run_id, str)
            or not RUN_ID_RE.fullmatch(run_id)
            or not isinstance(ttl, str)
        ):
            continue
        try:
            require_owned_name(name, run_id)
            expired = _timestamp(ttl) < now
        except (ValueError, CleanupError):
            continue
        if expired and run_id != active_run_id:
            selected.append(name)
    return tuple(sorted(selected))


def require_run_ownership(tags: Mapping[str, str], run_id: str) -> None:
    if (
        tags.get("owner") != OWNER
        or tags.get("repository") != REPOSITORY
        or tags.get("run-id") != run_id
        or not RUN_ID_RE.fullmatch(run_id)
    ):
        raise CleanupError("resource group is not owned by this Golden E2E run")


def _az(*args: str) -> str:
    result = subprocess.run(
        ["az", *args, "--output", "json"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise CleanupError(result.stderr.strip() or "Azure CLI command failed")
    return result.stdout


def delete_group(name: str, run_id: str | None) -> None:
    group = json.loads(_az("group", "show", "--name", name))
    tags = group.get("tags") or {}
    if run_id is None:
        ttl = tags.get("ttl")
        tag_run_id = tags.get("run-id")
        if (
            tags.get("owner") != OWNER
            or tags.get("repository") != REPOSITORY
            or not isinstance(tag_run_id, str)
            or not RUN_ID_RE.fullmatch(tag_run_id)
            or not isinstance(ttl, str)
            or _timestamp(ttl) >= datetime.now(timezone.utc)
        ):
            raise CleanupError("TTL sweep target is not owned and expired")
        require_owned_name(name, tag_run_id)
    else:
        require_owned_name(name, run_id)
        require_run_ownership(tags, run_id)
    _az("group", "delete", "--name", name, "--yes")
    for attempt in range(12):
        exists = json.loads(_az("group", "exists", "--name", name))
        if exists is False:
            return
        if attempt < 11:
            time.sleep(5)
    raise CleanupError("resource group deletion was not verified within 60 seconds")


def write_cleanup_result(path: Path, run_id: str, status: str, error: str | None = None) -> None:
    github_run_id, github_run_attempt = run_id.split("-", maxsplit=1)
    result = {
        "github_run_id": github_run_id,
        "github_run_attempt": github_run_attempt,
        "cleanup_status": status,
        "verified_at": datetime.now(timezone.utc).isoformat(),
    }
    if error is not None:
        result["error"] = error
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="action", required=True)
    run = subparsers.add_parser("run")
    run.add_argument("--name", required=True)
    run.add_argument("--run-id", required=True)
    run.add_argument("--result", type=Path, required=True)
    sweep = subparsers.add_parser("sweep")
    sweep.add_argument("--apply", action="store_true")
    sweep.add_argument("--active-run-id")
    ttl = subparsers.add_parser("validate-ttl")
    ttl.add_argument("--hours", required=True)
    args = parser.parse_args()
    try:
        if args.action == "validate-ttl":
            print(parse_ttl_hours(args.hours))
        elif args.action == "run":
            try:
                delete_group(args.name, args.run_id)
            except (CleanupError, json.JSONDecodeError) as exc:
                write_cleanup_result(args.result, args.run_id, "FAILED", str(exc))
                raise
            write_cleanup_result(args.result, args.run_id, "VERIFIED")
        else:
            resources = json.loads(_az("group", "list", "--tag", f"owner={OWNER}"))
            names = expired_owned_groups(
                resources,
                datetime.now(timezone.utc),
                active_run_id=args.active_run_id,
            )
            print(json.dumps({"expired_owned_groups": names}, indent=2))
            if args.apply:
                for name in names:
                    delete_group(name, None)
    except (CleanupError, json.JSONDecodeError) as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 4
    return 0


if __name__ == "__main__":
    sys.exit(main())
