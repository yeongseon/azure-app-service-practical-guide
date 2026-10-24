"""Azure App Service legacy lab classification tests (#182).

The classification is only useful if it cannot drift away from the
repository. A lab added later and never classified would otherwise sit
outside the Golden migration entirely while the file still looked
complete, so coverage is checked against the filesystem rather than
against a hand-maintained count.
"""

import sys

sys.dont_write_bytecode = True

import importlib.util
import datetime as dt
import json
import pathlib
import re
import subprocess
import unittest

from classification_integrity import ENVIRONMENT_FIELDS, evidence_environment, introducing_commit

ROOT = pathlib.Path(__file__).resolve().parents[2]
CLASSIFICATION = ROOT / "labs/golden-classification.json"
DATA = json.loads(CLASSIFICATION.read_text())
VALID = {"golden", "migration-needed", "archive-candidate"}
EXPECTED_SCENARIO_COUNT = 15
ARTIFACT_DIRECTORY_NAMES = {"artifacts-sanitized", "results"}
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")

_spec = importlib.util.spec_from_file_location("ev", ROOT / "scripts/golden/evaluate_run.py")
ev = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ev)


def labs_on_disk():
    return {
        p.name for p in (ROOT / "labs").iterdir()
        if p.is_dir() and not p.name.startswith("_")
    }


def artifact_directories():
    return {
        path.relative_to(ROOT / "labs").as_posix()
        for path in (ROOT / "labs").rglob("*")
        if path.is_dir() and path.name in ARTIFACT_DIRECTORY_NAMES
    }


def classified_artifact_sets():
    classified = []
    for row in DATA["labs"]:
        for item in row.get("artifact_sets", []):
            classified.append((f"{row['lab']}/{item['path']}", item))
        for stage in row.get("stages", []):
            for item in stage.get("artifact_sets", []):
                classified.append((f"{row['lab']}/{stage['stage']}/{item['path']}", item))
    return classified


def git_commit_resolves(commit):
    return subprocess.run(
        ["git", "cat-file", "-e", f"{commit}^{{commit}}"],
        cwd=ROOT,
        check=False,
        capture_output=True,
    ).returncode == 0


class CoverageTests(unittest.TestCase):
    def test_current_inventory_has_fifteen_scenarios(self):
        self.assertEqual(len(labs_on_disk()), EXPECTED_SCENARIO_COUNT)

    def test_every_lab_on_disk_is_classified(self):
        classified = {row["lab"] for row in DATA["labs"]}
        missing = labs_on_disk() - classified
        self.assertEqual(
            missing, set(),
            msg="labs exist on disk with no Golden classification; they would be "
                "silently excluded from the migration")

    def test_no_classification_refers_to_a_lab_that_does_not_exist(self):
        classified = {row["lab"] for row in DATA["labs"]}
        stale = classified - labs_on_disk()
        self.assertEqual(stale, set(), msg="classification refers to removed labs")

    def test_shared_harness_is_not_classified_as_a_lab(self):
        self.assertNotIn("_shared", {row["lab"] for row in DATA["labs"]})


