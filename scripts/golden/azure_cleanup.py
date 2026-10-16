#!/usr/bin/env python3
"""Select and delete only run-owned or expired Golden E2E resource groups."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import re
import subprocess
import sys
from typing import Mapping, Sequence


OWNER = "golden-e2e"
REPOSITORY = "yeongseon/azure-app-service-practical-guide"
RUN_ID_RE = re.compile(r"^[0-9]+-[1-9][0-9]*$")


class CleanupError(Exception):
    """A resource did not satisfy the cleanup ownership boundary."""


def _timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise CleanupError("ttl must include a timezone")
    return parsed


def expired_owned_groups(resources: Sequence[Mapping[str, str | Mapping[str, str]]], now: datetime) -> tuple[str, ...]:
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
            expired = _timestamp(ttl) < now
        except (ValueError, CleanupError):
            continue
        if expired:
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
    else:
        require_run_ownership(tags, run_id)
    _az("group", "delete", "--name", name, "--yes")
    exists = json.loads(_az("group", "exists", "--name", name))
    if exists is not False:
        raise CleanupError("resource group deletion was not verified")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="action", required=True)
    run = subparsers.add_parser("run")
    run.add_argument("--name", required=True)
    run.add_argument("--run-id", required=True)
    sweep = subparsers.add_parser("sweep")
    sweep.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        if args.action == "run":
            delete_group(args.name, args.run_id)
        else:
            resources = json.loads(_az("group", "list", "--tag", f"owner={OWNER}"))
            names = expired_owned_groups(resources, datetime.now(timezone.utc))
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
