"""Optional VPN resource contracts and parallel application identity selection."""

import json
from pathlib import Path
import subprocess
import shutil

import pytest

from config.appdefinition.roles import RoleAssignmentError, _resolve_identity
from config.deployment import appconfig

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def compiled(tmp_path_factory):
    destination = tmp_path_factory.mktemp("vpn-template") / "main.json"
    subprocess.run(
        [shutil.which("az"), "bicep", "build", "--file", str(ROOT / "infra" / "main.bicep"),
         "--outfile", str(destination), "--only-show-errors"],
        check=True, capture_output=True, text=True,
    )
    return json.loads(destination.read_text(encoding="utf-8-sig"))


def test_vpn_is_default_off_and_keeps_root_output_limit(compiled):
    assert compiled["parameters"]["deployVpnGateway"]["defaultValue"] is False
    assert len(compiled["outputs"]) <= 64
    deployment = compiled["resources"]["pointToSiteVpn"]
    assert deployment["condition"] == "[parameters('deployVpnGateway')]"
    assert "subscription().tenantId" in str(deployment["properties"]["parameters"]["tenantId"])
    assert "vpnLayoutValidation" in str(compiled["resources"]["virtualNetwork"]["dependsOn"])
    assert "vpnLayoutValidation" in str(compiled["resources"]["virtualNetworkSubnets"]["dependsOn"])


def test_vpn_uses_entra_and_a_routable_private_dns_server(compiled):
    template = compiled["resources"]["pointToSiteVpn"]["properties"]["template"]
    resources = {resource["type"]: resource for resource in template["resources"]}
    properties = resources["Microsoft.Network/virtualNetworkGateways"]["properties"]
    assert properties["gatewayType"] == "Vpn"
    assert properties["vpnType"] == "RouteBased"
    assert properties["vpnClientConfiguration"]["vpnAuthenticationTypes"] == ["AAD"]
    assert properties["vpnClientConfiguration"]["vpnClientProtocols"] == ["OpenVPN"]
    assert "vpnClientRootCertificates" not in properties["vpnClientConfiguration"]
    assert resources["Microsoft.Network/publicIPAddresses"]["sku"]["name"] == "Standard"
    assert resources["Microsoft.Network/dnsResolvers/inboundEndpoints"]["properties"]["ipConfigurations"][0]["privateIpAllocationMethod"] == "Static"
    assert "dnsServerAddress" in template["outputs"]
    assert "resourceId" in template["outputs"]


def test_reserved_subnets_and_layout_validation_are_explicit(compiled):
    layout = compiled["resources"]["vpnLayoutValidation"]["properties"]["template"]
    assert "cidr" in str(layout).lower()
    assert "non-overlapping" in layout["outputs"]["validated"]["value"]
    assert "networkIsolation=true" in layout["outputs"]["validated"]["value"]
    source = (ROOT / "infra" / "modules" / "networking" / "subnets.bicep").read_text()
    assert "'GatewaySubnet'" in source.split("var invalidNsgSubnets =", 1)[1].splitlines()[0]
    root = (ROOT / "infra" / "main.bicep").read_text(encoding="utf-8")
    assert "name: deployVpnGateway ? 'GatewaySubnet' : gatewaySubnetName" in root
    assert "delegation: 'Microsoft.Network/dnsResolvers'" in root


def test_internal_apps_get_wildcard_dns_in_the_vpn_vnet(compiled):
    deployment = compiled["resources"]["containerAppsPrivateDns"]
    assert "_networkIsolation" in deployment["condition"]
    assert "policyManagedPrivateDns" in deployment["condition"]
    resources = deployment["properties"]["template"]["resources"]
    wildcard = next(item for item in resources if item["type"] == "Microsoft.Network/privateDnsZones/A")
    assert "*" in wildcard["name"]
    assert wildcard["properties"]["aRecords"] == [{"ipv4Address": "[parameters('staticIp')]"}]
    link = next(item for item in resources if item["type"].endswith("/virtualNetworkLinks"))
    assert link["properties"]["registrationEnabled"] is False


def test_parallel_app_identity_requires_exact_selected_name():
    rows = [
        {"name": "old-ui", "identity": {"principalId": "old-principal"}},
        {"name": "private-ui", "identity": {"principalId": "new-principal"}},
    ]

    def run_az(arguments, *, required=True):
        assert arguments[:2] == ["containerapp", "list"]
        return json.dumps(rows)

    assert _resolve_identity("frontend", "group", run_az, "sub", "private-ui")[0] == "new-principal"
    with pytest.raises(RoleAssignmentError, match="found 2"):
        _resolve_identity("frontend", "group", run_az, "sub")
    with pytest.raises(RoleAssignmentError, match="found 0"):
        _resolve_identity("frontend", "group", run_az, "sub", "unknown")


def test_runtime_configuration_selects_parallel_apps(monkeypatch):
    monkeypatch.setattr(appconfig, "_container_app", lambda group, name, **kwargs: {
        "fqdn": name + ".example.test", "principalId": name,
    })
    values = appconfig.build_settings({
        "AZURE_RESOURCE_GROUP": "group",
        "RESOURCE_TOKEN": "token",
        "DEPLOYMENT_TOPOLOGY": "classic",
        "DEPLOY_INGESTION_CONTAINER_APP": "false",
        "RETRIEVAL_BACKEND": "foundry_iq",
        "FOUNDRY_IQ_PATTERN": "searchIndex",
        "FOUNDRY_IQ_KNOWLEDGE_SOURCE_KIND": "searchIndex",
        "SEARCH_RAG_INDEX_NAME": "kb-sections-v1",
        "FRONTEND_APP_NAME": "private-ui",
        "ORCHESTRATOR_APP_NAME": "private-orchestrator",
    })
    assert values["FRONTEND_APP_NAME"] == "private-ui"
    assert values["ORCHESTRATOR_APP_NAME"] == "private-orchestrator"
    assert values["ORCHESTRATOR_BASE_URL"] == "https://private-orchestrator.example.test"
    assert "dataingest" not in values["CONTAINER_APPS"]
