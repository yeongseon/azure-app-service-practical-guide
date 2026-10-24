import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
CONTRACT = (ROOT / "docs/meta/series-contract.md").read_text()
CLASSIFICATION = json.loads((ROOT / "labs/golden-classification.json").read_text())


class SeriesLabContractTests(unittest.TestCase):
    def test_contract_count_matches_classified_scenarios(self):
        self.assertIn(f"{len(CLASSIFICATION['labs'])} current scenario directories", CONTRACT)

    def test_contract_records_app_service_specific_models(self):
        for model in ("code deployment", "custom containers", "Windows `D:\\home`", "Linux `/home`"):
            with self.subTest(model=model):
                self.assertIn(model, CONTRACT)

    def test_contract_names_the_published_series_contract_without_inventing_requirements(self):
        self.assertIn("azure-architecture-practical-guide/contributing/series-lab-contract/", CONTRACT)
        self.assertIn("**Variant A**", CONTRACT)
        self.assertIn("The contract does not prescribe a deployment shape or a storage model.", CONTRACT)
        # The reconciliation must not present local App Service choices as series expectations.
        self.assertNotIn("Series expectation", CONTRACT)

    def test_contract_keeps_work_local_and_uses_priority_labels(self):
        self.assertIn("closeable in this repository", CONTRACT)
        self.assertIn(".github/priority-labels.json", CONTRACT)
        self.assertIn("#217", CONTRACT)


if __name__ == "__main__":
    unittest.main(verbosity=2)
