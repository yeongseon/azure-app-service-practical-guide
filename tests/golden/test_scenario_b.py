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


if __name__ == "__main__":
    unittest.main(verbosity=1)
