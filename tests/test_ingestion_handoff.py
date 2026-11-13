"""Offline handoff binds customer snapshots, not our existing environment."""

import copy
import hashlib
import json

import pytest

from config.deployment.ingestion_handoff import build_handoff, main
from config.search.markdown_index import render_index

SUB = "11111111-1111-4111-8111-111111111111"
TENANT = "22222222-2222-4222-8222-222222222222"
PREFIX = f"/subscriptions/{SUB}/resourceGroups/customer"
SEARCH = "https://customer-search.search.windows.net"
OPENAI = "https://customer-model.openai.azure.com"


@pytest.fixture
def inputs():
    def values(items):
        return {key: {"value": value} for key, value in items.items()}

    platform = {"properties": {
        "provisioningState": "Succeeded",
        "outputs": values({
            "TENANT_ID": TENANT, "SUBSCRIPTION_ID": SUB,
            "ENVIRONMENT_NAME": "customer", "NETWORK_ISOLATION": True,
            "RETRIEVAL_BACKEND": "foundry_iq", "FOUNDRY_IQ_PATTERN": "searchIndex",
            "KNOWLEDGE_BASE_ENDPOINT": SEARCH,
            "AZURE_AI_PROJECT_RESOURCE_ID": PREFIX + "/providers/Microsoft.CognitiveServices/accounts/customer-model/projects/app",
            "AZURE_AI_PROJECT_ENDPOINT": "https://customer-model.services.ai.azure.com/api/projects/app",
        }),
        "parameters": values({
            "foundryIqSearchIndexName": "customer-index",
            "additionalAppConfigurationSettings": [{"name": "SEARCH_RAG_SCHEMA", "value": "ado_markdown_v1"}],
            "modelDeploymentList": [{
                "name": "text-embedding", "canonical_name": "EMBEDDING_DEPLOYMENT_NAME",
                "model": {"name": "text-embedding-3-large", "version": "1"},
                "apiVersion": "2025-01-01-preview",
            }],
        }),
    }}
    account = PREFIX + "/providers/Microsoft.Storage/storageAccounts/customerstate"
    state = {"properties": {
        "provisioningState": "Succeeded",
        "parameters": values({"environmentName": "customer", "writerPrincipalType": "ServicePrincipal"}),
        "outputs": values({"ingestionState": {
            "storageAccountName": "customerstate", "storageAccountResourceId": account,
            "blobEndpoint": "https://customerstate.blob.core.windows.net/",
            "containerName": "ingestion-state",
            "containerResourceId": account + "/blobServices/default/containers/ingestion-state",
            "writerPrincipalId": "33333333-3333-4333-8333-333333333333",
            "writerPrincipalType": "ServicePrincipal",
        }}),
    }}
    schema = (json.dumps(render_index("customer-index", OPENAI, "text-embedding"), indent=2) + "\n").encode()
    return platform, state, schema


def build(inputs, **overrides):
    platform, state, schema = inputs
    arguments = dict(
        index_name="customer-index", schema_sha256=hashlib.sha256(schema).hexdigest(),
        serving_status="serving", search_schema_api_version="2025-05-01-preview",
    )
    arguments.update(overrides)
    return build_handoff(platform, state, schema, **arguments)


def test_customer_bindings_and_api_version_are_derived_from_exact_snapshots(inputs):
    result = build(inputs)
    config = result["publishing"]
    assert config["search_endpoint"] == SEARCH
    assert config["embedding_endpoint"] == OPENAI
    assert config["openai_api_version"] == "2025-01-01-preview"
    assert config["state_account_url"] == "https://customerstate.blob.core.windows.net"
    assert result["embedding"] == {"deployment": "text-embedding", "model": "text-embedding-3-large", "dimensions": 3072}
    assert result["tenant_id"] == TENANT
    assert result["live_access_verified"] is False
    assert result["publication_authorized"] is False
    assert result["serving_status"] == "serving"


