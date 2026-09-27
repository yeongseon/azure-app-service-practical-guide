"""Golden Scenario B: the two outbound paths must classify identically (#177).

The SNAT lab compares `/outbound` (no connection pooling, urllib) against
`/outbound-fixed` (pooled, requests). Pooling is supposed to be the only
independent variable, but the two handlers historically applied different
success semantics, which made the classification itself a confounder.

The defect is invisible to side-by-side reading: both handlers contained
the identical predicate `200 <= status < 500`. The divergence came from
`urllib.request.urlopen` *raising* `HTTPError` on 4xx, so the comparison
never ran and the exception handler counted it a failure, while `requests`
returned the 4xx and the comparison counted it a success.

These tests therefore assert on the *observed classification of a real
response*, never on the source text of the two branches.
"""

import sys

sys.dont_write_bytecode = True

import http.server
import importlib.util
import pathlib
import socketserver
import threading
import json
import tempfile
import unittest
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "classification", ROOT / "labs/snat-exhaustion/app/classification.py")
classification = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(classification)


class _Handler(http.server.BaseHTTPRequestHandler):
    status = 200

    def do_GET(self):
        self.send_response(self.status)
        self.end_headers()
        self.wfile.write(b"body")

    def log_message(self, *args):
        pass


class _Server:
    def __enter__(self):
        self.srv = socketserver.TCPServer(("127.0.0.1", 0), _Handler)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        return f"http://127.0.0.1:{self.srv.server_address[1]}/"

    def __exit__(self, *exc):
        self.srv.shutdown()
        self.srv.server_close()


