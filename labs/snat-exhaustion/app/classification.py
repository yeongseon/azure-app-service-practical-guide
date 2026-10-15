"""Shared outcome classification for the SNAT comparative experiment.

Both outbound paths import this module so that connection pooling is the
only independent variable between them. Neither handler may classify a
result on its own.

Why this module exists as a separate file: the two handlers previously
contained the *identical* predicate `200 <= status < 500`, so reading them
side by side suggested they agreed. They did not.
`urllib.request.urlopen` raises `HTTPError` on 4xx, so the comparison
never executed and the exception handler counted the response a failure,
while `requests` returned the 4xx and the comparison counted it a success.
The same HTTP response was therefore a failure on one transport and a
success on the other, which made the classification itself a confounder
for the variable under test.

A defect of that shape cannot be fixed by re-checking the numeric bands,
because the bands already matched. It is fixed by giving both transports
one implementation and testing the *observed classification of a real
response* rather than the source text of either branch.

Three outcomes, deliberately distinct:

``success``
    A completed HTTP round trip that the server answered successfully.

``failure``
    A completed HTTP round trip that the server answered unsuccessfully.
    The connection worked; the request did not.

``transport_failure``
    No usable HTTP response: the connection could not be established or
    completed. **This is the SNAT signal.** Port exhaustion surfaces as
    connection-level errors such as ``EADDRNOTAVAIL``, refusals and
    timeouts, not as HTTP status codes. Folding it into ``failure`` would
    discard the only outcome that discriminates the hypothesis.
"""

from __future__ import annotations

SUCCESS = "success"
FAILURE = "failure"
TRANSPORT_FAILURE = "transport_failure"

OUTCOMES = (SUCCESS, FAILURE, TRANSPORT_FAILURE)


def classify_status(status) -> str:
    """Classify a completed HTTP round trip by its status code.

    The caller must supply a status from a real response. ``None`` is
    rejected rather than defaulted, because silently treating "no status"
    as either outcome is how a transport failure gets recorded as an HTTP
    result.

    >>> classify_status(200)
    'success'
    >>> classify_status(301)
    'success'
    >>> classify_status(404)
    'failure'
    >>> classify_status(503)
    'failure'
    >>> classify_status(None)
    Traceback (most recent call last):
        ...
    ValueError: HTTP status must be an int, got None
    """
    if isinstance(status, bool) or not isinstance(status, int):
        raise ValueError(f"HTTP status must be an int, got {status!r}")
    if not 100 <= status <= 599:
        raise ValueError(f"HTTP status out of range: {status!r}")
    return SUCCESS if status < 400 else FAILURE


def classify_transport_failure(exc: BaseException) -> str:
    """Classify an exception raised before any HTTP response was obtained.

    >>> classify_transport_failure(OSError("connection refused"))
    'transport_failure'
    """
    return TRANSPORT_FAILURE


def summarise(outcomes) -> dict:
    """Count outcomes without deciding what caused them.

    The collector reports counts; assertions and the evaluator decide
    whether those counts support the hypothesis. Returning a verdict here
    would let the workload grade its own experiment.

    >>> summarise(["success", "transport_failure", "failure", "success"])
    {'success': 2, 'failure': 1, 'transport_failure': 1, 'total': 4}
    """
    counts = {SUCCESS: 0, FAILURE: 0, TRANSPORT_FAILURE: 0}
    total = 0
    for outcome in outcomes:
        if outcome not in counts:
            raise ValueError(f"unknown outcome: {outcome!r}")
        counts[outcome] += 1
        total += 1
    counts["total"] = total
    return counts