class ShapeTests(unittest.TestCase):
    def test_every_classification_uses_the_declared_vocabulary(self):
        for row in DATA["labs"]:
            self.assertIn(row["classification"], VALID, msg=row["lab"])

    def test_every_lab_carries_a_substantive_reason(self):
        for row in DATA["labs"]:
            self.assertGreater(
                len(row["reason"].strip()), 40,
                msg=f"{row['lab']} needs a reason that states why, not a label")

    def test_criteria_are_defined_for_every_used_classification(self):
        used = {row["classification"] for row in DATA["labs"]}
        self.assertTrue(used <= set(DATA["criteria"]))

    def test_lab_entries_are_unique(self):
        names = [row["lab"] for row in DATA["labs"]]
        self.assertEqual(len(names), len(set(names)))

    def test_windows_java_stages_match_the_directory_inventory(self):
        row = next(item for item in DATA["labs"]
                   if item["lab"] == "windows-java-httpplatformhandler-timeout")
        declared = {item["stage"] for item in row["stages"]}
        directory = ROOT / "labs" / row["lab"]
        actual = {path.name for path in directory.iterdir() if path.is_dir()}
        self.assertEqual(declared, actual)
        for item in row["stages"]:
            self.assertIn(item["classification"], VALID)
            self.assertIn(item["artifact_trust"], ev.EVIDENCE_TRUST)

    def test_every_retained_artifact_set_is_classified_exactly_once(self):
        classified_paths = [path for path, _item in classified_artifact_sets()]
        self.assertEqual(len(classified_paths), len(set(classified_paths)), msg="duplicate artifact classification")
        self.assertEqual(set(classified_paths), artifact_directories())

    def test_artifact_metadata_has_split_resolvable_provenance(self):
        for path, item in classified_artifact_sets():
            self.assertIn(item["trust"], ev.EVIDENCE_TRUST, msg=path)
            self.assertRegex(item["captured_at"], r"^\d{4}-\d{2}-\d{2}$", msg=path)
            self.assertNotIn("source_commit", item, msg=f"{path}: ambiguous source_commit")
            introduced = item["artifact_introduced_commit"]
            self.assertRegex(introduced, FULL_SHA, msg=path)
            self.assertTrue(git_commit_resolves(introduced), msg=f"{path}: artifact commit does not resolve")
            revision = item["run_source_revision"]
            if revision is None:
                self.assertTrue(item["run_source_unavailable_reason"].strip(), msg=path)
                self.assertIsNone(item["run_source_dirty"], msg=path)
            else:
                self.assertRegex(revision, FULL_SHA, msg=path)
                self.assertTrue(git_commit_resolves(revision), msg=f"{path}: run revision does not resolve")
                self.assertIsInstance(item["run_source_dirty"], bool, msg=path)

    def test_artifact_commit_is_the_commit_that_introduced_capture_evidence(self):
        for path, item in classified_artifact_sets():
            commit, status = introducing_commit(ROOT, item["captured_at_evidence"])
            self.assertEqual(status, "verified", msg=f"{path}: {status}")
            self.assertEqual(item["artifact_introduced_commit"], commit, msg=path)

    def test_capture_dates_are_derived_from_retained_evidence(self):
        for path, item in classified_artifact_sets():
            evidence_path = ROOT / "labs" / item["captured_at_evidence"]
            self.assertTrue(evidence_path.is_file(), msg=path)
            evidence = evidence_path.read_text()
            compact_date = item["captured_at"].replace("-", "")
            self.assertTrue(
                item["captured_at"] in evidence or compact_date in evidence or compact_date in evidence_path.name,
                msg=f"{path}: captured_at is not derivable from {item['captured_at_evidence']}",
            )
            self.assertLessEqual(dt.date.fromisoformat(item["captured_at"]), dt.date.today(), msg=path)

    def test_environment_is_exactly_derived_from_its_named_evidence(self):
        for path, item in classified_artifact_sets():
            self.assertEqual(set(item["environment"]), ENVIRONMENT_FIELDS, msg=path)
            self.assertEqual(item["environment"], evidence_environment(ROOT, path, item), msg=path)

    def test_manifest_provenance_is_exactly_derived_from_evidence(self):
        for path, item in classified_artifact_sets():
            evidence_paths = item.get("environment_evidence", [])
            manifests = [json.loads((ROOT / "labs" / value).read_text()) for value in evidence_paths]
            source_manifests = [value for value in manifests if "sourceRevision" in value]
            if not source_manifests:
                continue
            self.assertEqual({value["sourceRevision"] for value in source_manifests}, {item["run_source_revision"]}, msg=path)
            self.assertEqual({value["sourceDirtyAtRun"] for value in source_manifests}, {item["run_source_dirty"]}, msg=path)


def environment_bearing_manifests(set_path):
    """Retained manifests under an artifact set that record a SKU and a CLI version."""
    found = []
    for path in sorted((ROOT / "labs" / set_path).rglob("*.json")):
        try:
            document = json.loads(path.read_text())
        except ValueError:
            continue
        if isinstance(document, dict) and "azureCliVersion" in document and any(
                key in document for key in ("sku", "skuAtStart", "skuAtEnd")):
            found.append(path.relative_to(ROOT / "labs").as_posix())
    return found