def classify_via_urllib(url, timeout=5):
    """Mirror the no-pooling handler using the shared classifier."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return classification.classify_status(resp.status)
    except urllib.error.HTTPError as exc:
        return classification.classify_status(exc.code)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return classification.classify_transport_failure(exc)


def classify_via_requests(url, timeout=5):
    """Mirror the pooled handler using the shared classifier."""
    import requests as rq
    try:
        response = rq.get(url, timeout=timeout)
        return classification.classify_status(response.status_code)
    except rq.RequestException as exc:
        return classification.classify_transport_failure(exc)


class ClassifierUnitTests(unittest.TestCase):
    def test_2xx_is_success(self):
        self.assertEqual(classification.classify_status(200), "success")

    def test_4xx_is_a_failure_not_a_success(self):
        """A 4xx is a completed round trip that did not succeed.

        Whichever way this is decided, both transports must agree. Counting
        it a success on one path and a failure on the other is what makes
        the classification a confounder for pooling.
        """
        self.assertEqual(classification.classify_status(404), "failure")

    def test_5xx_is_failure(self):
        self.assertEqual(classification.classify_status(503), "failure")

    def test_transport_failure_is_distinct_from_an_http_failure(self):
        outcome = classification.classify_transport_failure(OSError("refused"))
        self.assertEqual(outcome, "transport_failure")
        self.assertNotEqual(outcome, classification.classify_status(503))

    def test_unknown_status_is_rejected(self):
        with self.assertRaises(ValueError):
            classification.classify_status(None)


class TransportParityTests(unittest.TestCase):
    """The same response must classify identically on both transports."""

    def _both(self, status):
        _Handler.status = status
        with _Server() as url:
            return classify_via_urllib(url), classify_via_requests(url)

    def test_404_classifies_identically(self):
        urllib_outcome, requests_outcome = self._both(404)
        self.assertEqual(
            urllib_outcome, requests_outcome,
            msg="a 404 must not be a failure on one transport and a success on the other")

    def test_200_classifies_identically(self):
        self.assertEqual(*self._both(200))

    def test_500_classifies_identically(self):
        self.assertEqual(*self._both(500))

    def test_every_sampled_status_agrees_across_transports(self):
        for status in (200, 204, 301, 400, 401, 403, 404, 429, 500, 502, 503):
            with self.subTest(status=status):
                self.assertEqual(*self._both(status))


class GoldenContractTests(unittest.TestCase):
    """Scenario B shipped a classifier and a suite but no Golden contract.

    Review found the review itself claiming all three scenarios carried
    contracts while this one carried none, so the contract is pinned here.
    """

    LAB = pathlib.Path(__file__).resolve().parents[2] / "labs/snat-exhaustion/golden"

    @classmethod
    def setUpClass(cls):
        import importlib.util
        root = pathlib.Path(__file__).resolve().parents[2]
        spec = importlib.util.spec_from_file_location(
            "evb", root / "scripts/golden/evaluate_run.py")
        cls.ev = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.ev)
        cls.template = json.loads((cls.LAB / "manifest.template.json").read_text())
        cls.classification = json.loads(
            (cls.LAB / "evidence-classification.json").read_text())

    def _run(self, observations, execution="COMPLETE"):
        directory = pathlib.Path(tempfile.mkdtemp()) / "run"
        directory.mkdir(parents=True)
        manifest = dict(self.template)
        manifest.update(run_id="20260927T050607Z-b1c2d3",
                        resource_id="/subscriptions/x/rg/app",
                        captured_at="2026-09-27T05:06:07Z",
                        execution_status=execution)
        (directory / "manifest.json").write_text(json.dumps(manifest))
        (directory / "evidence.json").write_text(json.dumps({
            "run_id": manifest["run_id"],
            "captured_at": manifest["captured_at"],
            "observations": observations}))
        return directory

    COMPLETE = {"baseline_success_count": 50, "load_transport_failure_count": 7,
                "destination_health_status": 200, "load_http_error_count": 0,
                "recovery_success_count": 50}

    def test_the_template_ships_unrun(self):
        self.assertEqual(self.template["execution_status"], "NOT_RUN")
        self.assertIsNone(self.template["run_id"])
        self.assertIsNone(self.template["captured_at"])

    def test_a_template_alone_yields_no_verdict(self):
        result = self.ev.evaluate(self._run(self.COMPLETE, execution="NOT_RUN"))
        self.assertEqual(result["hypothesis_status"], "NOT_TESTED")

    def test_a_complete_run_with_full_evidence_is_supported(self):
        self.assertEqual(
            self.ev.evaluate(self._run(self.COMPLETE))["hypothesis_status"], "SUPPORTED")

    def test_an_unhealthy_destination_refuses_the_hypothesis(self):
        """The discriminating assertion that separates the two explanations.

        If the destination is itself unhealthy, transport failures are
        explained without port exhaustion and the hypothesis must not stand.
        """
        evidence = dict(self.COMPLETE, destination_health_status=503)
        self.assertEqual(
            self.ev.evaluate(self._run(evidence))["hypothesis_status"], "CONTRADICTED")

    def test_http_errors_instead_of_transport_failures_refuse_it(self):
        evidence = dict(self.COMPLETE, load_http_error_count=12)
        self.assertEqual(
            self.ev.evaluate(self._run(evidence))["hypothesis_status"], "CONTRADICTED")

    def test_a_missing_discriminator_is_inconclusive_not_supported(self):
        evidence = dict(self.COMPLETE)
        del evidence["destination_health_status"]
        self.assertEqual(
            self.ev.evaluate(self._run(evidence))["hypothesis_status"], "INCONCLUSIVE")

    def test_no_recovery_prevents_support(self):
        evidence = dict(self.COMPLETE, recovery_success_count=0)
        self.assertEqual(
            self.ev.evaluate(self._run(evidence))["hypothesis_status"], "CONTRADICTED")

    def test_every_role_and_claim_level_is_from_the_frozen_vocabulary(self):
        for assertion in self.template["assertions"]:
            self.assertIn(assertion["role"], self.ev.EVIDENCE_ROLES)
            self.assertIn(assertion["claim_level"], self.ev.CLAIM_LEVELS)

    def test_the_contract_declares_a_discriminating_assertion(self):
        roles = {a["role"] for a in self.template["assertions"]}
        self.assertIn("discriminating", roles)
        self.assertIn("control", roles)
        self.assertIn("recovery", roles)

    def test_the_missing_collector_is_disclosed_not_hidden(self):
        gaps = " ".join(self.classification["known_gaps"]).lower()
        self.assertIn("destination_health_status", gaps)


if __name__ == "__main__":
    unittest.main(verbosity=1)
