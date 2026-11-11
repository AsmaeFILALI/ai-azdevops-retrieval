"""Portable customer inputs must compose without our saved deployment state."""

import json
import hashlib
from pathlib import Path

import pytest

from config.deployment import appconfig
from config.deployment.composition import compose_parameters

ROOT = Path(__file__).resolve().parents[1]


def test_root_and_tracked_seed_are_the_same_portable_inputs():
    root = json.loads((ROOT / "main.parameters.json").read_text())
    seed = json.loads((ROOT / "infra" / "main.parameters.json").read_text())
    assert root == seed
    assert root["parameters"]["dbAccountName"]["value"] == "${COSMOS_ACCOUNT_NAME=}"


def test_pinned_consumer_contract_uses_committed_lf_bytes():
    path = ROOT / "contracts/ado-markdown-index-consumer-v1.json"
    raw = path.read_bytes()
    assert b"\r" not in raw
    expected = path.with_suffix(".json.sha256").read_text(encoding="ascii").split()[0]
    assert hashlib.sha256(raw).hexdigest() == expected


def test_profile_composes_the_private_markdown_poc_without_generated_bindings():
    profile = json.loads((ROOT / "samples/customer-poc/azd-env.example.json").read_text())
    environment = {**profile["inputs"], **profile["bootstrap"]}
    source = json.loads((ROOT / "main.parameters.json").read_text())
    result = compose_parameters(source, environment)["parameters"]
    assert [app["service_name"] for app in result["containerAppsList"]["value"]] == [
        "orchestrator", "frontend",
    ]
    settings = {item["name"]: item["value"] for item in result["additionalAppConfigurationSettings"]["value"]}
    assert settings["SEARCH_RAG_SCHEMA"] == "ado_markdown_v1"
    assert settings["AGENT_STRATEGY"] == "maf_lite"
    assert settings["CHAT_BACKEND"] == "orchestrator"
    assert result["prepareHostedAgent"]["value"] is False
    assert result["deployHostedAgent"]["value"] is False
    assert source["parameters"]["vnetAddressPrefixes"]["value"] == ["10.77.0.0/21"]
    expected_subnets = {
        "agentSubnetPrefix": "10.77.0.0/24",
        "acaEnvironmentSubnetPrefix": "10.77.1.0/24",
        "peSubnetPrefix": "10.77.2.0/26",
        "azureBastionSubnetPrefix": "10.77.2.64/26",
        "azureFirewallSubnetPrefix": "10.77.2.128/26",
        "gatewaySubnetPrefix": "10.77.2.192/26",
        "azureAppGatewaySubnetPrefix": "10.77.3.0/27",
        "jumpboxSubnetPrefix": "10.77.3.64/27",
        "devopsBuildAgentsSubnetPrefix": "10.77.3.96/27",
    }
    for parameter, cidr in expected_subnets.items():
        assert source["parameters"][parameter]["value"] == cidr
    assert environment["VPN_CLIENT_ADDRESS_POOL"] == "172.27.240.0/24"
    assert environment["VPN_DNS_RESOLVER_SUBNET_PREFIX"] == "10.77.3.128/28"
    assert not {"RESOURCE_TOKEN", "APP_CONFIG_ENDPOINT", "DATABASE_ACCOUNT_NAME", "FRONTEND_APP_NAME"} & environment.keys()
    assert profile["bootstrap"]["RUN_FROM_JUMPBOX"] == "false"
    assert profile["connected"]["RUN_FROM_JUMPBOX"] == "true"


def test_strategy_is_opt_in_and_published_by_both_paths(monkeypatch):
    source = json.loads((ROOT / "main.parameters.json").read_text())
    environment = {"DEPLOYMENT_TOPOLOGY": "classic"}
    baseline = compose_parameters(source, environment)
    assert "AGENT_STRATEGY" not in {
        row["name"] for row in baseline["parameters"]["additionalAppConfigurationSettings"]["value"]
    }
    monkeypatch.setattr(appconfig, "_container_app", lambda *args, **kwargs: {
        "fqdn": "app.example.test", "principalId": "principal",
    })
    environment.update(AZURE_RESOURCE_GROUP="example", RESOURCE_TOKEN="example")
    assert "AGENT_STRATEGY" not in appconfig.build_settings(environment)
    environment["AGENT_STRATEGY"] = "maf_lite"
    assert appconfig.build_settings(environment)["AGENT_STRATEGY"] == "maf_lite"


@pytest.mark.parametrize("value", ["not-a-strategy", "maf_lite\n", " "])
def test_invalid_strategy_fails_before_publication(value):
    source = json.loads((ROOT / "main.parameters.json").read_text())
    with pytest.raises(ValueError, match="AGENT_STRATEGY"):
        compose_parameters(source, {"DEPLOYMENT_TOPOLOGY": "classic", "AGENT_STRATEGY": value})


def test_state_example_matches_public_template_and_security_defaults():
    example = json.loads((ROOT / "samples/customer-poc/ingestion-state.parameters.example.json").read_text())
    parameters = example["parameters"]
    assert parameters["writerPrincipalType"]["value"] == "ServicePrincipal"
    assert parameters["softDeleteRetentionDays"]["value"] == 14
    assert parameters["containerName"]["value"] == "ingestion-state"
    assert parameters["storageAccountName"]["value"] == ""
    assert parameters["ingestionResourceGroupName"]["value"] == ""
