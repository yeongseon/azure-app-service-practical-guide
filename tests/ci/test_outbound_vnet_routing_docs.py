"""Offline guard for the outbound VNet routing documentation.

Issue #254: the guide explained Route All mostly through the legacy
WEBSITE_VNET_ROUTE_ALL app setting. Microsoft Learn recommends the
outboundVnetRouting.* site properties and keeps the legacy names supported.
This is a static check of the guide's own text; it reads no Azure resource and
proves no routing behavior.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
NETWORKING = (DOCS / "platform/networking.md").read_text(encoding="utf-8")
SECTION = NETWORKING.split("#### Outbound VNet routing properties")[1].split("\n#### ")[0]
PROPERTIES = (
    "allTraffic", "applicationTraffic", "imagePullTraffic",
    "contentShareTraffic", "backupRestoreTraffic", "managedIdentityTraffic",
)
LEGACY = (
    "vnetRouteAllEnabled", "WEBSITE_VNET_ROUTE_ALL", "vnetImagePullEnabled",
    "WEBSITE_PULL_IMAGE_OVER_VNET", "vnetContentShareEnabled", "WEBSITE_CONTENTOVERVNET",
    "vnetBackupRestoreEnabled",
)
ANCHOR = "platform/networking.md#outbound-vnet-routing-properties"


class OutboundVnetRoutingDocsTests(unittest.TestCase):
    def test_every_documented_property_and_legacy_name_is_listed(self):
        for name in PROPERTIES + LEGACY:
            with self.subTest(name=name):
                self.assertIn(f"`{name}", SECTION)

    def test_all_traffic_is_recommended_and_legacy_names_are_not_called_unsupported(self):
        self.assertIn("recommends `outboundVnetRouting.allTraffic`", SECTION)
        self.assertIn("still supported", SECTION)
        for word in ("deprecated", "unsupported", "obsolete", "retired"):
            with self.subTest(word=word):
                self.assertNotRegex(SECTION, rf"\b{word}\b")

    def test_application_and_configuration_routing_are_distinguished(self):
        self.assertIn("configuration traffic keeps using the public route", SECTION)
        self.assertIn("`allTraffic=true` already routes all configuration traffic", SECTION)
        self.assertIn("ports 443 and 445", SECTION)
        self.assertIn("The portal cannot set `allTraffic`", SECTION)

    def test_inspection_example_is_read_only_and_treats_absence_as_unknown(self):
        fence = re.search(r"```bash\n(.*?)\n```", SECTION, re.DOTALL).group(1)
        lines = [" ".join(line.split()) for line in fence.replace("\\\n", " ").split("\n") if line.strip()]
        self.assertEqual(lines, ['az resource show --ids "$APP_RESOURCE_ID" --api-version 2025-03-01 --output json'])
        self.assertIn("An absent property is **UNKNOWN**, not `false`", SECTION)
        self.assertNotIn("--query", fence)

    def test_the_section_states_what_the_property_does_not_prove(self):
        for phrase in ("What the property proves", "does not prove", "DNS", "firewall", "source IP", "private endpoint"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, SECTION)
        self.assertIn("RFC 1918", SECTION)
        self.assertIn("four different mechanisms", SECTION)

    def test_the_existing_playbooks_are_linked_not_duplicated(self):
        for target in (
            "snat-or-application-issue.md",
            "dns-resolution-vnet-integrated-app-service.md",
            "private-endpoint-custom-dns-route-confusion.md",
        ):
            with self.subTest(target=target):
                self.assertIn(target, SECTION)
                self.assertTrue(any(DOCS.rglob(target)))

    def test_related_pages_link_to_the_canonical_section(self):
        for page in ("platform/storage-connectivity.md", "operations/networking.md", "reference/troubleshooting.md"):
            with self.subTest(page=page):
                text = (DOCS / page).read_text(encoding="utf-8")
                self.assertIn("networking.md#outbound-vnet-routing-properties", text)

    def test_the_operations_procedure_prefers_the_property_and_names_the_legacy_setting(self):
        text = (DOCS / "operations/networking.md").read_text(encoding="utf-8")
        self.assertIn("--set properties.outboundVnetRouting.allTraffic=true", text)
        self.assertNotIn('--settings "WEBSITE_VNET_ROUTE_ALL=1"', text)
        self.assertIn("legacy `WEBSITE_VNET_ROUTE_ALL=1` app setting is still supported", text)

    def test_the_legacy_check_page_says_an_empty_result_is_not_proof(self):
        text = (DOCS / "reference/troubleshooting.md").read_text(encoding="utf-8")
        self.assertIn("an empty result here does not mean route-all is off", text)

    def test_the_storage_guide_separates_content_share_routing(self):
        text = (DOCS / "platform/storage-connectivity.md").read_text(encoding="utf-8")
        self.assertIn("outboundVnetRouting.contentShareTraffic", text)
        self.assertIn("outboundVnetRouting.allTraffic", text)


if __name__ == "__main__":
    unittest.main()
