"""The customer handover must be readable from this checkout alone."""

import json
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "customer"
PAGES = sorted(DOCS.glob("*.md"))


def markdown_without_code(text: str) -> str:
    return re.sub(r"^```[^\n]*\n.*?^```\s*$", "", text, flags=re.MULTILINE | re.DOTALL)


def heading_anchors(text: str) -> set[str]:
    anchors = set()
    for heading in re.findall(r"^#{1,6}\s+(.+)$", markdown_without_code(text), re.MULTILINE):
        anchors.add(re.sub(r"[^\w-]", "", heading.lower().replace(" ", "-")))
    return anchors


@pytest.mark.parametrize("page", PAGES, ids=lambda path: path.name)
def test_customer_guide_links_resolve_inside_checkout(page):
    text = markdown_without_code(page.read_text(encoding="utf-8"))
    links = re.findall(r"\[[^\]]+\]\(([^)]+)\)", text)
    for link in links:
        destination = urlsplit(link)
        assert not destination.scheme and not destination.netloc, (
            f"{page.name} must not require external documentation: {link}"
        )
        target = (page.parent / unquote(destination.path)).resolve()
        assert target.is_relative_to(ROOT), f"Link leaves checkout: {link}"
        assert target.exists(), f"Missing target in {page.name}: {link}"
        if destination.fragment:
            assert target.suffix == ".md"
            assert unquote(destination.fragment) in heading_anchors(target.read_text(encoding="utf-8")), (
                f"Missing heading in {page.name}: {link}"
            )


def test_readme_uses_local_customer_entrypoint():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "[customer deployment runbook](docs/customer/azure-devops-markdown-poc.md)" in readme
    assert "[complete customer documentation bundle](docs/customer/README.md)" in readme
    assert DOCS.joinpath("README.md").is_file()
    assert len(PAGES) >= 5
    for page in PAGES:
        assert f"]({page.relative_to(ROOT).as_posix()})" in readme
    for relative in (
        "samples/customer-poc/azd-env.example.json",
        "samples/customer-poc/ingestion-state.parameters.example.json",
        "samples/customer-poc/vpn-clientconfig.example.xml",
        "infra/ingestion-state.bicep",
    ):
        assert f"]({relative})" in readme


def test_readme_links_selected_component_sources():
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for component in manifest["components"]:
        if component["name"] in {"agent-app-ui", "agent-app-orchestrator"}:
            repository = component["repo"].removesuffix(".git")
            assert f"]({repository}/tree/{component['commit']})" in readme


def test_customer_guide_records_current_component_pins():
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    guide = (DOCS / "azure-devops-markdown-poc.md").read_text(encoding="utf-8")
    for component in manifest["components"]:
        if component["name"] in {"agent-app-ui", "agent-app-orchestrator"}:
            assert component["commit"] in guide
            assert component["branch"] in guide


def test_documented_markdown_target_matches_profile():
    profile = json.loads(
        (ROOT / "samples/customer-poc/azd-env.example.json").read_text(encoding="utf-8")
    )["inputs"]
    configuration = (DOCS / "configuration.md").read_text(encoding="utf-8")
    for name in (
        "SEARCH_RAG_SCHEMA", "SEARCH_RAG_INDEX_NAME",
        "FOUNDRY_IQ_SEARCH_INDEX_NAME", "FOUNDRY_IQ_SEMANTIC_CONFIGURATION_NAME",
    ):
        assert f"{name}={profile[name]}" in configuration


def test_vpn_dns_fragment_has_resolver_placeholder_and_service_suffixes():
    namespace = "{http://schemas.datacontract.org/2004/07/}"
    fragment = ElementTree.parse(ROOT / "samples/customer-poc/vpn-clientconfig.example.xml").getroot()
    assert fragment.tag == f"{namespace}clientconfig"
    assert "{http://www.w3.org/2001/XMLSchema-instance}nil" not in fragment.attrib
    servers = fragment.findall(f"{namespace}dnsservers/{namespace}dnsserver")
    assert [server.text for server in servers] == ["REPLACE_WITH_CUSTOMER_RESOLVER_IP"]
    suffixes = [item.text for item in fragment.findall(f"{namespace}dnssuffixes/{namespace}dnssuffix")]
    assert len(suffixes) == len(set(suffixes))
    assert set(suffixes) == {
        ".vault.azure.net", ".vaultcore.azure.net", ".azconfig.io", ".search.windows.net",
        ".documents.azure.com", ".blob.core.windows.net", ".azurecr.io",
        ".openai.azure.com", ".services.ai.azure.com", ".cognitiveservices.azure.com",
        ".azurecontainerapps.io", ".monitor.azure.com", ".opinsights.azure.com",
        ".applicationinsights.io", ".azure.automation.net",
    }


def test_private_access_requires_suffixes_reimport_and_normal_dns_validation():
    guide = (DOCS / "private-access.md").read_text(encoding="utf-8")
    for required in (
        "vpn-clientconfig.example.xml", "i:nil", "dnssuffix", "dnsserver",
        "reimport", "Get-DnsClientNrptPolicy -Effective",
        "Resolve-DnsName $hostnameToCheck -Server $resolverAddress",
        "Resolve-DnsName $hostnameToCheck -Type A",
    ):
        assert required in guide