class ProvenanceFetchTests(unittest.TestCase):
    """CI clones shallowly, so every commit the classification names must be fetched."""

    def test_every_classified_commit_is_fetched_by_the_workflow(self):
        needed = set()
        for _path, item in classified_artifact_sets():
            needed.add(item["artifact_introduced_commit"])
            if item["run_source_revision"]:
                needed.add(item["run_source_revision"])
        workflow = (ROOT / ".github/workflows/validate-content-sources.yml").read_text()
        literal = set(re.findall(r"\b[0-9a-f]{40}\b", workflow))
        dynamic = set()
        for run in (ROOT / "evidence/runs").glob("*"):
            for name, getter in (
                ("manifest.json", lambda d: d.get("source_commit")),
                ("provenance.json", lambda d: d.get("derivation", {}).get("collector_commit")),
            ):
                if (run / name).is_file():
                    value = getter(json.loads((run / name).read_text()))
                    if isinstance(value, str):
                        dynamic.add(value)
        self.assertEqual(sorted(needed - literal - dynamic), [], msg="commits the workflow never fetches")

    def test_classification_commits_are_fetched_into_named_refs(self):
        workflow = (ROOT / ".github/workflows/validate-content-sources.yml").read_text()
        # `git log --all` only sees refs, so a bare `git fetch origin <sha>` is not enough.
        self.assertIn('"$sha:refs/golden-provenance/$sha"', workflow)


class OtherCaptureTests(unittest.TestCase):
    """A set-level record must not hide sub-captures whose environment or trust differs."""

    def test_no_environment_bearing_manifest_escapes_classification(self):
        for path, item in classified_artifact_sets():
            accounted = set(item.get("environment_evidence", []))
            for capture in item.get("other_captures", []):
                accounted |= set(capture.get("environment_evidence", []))
            with self.subTest(artifact_set=path):
                self.assertEqual(
                    sorted(set(environment_bearing_manifests(path)) - accounted), [],
                    msg=f"{path}: retained manifests are not named by the set or an other_capture")

    def test_other_captures_are_well_formed_and_exactly_derived(self):
        for path, item in classified_artifact_sets():
            seen = []
            for capture in item.get("other_captures", []):
                capture_path = f"{path}/{capture['path']}"
                with self.subTest(capture=capture_path):
                    seen.append(capture["path"])
                    self.assertTrue((ROOT / "labs" / capture_path).is_dir())
                    self.assertIn(capture["trust"], ev.EVIDENCE_TRUST)
                    self.assertTrue(capture["limitation"].strip(), msg="a limitation is required")
                    self.assertEqual(set(capture["environment"]), ENVIRONMENT_FIELDS)
                    self.assertEqual(capture["environment"], evidence_environment(ROOT, capture_path, capture))
            self.assertEqual(len(seen), len(set(seen)), msg=f"{path}: duplicate other_capture")

    def test_the_explicitly_excluded_control_is_classified_invalid(self):
        excluded = {
            path for path, _item in classified_artifact_sets()
            for child in (ROOT / "labs" / path).iterdir() if child.is_dir() and child.name == "excluded"
        }
        self.assertTrue(excluded, msg="expected at least one retained excluded/ directory")
        for path, item in classified_artifact_sets():
            if path in excluded:
                captures = {capture["path"]: capture for capture in item.get("other_captures", [])}
                with self.subTest(artifact_set=path):
                    self.assertEqual(captures["excluded"]["trust"], "invalid")

    def test_a_set_with_other_captures_carries_its_own_limitation(self):
        for path, item in classified_artifact_sets():
            if item.get("other_captures"):
                with self.subTest(artifact_set=path):
                    self.assertTrue(item.get("limitation", "").strip())

    def test_other_capture_dates_are_derivable_from_files_inside_them(self):
        for path, item in classified_artifact_sets():
            for capture in item.get("other_captures", []):
                date = capture.get("captured_at")
                if date is None:
                    continue
                compact = date.replace("-", "")
                root = ROOT / "labs" / path / capture["path"]
                found = any(
                    date in file.name or compact in file.name or date in file.read_text(errors="ignore")
                    for file in root.rglob("*") if file.is_file()
                )
                with self.subTest(capture=f"{path}/{capture['path']}"):
                    self.assertTrue(found, msg=f"{date} is not derivable from files under {capture['path']}")

    def test_a_set_referencing_several_deployments_declares_all_of_them(self):
        deployment = re.compile(r"\brg-lab-[a-z0-9]+(?:-[a-z0-9]+)*")
        for path, item in classified_artifact_sets():
            found = set()
            for file in (ROOT / "labs" / path).rglob("*"):
                if file.is_file() and file.suffix in {".json", ".log", ".txt", ".md", ".csv"}:
                    found |= {re.sub(r"-[A-Za-z]+webspace$", "", name) for name in deployment.findall(file.read_text(errors="ignore"))}
            declared = set(item.get("deployments", []))
            for capture in item.get("other_captures", []):
                declared |= set(capture.get("deployments", []))
            with self.subTest(artifact_set=path):
                if len(found) > 1:
                    self.assertEqual(declared, found, msg="a multi-deployment set must declare every deployment it contains")
                self.assertEqual(sorted(declared - found), [], msg="declared a deployment the set does not contain")

    def test_the_invalidated_plan_change_capture_records_its_in_run_transition(self):
        item = dict(classified_artifact_sets())["missing-wwwroot-content/artifacts-sanitized"]
        capture = next(c for c in item["other_captures"] if c["path"] == "f1-plan-run")
        self.assertEqual(capture["trust"], "invalid")
        transition = capture["plan_transition"]
        settle = "missing-wwwroot-content/artifacts-sanitized/f1-plan-run/manifest-arm-b-settle.json"
        manifest = json.loads((ROOT / "labs" / settle).read_text())
        started, finished = manifest["armStartedAt"][:19], manifest["armFinishedAt"][:19]
        self.assertLess(started, transition["at"][:19])
        self.assertLess(transition["at"][:19], finished)
        activity = (ROOT / "labs" / transition["evidence"]).read_text()
        self.assertIn(transition["at"][:19], activity)
        self.assertEqual(transition["recorded_sku_scope"], "end of run")
        self.assertIn("does not describe the whole arm", capture["limitation"])

    def test_the_f1_capture_is_not_folded_into_the_b1_environment(self):
        by_path = dict(classified_artifact_sets())
        item = by_path["missing-wwwroot-content/artifacts-sanitized"]
        self.assertEqual(item["environment"]["sku"], "B1")
        self.assertEqual({c["path"]: c["environment"]["sku"] for c in item["other_captures"]}, {"f1-plan-run": "F1"})


