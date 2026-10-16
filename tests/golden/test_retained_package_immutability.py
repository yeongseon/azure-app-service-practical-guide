#!/usr/bin/env python3
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/golden/check_retained_packages.py"


def run_git(repo: pathlib.Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


class RetainedPackageImmutabilityTests(unittest.TestCase):
    def setUp(self):
        self.repo = pathlib.Path(tempfile.mkdtemp())
        run_git(self.repo, "init")
        run_git(self.repo, "config", "user.email", "test@example.com")
        run_git(self.repo, "config", "user.name", "Golden Test")
        (self.repo / "scripts/golden").mkdir(parents=True)
        shutil.copy2(SCRIPT, self.repo / "scripts/golden/check_retained_packages.py")
        self.run_dir = self.repo / "evidence/runs/run-one"
        self.run_dir.mkdir(parents=True)
        for name, content in {
            "manifest.json": '{"run_id":"run-one","captured_at":"2026-01-01T00:00:00Z"}',
            "evidence.json": '{"run_id":"run-one","captured_at":"2026-01-01T00:00:00Z"}',
            "result.json": '{"run_id":"run-one","captured_at":"2026-01-01T00:00:00Z"}',
        }.items():
            (self.run_dir / name).write_text(content)
        self._write_digest_manifest()
        self._write_declarations({})
        run_git(self.repo, "add", ".")
        run_git(self.repo, "commit", "-m", "base")
        self.base = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=self.repo, text=True).strip()

    def _write_digest_manifest(self) -> None:
        files = {
            str(path.relative_to(self.repo)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(self.run_dir.glob("*.json"))
        }
        manifest = {"version": 1, "packages": {"run-one": {"historical": True, "files": files}}}
        (self.repo / "evidence/retained-digests.json").write_text(json.dumps(manifest))

    def _write_declarations(self, runs: dict) -> None:
        path = self.repo / "evidence/run-declarations.json"
        path.write_text(json.dumps({"version": 1, "runs": runs}))

    def _check(self, base: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "scripts/golden/check_retained_packages.py", "--base-ref", base],
            cwd=self.repo,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_addition_inside_existing_package_fails(self):
        (self.run_dir / "extra.json").write_text("{}")
        run_git(self.repo, "add", ".")
        run_git(self.repo, "commit", "-m", "add retained file")
        self.assertNotEqual(self._check(self.base).returncode, 0)

    def test_consistent_redating_and_commit_fails(self):
        for path in self.run_dir.glob("*.json"):
            path.write_text(path.read_text().replace("2026-01-01", "2026-02-01"))
        run_git(self.repo, "add", ".")
        run_git(self.repo, "commit", "-m", "redate retained package")
        self.assertNotEqual(self._check(self.base).returncode, 0)

    def test_head_base_cannot_bypass_digest_manifest(self):
        (self.run_dir / "manifest.json").write_text("{}")
        self.assertNotEqual(self._check("HEAD").returncode, 0)

    def test_existing_digest_entry_is_append_only(self):
        manifest_path = self.repo / "evidence/retained-digests.json"
        document = json.loads(manifest_path.read_text())
        document["packages"]["run-one"]["historical"] = False
        manifest_path.write_text(json.dumps(document))
        run_git(self.repo, "add", ".")
        run_git(self.repo, "commit", "-m", "rewrite retained entry")
        self.assertNotEqual(self._check(self.base).returncode, 0)

    def test_whole_new_run_directory_is_allowed_when_manifested(self):
        new_dir = self.repo / "evidence/runs/run-two"
        new_dir.mkdir()
        (new_dir / "manifest.json").write_text("{}")
        manifest_path = self.repo / "evidence/retained-digests.json"
        document = json.loads(manifest_path.read_text())
        path = "evidence/runs/run-two/manifest.json"
        document["packages"]["run-two"] = {
            "historical": False,
            "files": {path: hashlib.sha256((self.repo / path).read_bytes()).hexdigest()},
        }
        manifest_path.write_text(json.dumps(document))
        run_git(self.repo, "add", ".")
        run_git(self.repo, "commit", "-m", "add new run")
        self.assertEqual(self._check(self.base).returncode, 0)

    def test_new_package_cannot_self_declare_historical(self):
        new_dir = self.repo / "evidence/runs/forged"
        new_dir.mkdir()
        (new_dir / "manifest.json").write_text(json.dumps({
            "run_id": "forged", "execution_status": "COMPLETE", "hypothesis": "forged"
        }))
        manifest_path = self.repo / "evidence/retained-digests.json"
        document = json.loads(manifest_path.read_text())
        relative = "evidence/runs/forged/manifest.json"
        document["packages"]["forged"] = {
            "historical": True,
            "files": {relative: hashlib.sha256((self.repo / relative).read_bytes()).hexdigest()},
        }
        manifest_path.write_text(json.dumps(document))
        run_git(self.repo, "add", ".")
        run_git(self.repo, "commit", "-m", "forge historical run")
        self.assertNotEqual(self._check(self.base).returncode, 0)

    def test_existing_declaration_cannot_be_modified(self):
        self._write_declarations({
            "run-one": {
                "scenario": "scenario-a",
                "retained_package": "evidence/runs/run-one",
            }
        })
        run_git(self.repo, "add", ".")
        run_git(self.repo, "commit", "-m", "declare run")
        base = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=self.repo, text=True).strip()
        self._write_declarations({
            "run-one": {
                "scenario": "changed",
                "retained_package": "evidence/runs/run-one",
            }
        })
        self.assertNotEqual(self._check(base).returncode, 0)

    def test_existing_declaration_cannot_be_deleted(self):
        self._write_declarations({
            "run-one": {
                "scenario": "scenario-a",
                "retained_package": "evidence/runs/run-one",
            }
        })
        run_git(self.repo, "add", ".")
        run_git(self.repo, "commit", "-m", "declare run")
        base = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=self.repo, text=True).strip()
        self._write_declarations({})
        self.assertNotEqual(self._check(base).returncode, 0)

    def test_declaration_cannot_redirect_retained_package(self):
        self._write_declarations({
            "run-one": {
                "scenario": "scenario-a",
                "retained_package": "evidence/runs/other",
            }
        })
        self.assertNotEqual(self._check(self.base).returncode, 0)

    def test_declaration_rejects_unknown_historical_property(self):
        self._write_declarations({
            "run-one": {
                "scenario": "scenario-a",
                "retained_package": "evidence/runs/run-one",
                "historical": True,
            }
        })
        self.assertNotEqual(self._check(self.base).returncode, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
