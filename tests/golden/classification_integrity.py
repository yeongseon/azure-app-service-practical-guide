from __future__ import annotations

import json
import pathlib
import subprocess


ENVIRONMENT_FIELDS = {"sku", "runtime", "os", "region", "cli_version", "unknown_reasons"}


def introducing_commit(root: pathlib.Path, evidence_path: str) -> tuple[str | None, str]:
    result = subprocess.run(
        [
            "git",
            "log",
            "--all",
            "--diff-filter=A",
            "--follow",
            "--format=%H",
            "--",
            f"labs/{evidence_path}",
        ],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    commits = list(dict.fromkeys(result.stdout.splitlines()))
    if result.returncode != 0 or not commits:
        return None, "history-unavailable"
    return commits[-1], "verified"


def _manifest_environment(documents: list[dict]) -> dict:
    skus = {
        value
        for document in documents
        for key in ("sku", "skuAtStart", "skuAtEnd")
        if (value := document.get(key)) is not None
    }
    runtimes = {document["runtime"] for document in documents if "runtime" in document}
    regions = {document["location"] for document in documents if "location" in document}
    versions = {document["azureCliVersion"] for document in documents if "azureCliVersion" in document}
    if not all(len(values) == 1 for values in (skus, runtimes, regions, versions)):
        raise AssertionError("environment evidence contains conflicting or missing manifest values")
    runtime = runtimes.pop()
    os_name = "Windows" if "Windows" in runtime else None
    unknown_reasons = {} if os_name else {"os": "The retained manifest does not record the operating system."}
    return {
        "sku": skus.pop(),
        "runtime": runtime,
        "os": os_name,
        "region": regions.pop(),
        "cli_version": versions.pop(),
        "unknown_reasons": unknown_reasons,
    }


def _java_environment(documents: list[dict]) -> dict:
    merged = next((document for document in documents if "webapp_config" in document), None)
    if merged is not None:
        config = merged["webapp_config"]
        plan = merged["plan_config"]
        sku = plan["sku"]["name"]
        region = plan["location"]
        os_name = "Linux" if plan["properties"]["reserved"] else "Windows"
    else:
        config = next(document for document in documents if "javaVersion" in document)
        app = next(document for document in documents if "reserved" in document)
        sku = app["sku"]
        region = app["location"]
        os_name = "Linux" if app["reserved"] else "Windows"
    return {
        "sku": sku,
        "runtime": f"{config['javaContainer']} {config['javaContainerVersion']} {config['javaVersion']}",
        "os": os_name,
        "region": region,
        "cli_version": None,
        "unknown_reasons": {"cli_version": "The retained Java stage evidence does not record the Azure CLI version."},
    }


def evidence_environment(root: pathlib.Path, artifact_path: str, item: dict) -> dict:
    evidence_paths = item.get("environment_evidence")
    if not evidence_paths:
        reason = item.get("environment_evidence_unavailable_reason", "").strip()
        if not reason:
            raise AssertionError(f"{artifact_path}: environment evidence is required")
        return {
            "sku": None,
            "runtime": None,
            "os": None,
            "region": None,
            "cli_version": None,
            "unknown_reasons": {field: reason for field in ENVIRONMENT_FIELDS - {"unknown_reasons"}},
        }

    artifact_root = pathlib.PurePosixPath(artifact_path)
    documents = []
    for relative in evidence_paths:
        evidence_path = pathlib.PurePosixPath(relative)
        if not evidence_path.is_relative_to(artifact_root):
            raise AssertionError(f"{artifact_path}: environment evidence belongs to another artifact set")
        documents.append(json.loads((root / "labs" / relative).read_text()))
    if "windows-java-httpplatformhandler-timeout" in artifact_path:
        return _java_environment(documents)
    return _manifest_environment(documents)