class GoldenClaimTests(unittest.TestCase):
    """A lab may only be called Golden if it actually declares a contract."""

    def test_golden_labs_have_a_manifest_declaring_assertions(self):
        for row in DATA["labs"]:
            if row["classification"] != "golden":
                continue
            manifest = ROOT / "labs" / row["lab"] / "golden/manifest.template.json"
            self.assertTrue(manifest.is_file(), msg=f"{row['lab']} claims golden with no manifest")
            data = json.loads(manifest.read_text())
            self.assertTrue(data["assertions"], msg=f"{row['lab']} declares no assertions")

    def test_golden_labs_declare_all_four_evidence_roles(self):
        for row in DATA["labs"]:
            if row["classification"] != "golden":
                continue
            manifest = json.loads(
                (ROOT / "labs" / row["lab"] / "golden/manifest.template.json").read_text())
            roles = {a["role"] for a in manifest["assertions"]}
            self.assertEqual(
                roles, {"control", "symptom", "discriminating", "recovery"}, msg=row["lab"])

    def test_golden_labs_ship_not_run_until_azure_produces_evidence(self):
        for row in DATA["labs"]:
            if row["classification"] != "golden":
                continue
            manifest = json.loads(
                (ROOT / "labs" / row["lab"] / "golden/manifest.template.json").read_text())
            self.assertEqual(manifest["execution_status"], "NOT_RUN", msg=row["lab"])

    def test_a_lab_without_a_manifest_is_not_called_golden(self):
        for row in DATA["labs"]:
            has_manifest = (ROOT / "labs" / row["lab"] / "golden/manifest.template.json").is_file()
            if not has_manifest:
                self.assertNotEqual(row["classification"], "golden", msg=row["lab"])


if __name__ == "__main__":
    unittest.main(verbosity=1)
