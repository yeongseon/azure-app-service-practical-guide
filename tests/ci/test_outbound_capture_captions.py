"""Outbound Networking-blade captions must describe configuration, not measured egress."""
from __future__ import annotations

import unittest
from pathlib import Path

DOCS = Path(__file__).resolve().parents[2] / "docs"
OVERSTATED = "so outbound traffic uses the listed platform outbound addresses"
CAPTION = "potential outbound address pool (not a measured egress address for any connection)"


class OutboundCaptureCaptionTests(unittest.TestCase):
    def test_no_caption_presents_configuration_as_observed_egress(self) -> None:
        offenders = [str(p.relative_to(DOCS)) for p in DOCS.rglob("*.md") if OVERSTATED in p.read_text(encoding="utf-8")]
        self.assertEqual(offenders, [])

    def test_captions_describe_potential_pool(self) -> None:
        hits = [p for p in DOCS.rglob("*.md") if CAPTION in p.read_text(encoding="utf-8")]
        self.assertEqual(len(hits), 9)

    def test_platform_blade_text_is_not_an_observation_claim(self) -> None:
        text = (DOCS / "platform/networking.md").read_text(encoding="utf-8")
        self.assertNotIn("tell you whether requests arrive", text)
        self.assertIn("Configuration alone does not establish which path a particular request actually used", text)
        self.assertIn("rather than a measured egress address", text)

    def test_snat_pages_do_not_treat_configuration_as_established_path(self) -> None:
        lab = (DOCS / "troubleshooting/lab-guides/snat-exhaustion.md").read_text(encoding="utf-8")
        self.assertNotIn("This establishes the constrained default egress capacity", lab)
        self.assertIn("[Inferred from displayed configuration]", lab)
        play = (DOCS / "troubleshooting/playbooks/outbound-network/snat-or-application-issue.md").read_text(encoding="utf-8")
        self.assertNotIn("single source of truth", play)
        self.assertNotIn("H1 is unlikely and you should pivot", play)
        self.assertIn("confirm routing and observe the connection's source address before weakening H1", play)


if __name__ == "__main__":
    unittest.main()
