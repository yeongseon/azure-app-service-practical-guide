from __future__ import annotations

import importlib.util
import json
from dataclasses import dataclass
from pathlib import Path
import tempfile
from typing import TypeAlias
import unittest


ROOT = Path(__file__).resolve().parents[2]
EVALUATOR = ROOT / "scripts/golden/evaluate_run.py"
RUN_ID = "run-A"
CAPTURED_AT = "2026-09-27T00:00:00Z"
JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]


@dataclass(frozen=True, slots=True)
class NegativeCase:
    name: str
    evidence: dict[str, JsonValue] | str | None
    assertions: tuple[dict[str, JsonValue], ...]
    expected: str
    mutation_before: str
    mutation_after: str


CASES = (
    NegativeCase(
        "missing", None,
        ({"id": "status", "field": "status", "equals": 503},),
        "INCONCLUSIVE", 'if field not in evidence:\n        return "INCONCLUSIVE"',
        'if field not in evidence:\n        return "SUPPORTED"'),
    NegativeCase(
        "empty", {},
        ({"id": "status", "field": "status", "equals": 503},),
        "INCONCLUSIVE", 'if field not in evidence:\n        return "INCONCLUSIVE"',
        'if field not in evidence:\n        return "SUPPORTED"'),
    NegativeCase(
        "malformed", "{not json",
        ({"id": "status", "field": "status", "equals": 503},),
        "MODEL_ERROR", "except json.JSONDecodeError as exc:",
        "except UnicodeDecodeError as exc:"),
    NegativeCase(
        "contradictory", {"status": 200},
        ({"id": "status", "field": "status", "equals": 503},),
        "CONTRADICTED",
        'return "SUPPORTED" if compatible(expected) and observed == expected else "CONTRADICTED"',
        'return "SUPPORTED"'),
    NegativeCase(
        "wrong-run", {"run_id": "run-B", "captured_at": CAPTURED_AT,
                      "observations": {"status": 503}},
        ({"id": "status", "field": "status", "equals": 503},),
        "MODEL_ERROR", "if declared != run_id:", "if False:"),
    NegativeCase(
        "recovery-missing", {"status": 503},
        ({"id": "status", "field": "status", "equals": 503},
         {"id": "recovery", "role": "recovery", "field": "recovery", "equals": 200}),
        "INCONCLUSIVE", 'if field not in evidence:\n        return "INCONCLUSIVE"',
        'if field not in evidence:\n        return "SUPPORTED"'),
    NegativeCase(
        "mismatched-comparison", {"status": 404},
        ({"id": "status", "field": "status", "equals": 200},),
        "CONTRADICTED",
        'return "SUPPORTED" if compatible(expected) and observed == expected else "CONTRADICTED"',
        'return "SUPPORTED"'),
)


def load_evaluator(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_run(case: NegativeCase, parent: Path) -> Path:
    run = parent / case.name
    run.mkdir()
    manifest = {
        "run_id": RUN_ID,
        "resource_id": None,
        "captured_at": CAPTURED_AT,
        "execution_status": "COMPLETE",
        "assertions": list(case.assertions),
    }
    (run / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    if case.evidence is not None:
        payload = case.evidence if isinstance(case.evidence, str) else json.dumps(case.evidence)
        (run / "evidence.json").write_text(payload, encoding="utf-8")
    return run


def classify(module, run: Path) -> str:
    try:
        return module.evaluate(run)["hypothesis_status"]
    except module.ModelError:
        return "MODEL_ERROR"
    except json.JSONDecodeError:
        return "UNEXPECTED_ERROR"


class NegativeEvidenceMatrixTests(unittest.TestCase):
    def test_seven_fixtures_have_exact_outcomes(self) -> None:
        evaluator = load_evaluator(EVALUATOR, "negative_matrix_evaluator")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for case in CASES:
                with self.subTest(category=case.name):
                    self.assertEqual(classify(evaluator, make_run(case, root)), case.expected)

    def test_each_evaluator_guard_is_mutation_sensitive(self) -> None:
        source = EVALUATOR.read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for index, case in enumerate(CASES):
                with self.subTest(category=case.name):
                    self.assertIn(case.mutation_before, source)
                    mutated = source.replace(case.mutation_before, case.mutation_after, 1)
                    module_path = root / f"evaluate_run_{index}.py"
                    module_path.write_text(mutated, encoding="utf-8")
                    evaluator = load_evaluator(module_path, f"mutated_evaluator_{index}")
                    self.assertNotEqual(
                        classify(evaluator, make_run(case, root)), case.expected,
                        msg=f"removing the {case.name} guard did not kill its fixture")


if __name__ == "__main__":
    unittest.main(verbosity=1)
