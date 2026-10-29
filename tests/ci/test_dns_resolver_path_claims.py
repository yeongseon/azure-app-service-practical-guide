"""DNS captions distinguish resolver-dependent rules from displayed configuration."""
from __future__ import annotations

import unittest
from pathlib import Path
from typing import Final

DOCS: Final = Path(__file__).resolve().parents[2] / "docs/troubleshooting"
DNS: Final = "playbooks/outbound-network/dns-resolution-vnet-integrated-app-service.md"
PRIVATE: Final = "playbooks/outbound-network/private-endpoint-custom-dns-route-confusion.md"
LAB: Final = "lab-guides/dns-vnet-resolution.md"
OLD_CLAIMS: Final = (
    (DNS, (
        "Private DNS zone records are only returned when the query reaches the integration VNet those zones are linked to",
        "never consults private zones linked to any integration VNet",
        "returns private zone records **only** when the matching `privatelink.*` zone is linked to the integration VNet",
        "The captured `N/A` values indicate no route table or NSG is attached (consistent with the `Not configured` integration state from Step 1)",
    )),
    (PRIVATE, (
        "otherwise private DNS zones linked to that VNet are never consulted and the private endpoint is unreachable by design",
        "For any private-endpoint dependency, this must name an integration subnet",
        "the private endpoint path stays unreachable regardless of zone or route configuration",
        "returns the private endpoint's private IP **only if** the matching `privatelink.*` Private DNS zone is linked to the integration VNet",
        "must conditionally forward the `privatelink.*` zones to Azure DNS `168.63.129.16`",
        "The captured `N/A` values indicate no route table or NSG is attached",
    )),
    (LAB, (
        "Without VNet integration and a linked private DNS zone, a private endpoint name resolves to its public address",
    )),
)


class DnsResolverPathClaimTests(unittest.TestCase):
    def test_categorical_claims_are_absent_when_reading_dns_pages(self) -> None:
        # Given the issue's exact categorical claims, when reading each page,
        # then none may remain as an unqualified rule.
        for relative, phrases in OLD_CLAIMS:
            text = (DOCS / relative).read_text(encoding="utf-8")
            for phrase in phrases:
                with self.subTest(page=relative, phrase=phrase):
                    self.assertNotIn(phrase, text)

    def test_path_qualification_is_present_when_reading_each_page(self) -> None:
        # Given all three affected pages, when reading their DNS explanation,
        # then the configuration-versus-observation boundary stays explicit.
        for relative in (DNS, PRIVATE, LAB):
            text = (DOCS / relative).read_text(encoding="utf-8")
            with self.subTest(page=relative):
                self.assertIn("The blade displays configuration, not the observed resolution path", text)

    def test_capture_fidelity_is_preserved_when_reading_playbooks(self) -> None:
        # Given the unchanged Networking capture, when reading its captions,
        # then the macro and quoted displayed values remain intact.
        for relative in (DNS, PRIVATE):
            text = (DOCS / relative).read_text(encoding="utf-8")
            for value in (
                'shot("operations--networking--01-networking-hub")',
                "`Not configured`", "`Default (Azure-provided)`",
                "`N/A`", "`0 private endpoints`",
            ):
                with self.subTest(page=relative, value=value):
                    self.assertIn(value, text)


if __name__ == "__main__":
    _ = unittest.main()
