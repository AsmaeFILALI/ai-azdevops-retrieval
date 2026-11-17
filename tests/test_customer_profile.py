"""Portable customer inputs must compose without our saved deployment state."""

import json
import hashlib
from pathlib import Path
import subprocess
import sys

import pytest

from config.deployment import appconfig
from config.deployment.composition import compose_parameters

ROOT = Path(__file__).resolve().parents[1]


def test_root_preserves_portable_legacy_seed_inputs():
    root = json.loads((ROOT / "main.parameters.json").read_text(encoding="utf-8"))
    location = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, encoding="utf-8", check=False,
    )
    if location.returncode or Path(location.stdout.strip()).resolve() != ROOT.resolve():
        pytest.skip("Committed seed comparison requires this checkout's Git metadata.")
    seed = json.loads(subprocess.check_output(
        ["git", "-C", str(ROOT), "show", "HEAD:infra/main.parameters.json"],
        text=True, encoding="utf-8",
    ))
    assert root["contentVersion"] == seed["contentVersion"]
    assert all(root["parameters"].get(name) == value for name, value in seed["parameters"].items())
    assert root["parameters"]["dbAccountName"]["value"] == "${COSMOS_ACCOUNT_NAME=}"


def test_seed_contract_survives_normal_preprovision_generation(tmp_path, monkeypatch):
    source = json.loads((ROOT / "main.parameters.json").read_text(encoding="utf-8"))
    profile = json.loads((ROOT / "samples/customer-poc/azd-env.example.json").read_text(encoding="utf-8"))
    checkout = tmp_path / "source"
    (checkout / "infra").mkdir(parents=True)
    for relative in ("main.parameters.json", "infra/main.parameters.json"):
        (checkout / relative).write_text(json.dumps(source), encoding="utf-8")
    for args in (
        ["init", "--quiet"], ["add", "."],
        ["-c", "core.hooksPath=", "-c", "user.name=Offline Test",
         "-c", "user.email=offline@example.invalid", "commit", "--quiet", "-m", "seed fixture"],
    ):
        subprocess.run(["git", "-C", str(checkout), *args], check=True, capture_output=True)
    generated = compose_parameters(source, profile["inputs"] | profile["bootstrap"])
    assert generated != source
    (checkout / "infra/main.parameters.json").write_text(json.dumps(generated), encoding="utf-8")
    monkeypatch.setattr(sys.modules[__name__], "ROOT", checkout)
    test_root_preserves_portable_legacy_seed_inputs()


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


def test_state_profile_is_integrated_and_requires_the_worker_object_id():
    parameters = json.loads((ROOT / "main.parameters.json").read_text())["parameters"]
    profile = json.loads((ROOT / "samples/customer-poc/azd-env.example.json").read_text())["inputs"]
    assert profile["DEPLOY_INGESTION_STATE_STORE"] == "true"
    assert profile["INGESTION_STATE_WRITER_PRINCIPAL_ID"] == "<WORKER_SERVICE_PRINCIPAL_OBJECT_UUID>"
    assert parameters["deployIngestionStateStore"]["value"] == "${DEPLOY_INGESTION_STATE_STORE=false}"
    assert parameters["ingestionStateSoftDeleteRetentionDays"]["value"] == "${INGESTION_STATE_SOFT_DELETE_RETENTION_DAYS=14}"
    assert parameters["ingestionStateContainerName"]["value"] == "${INGESTION_STATE_CONTAINER_NAME=ingestion-state}"
    assert parameters["ingestionStateWriterPrincipalId"]["value"] == "${INGESTION_STATE_WRITER_PRINCIPAL_ID=}"
