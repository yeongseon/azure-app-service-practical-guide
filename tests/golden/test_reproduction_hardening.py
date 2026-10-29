"""Synthetic package attacks against the independent-reproduction gate (#179)."""

import hashlib
import json
import unittest

import test_reproduction as fixtures

repro = fixtures.repro


class ReproductionHardeningTests(unittest.TestCase):
    def setUp(self):
        self.packages = fixtures.RunPackageMutationTests()
        self.packages.setUp()
        self.addCleanup(self.packages.tearDown)
        self.runs = self.packages.runs
        for run_id in ("original", "replay"):
            self.packages._run(
                run_id, fixtures.record()["scenario"], f"rg-{run_id}", f"app-{run_id}")
        self.path = self.packages._record(attestation={
            "url": "https://github.com/o/r/pull/1#pullrequestreview-1",
            "reviewer_login": "reviewer",
            "original_operator_login": "operator",
            "pr_author_login": "author",
        })

    def _replace(self, relative: str, updates: dict) -> None:
        path = self.runs / relative
        document = json.loads(path.read_text())
        path.write_text(json.dumps(document | updates))

    def _refresh(self, run_id: str) -> None:
        """Keep derived verdicts and digests valid so only the attack is tested."""
        directory = self.runs / run_id
        (directory / "result.json").unlink()
        result = repro.evaluator.evaluate(directory)
        (directory / "result.json").write_text(json.dumps(result))
        self._replace(f"{run_id}/provenance.json", {"digests": {
            name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
            for name in ("manifest.json", "evidence.json", "result.json")
        }})

    def _check(self):
        return repro.check(self.path, attestation_verifier=lambda attestation: True)

    def test_distinct_later_capture_with_verified_attestation_is_reproduced(self):
        # Given: distinct observations, resources, identities and valid cleanup.
        # When: the external identity verifier confirms the attestation.
        result = self._check()
        # Then: a qualifying synthetic pair still passes the offline gate.
        self.assertEqual(result["reproduction_result"], "REPRODUCED")
        self.assertTrue(result["passed"])

    def test_rewrapped_observations_are_refused(self):
        # Given: copied observations under different identity and provenance.
        original = json.loads((self.runs / "original/evidence.json").read_text())
        self._replace("replay/evidence.json", {
            "observations": original["observations"],
            "collector": "another-collector",
            "runner_source_commit": "3e0442bb19b966766598ffeae1fb47f3f6960837",
            "capture_provenance": "primary",
            "incomplete_fields": [],
        })
        self._refresh("replay")
        # When / Then: wrapper changes cannot make reused observations pass.
        with self.assertRaises(repro.ReproductionError):
            self._check()

    def test_missing_cleanup_record_is_refused_for_each_run(self):
        for run_id in ("original", "replay"):
            with self.subTest(run_id=run_id):
                # Given: provenance claims cleanup but the record is absent.
                path = self.runs / run_id / "cleanup.json"
                content = path.read_text()
                path.unlink()
                try:
                    # When / Then: each package must supply cleanup evidence.
                    with self.assertRaisesRegex(repro.ReproductionError, run_id):
                        self._check()
                finally:
                    path.write_text(content)

    def test_invalid_cleanup_record_is_refused_for_each_run(self):
        for run_id in ("original", "replay"):
            for update in ({"run_id": "other-run"}, {"cleanup_verified": False},
                           {"final_group_exists": True}, {"cleanup_verified": 1},
                           {"final_group_exists": 0}):
                with self.subTest(run_id=run_id, update=update):
                    # Given: an otherwise valid package has invalid cleanup.
                    path = self.runs / run_id / "cleanup.json"
                    content = path.read_text()
                    self._replace(f"{run_id}/cleanup.json", update)
                    try:
                        # When / Then: the error identifies the affected run.
                        with self.assertRaisesRegex(repro.ReproductionError, run_id):
                            self._check()
                    finally:
                        path.write_text(content)

    def test_cleanup_provenance_disagreement_is_refused(self):
        # Given: cleanup claims success while provenance says it was unverified.
        self._replace("replay/provenance.json", {"cleanup_verified": False})
        # When / Then: contradictory cleanup claims cannot qualify.
        with self.assertRaisesRegex(repro.ReproductionError, "replay"):
            self._check()

    def test_replay_capture_must_be_strictly_later(self):
        for captured in ("2026-09-27T02:00:00Z", "2026-09-27T03:00:00Z",
                         "2026-09-27T04:00:00+01:00"):
            with self.subTest(captured_at=captured):
                # Given: distinct observations but an earlier or equal instant.
                self._replace("replay/manifest.json", {"captured_at": captured})
                self._replace("replay/evidence.json", {"captured_at": captured})
                self._refresh("replay")
                # When / Then: offset spelling does not change temporal order.
                with self.assertRaises(repro.ReproductionError):
                    self._check()

    def test_display_identity_variants_are_not_independent(self):
        for reviewer, operator in (("Alice", "alice"), ("alice", " alice "),
                                   (" Alice ", "alice")):
            with self.subTest(reviewer=reviewer, operator=operator):
                # Given: the same display identity with different formatting.
                value = json.loads(self.path.read_text())
                self.path.write_text(json.dumps(value | {
                    "reviewer": reviewer, "original_operator": operator}))
                # When: the complete checker receives an approving verifier.
                result = self._check()
                # Then: formatting cannot turn the operator into another human.
                self.assertEqual(result["reproduction_result"], "NOT_INDEPENDENT")

    def test_attestation_identity_whitespace_collisions_are_not_independent(self):
        for field in ("original_operator_login", "pr_author_login"):
            with self.subTest(field=field):
                # Given: two logins differ only by surrounding whitespace.
                value = json.loads(self.path.read_text())
                value["attestation"] = {
                    "url": "https://github.com/o/r/pull/1#pullrequestreview-1",
                    "reviewer_login": "reviewer",
                    "original_operator_login": "operator",
                    "pr_author_login": "author",
                } | {field: " reviewer "}
                self.path.write_text(json.dumps(value))
                # When: a permissive external verifier is supplied.
                result = self._check()
                # Then: local normalization still rejects the identity collision.
                self.assertEqual(result["reproduction_result"], "NOT_INDEPENDENT")


if __name__ == "__main__":
    unittest.main(verbosity=2)