def test_secret_bearing_extra_snapshot_fields_are_not_exported(inputs):
    inputs[0]["properties"]["outputs"]["password"] = {"value": "never-export-this"}
    inputs[1]["properties"]["outputs"]["ingestionState"]["value"]["accountKey"] = "never-export-this"
    assert "never-export-this" not in json.dumps(build(inputs))


@pytest.mark.parametrize("case", [
    "failed", "foreign-subscription", "wrong-blob-host", "wrong-container",
    "wrong-model", "wrong-project-host", "wrong-environment", "missing-api",
    "wrong-binding", "wrong-schema-endpoint", "missing-principal",
])
def test_conflicting_or_missing_bindings_fail_closed(inputs, case):
    platform, state, schema = copy.deepcopy(inputs)
    output = platform["properties"]["outputs"]
    state_values = state["properties"]["outputs"]["ingestionState"]["value"]
    if case == "failed":
        state["properties"]["provisioningState"] = "Failed"
    elif case == "foreign-subscription":
        state_values["storageAccountResourceId"] = state_values["storageAccountResourceId"].replace(SUB, TENANT)
    elif case == "wrong-blob-host":
        state_values["blobEndpoint"] = "https://otherstate.blob.core.windows.net"
    elif case == "wrong-container":
        state_values["containerName"] = "different"
    elif case == "wrong-model":
        platform["properties"]["parameters"]["modelDeploymentList"]["value"][0]["model"]["name"] = "text-embedding-ada-002"
    elif case == "wrong-project-host":
        output["AZURE_AI_PROJECT_ENDPOINT"]["value"] = "https://other.services.ai.azure.com/api/projects/app"
    elif case == "wrong-environment":
        state["properties"]["parameters"]["environmentName"]["value"] = "another"
    elif case == "missing-api":
        del platform["properties"]["parameters"]["modelDeploymentList"]["value"][0]["apiVersion"]
    elif case == "wrong-binding":
        platform["properties"]["parameters"]["foundryIqSearchIndexName"]["value"] = "other"
    elif case == "wrong-schema-endpoint":
        schema = json.dumps(render_index("customer-index", "https://other.openai.azure.com", "text-embedding")).encode()
    else:
        del state_values["writerPrincipalId"]
    with pytest.raises(ValueError):
        build((platform, state, schema))


@pytest.mark.parametrize("version", ["latest", "2025-99-99", "2025-01-01?sig=secret"])
def test_api_versions_are_real_date_based_values(inputs, version):
    with pytest.raises(ValueError):
        build(inputs, search_schema_api_version=version)


def test_owner_hash_is_required_and_exact(inputs):
    with pytest.raises(ValueError, match="SHA-256"):
        build(inputs, schema_sha256="a" * 64)


def test_nonserving_target_is_explicit_not_inferred_from_its_name(inputs):
    inputs[0]["properties"]["parameters"]["foundryIqSearchIndexName"]["value"] = "another-serving-index"
    assert build(inputs, serving_status="non-serving")["serving_status"] == "non-serving"


def test_nonserving_declaration_cannot_contradict_recorded_main_binding(inputs):
    with pytest.raises(ValueError, match="referenced"):
        build(inputs, serving_status="non-serving")


def test_cli_never_overwrites_inputs_or_existing_output(inputs, tmp_path):
    platform, state, schema = inputs
    first, second, third = [tmp_path / name for name in ("main.json", "state.json", "schema.json")]
    first.write_text(json.dumps(platform))
    second.write_text(json.dumps(state))
    third.write_bytes(schema)
    args = [
        "--platform-deployment", str(first), "--state-deployment", str(second),
        "--platform-schema", str(third), "--schema-sha256", hashlib.sha256(schema).hexdigest(),
        "--index-name", "customer-index", "--serving-status", "serving",
        "--search-schema-api-version", "2025-05-01-preview", "--output",
    ]
    assert main(args + [str(first)]) == 1
    output = tmp_path / "handoff.json"
    assert main(args + [str(output)]) == 0
    assert main(args + [str(output)]) == 1
    assert json.loads(first.read_text()) == platform
