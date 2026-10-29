from __future__ import annotations

import json
import pathlib
import subprocess


ENVIRONMENT_FIELDS = {"sku", "runtime", "os", "region", "cli_version", "unknown_reasons"}
ENVIRONMENT_KEYS = {"linuxFxVersion", "windowsFxVersion", "kind", "reserved", "location",
                    "sku", "skuAtStart", "skuAtEnd", "azureCliVersion", "runtime", "javaVersion"}


def capture_files(artifact_root: pathlib.Path, item: dict) -> list[pathlib.Path]:
    """Expand an exclusive directory scope or explicit file list within its set."""
    if "files" in item:
        files = [artifact_root / relative for relative in item["files"]]
        if not files or any(not file.is_relative_to(artifact_root) or ".." in file.parts for file in files):
            raise AssertionError("capture files must remain inside their artifact set")
        return files
    scope = artifact_root / item.get("path", ".")
    if not scope.is_relative_to(artifact_root) or ".." in scope.parts:
        raise AssertionError("capture path must remain inside its artifact set")
    return sorted(file for file in scope.rglob("*") if file.is_file())


def _environment_keys(value) -> set[str]:
    if isinstance(value, dict):
        return (set(value) & ENVIRONMENT_KEYS).union(*(_environment_keys(child) for child in value.values()))
    if isinstance(value, list):
        return set().union(*(_environment_keys(child) for child in value))
    return set()


def _configuration_environment(documents: list[dict]) -> dict:
    """Read configuration fields verbatim and infer the operating system from their signals.

    Linux is inferred, not read, from reserved=true, a kind containing linux,
    or a nonempty linuxFxVersion (Microsoft Learn defines linuxFxVersion as the
    Linux app framework and version). Absent signals do not establish Windows.
    """
    documents = [part for doc in documents for part in (doc, doc.get("siteConfig", {}))]
    keys = {"sku": ("sku", "skuAtStart", "skuAtEnd"), "runtime": ("linuxFxVersion",),
            "region": ("location",), "cli_version": ("azureCliVersion",)}
    result = {}
    for field, names in keys.items():
        values = {value for doc in documents for key in names
                  if isinstance(value := doc.get(key), str) and value.strip()}
        if len(values) > 1:
            raise AssertionError(f"conflicting configuration {field} values")
        result[field] = next(iter(values), None)
    linux = any(doc.get("reserved") is True or "linux" in (doc.get("kind") or "").lower()
                or bool(doc.get("linuxFxVersion")) for doc in documents)
    if linux and any(doc.get("reserved") is False or bool(doc.get("windowsFxVersion")) for doc in documents):
        raise AssertionError("conflicting configuration os values")
    result["os"] = "Linux" if linux else None
    labels = {"sku": "plan SKU", "runtime": "runtime", "os": "operating system",
              "region": "region", "cli_version": "Azure CLI version"}
    result["unknown_reasons"] = {
        field: f"The retained configuration does not record the {labels[field]}."
        for field in labels if result[field] is None
    }
    return result


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
        scope = {key: value for key, value in item.items()
                 if key != "path" or value != pathlib.PurePosixPath(artifact_path).name}
        for file in capture_files(root / "labs" / artifact_path, scope):
            if file.suffix == ".json":
                try:
                    document = json.loads(file.read_text())
                except json.JSONDecodeError:
                    continue
                if _environment_keys(document):
                    raise AssertionError(f"{file}: uncited environment-bearing JSON")
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
    if any("webapp_config" in doc or bool(doc.get("javaVersion")) for doc in documents):
        environment = _java_environment(documents)
    elif any("runtime" in doc for doc in documents):
        environment = _manifest_environment(documents)
    else:
        environment = _configuration_environment(documents)
    declared = item.get("environment", {})
    for field in ENVIRONMENT_FIELDS - {"unknown_reasons"}:
        if field not in declared or declared[field] is not None:
            continue
        reason = declared.get("unknown_reasons", {}).get(field, "")
        if not reason.strip():
            raise AssertionError(f"{field}: unknown requires a reason")
        if environment.get(field) is not None:
            raise AssertionError(f"{field} declared unknown but supplied by cited evidence")
        keys = {"sku": {"sku", "skuAtStart", "skuAtEnd"}, "runtime": {"runtime", "linuxFxVersion", "windowsFxVersion", "javaVersion"},
                "region": {"location"}, "cli_version": {"azureCliVersion"}, "os": {"reserved", "kind", "linuxFxVersion", "windowsFxVersion"}}
        if field != "os" and any(_environment_keys(doc) & keys[field] for doc in documents):
            raise AssertionError(f"{field} declared unknown but its key is present in cited evidence")
    return environment
