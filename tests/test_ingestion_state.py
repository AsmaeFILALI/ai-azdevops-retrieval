"""Compiled contracts for the standalone ingestion control-state deployment."""

import json
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


def resources(template):
    collection = template["resources"]
    return list(collection.values()) if isinstance(collection, dict) else collection


@pytest.fixture(scope="module")
def compiled(tmp_path_factory):
    destination = tmp_path_factory.mktemp("state-template") / "ingestion-state.json"
    subprocess.run(
        [
            shutil.which("az"), "bicep", "build",
            "--file", str(ROOT / "infra" / "ingestion-state.bicep"),
            "--outfile", str(destination), "--only-show-errors",
        ],
        check=True, capture_output=True, text=True,
    )
    return json.loads(destination.read_text(encoding="utf-8-sig"))


@pytest.fixture(scope="module")
def state(compiled):
    deployment = next(item for item in resources(compiled) if item["type"] == "Microsoft.Resources/deployments")
    return deployment["properties"]["template"]


def test_target_is_separate_incremental_resource_group(compiled):
    assert "subscriptionDeploymentTemplate" in compiled["$schema"]
    assert {item["type"] for item in resources(compiled)} == {
        "Microsoft.Resources/resourceGroups", "Microsoft.Resources/deployments",
    }
    assert compiled["parameters"]["storageAccountName"]["defaultValue"] == ""
    assert compiled["parameters"]["ingestionResourceGroupName"]["defaultValue"] == ""
    assert compiled["parameters"]["writerPrincipalType"]["defaultValue"] == "ServicePrincipal"
    assert compiled["parameters"]["containerName"]["defaultValue"] == "ingestion-state"
    assert "defaultValue" not in compiled["parameters"]["writerPrincipalId"]
    deployment = next(item for item in resources(compiled) if item["type"] == "Microsoft.Resources/deployments")
    assert deployment["properties"]["mode"] == "Incremental"
    group = next(item for item in resources(compiled) if item["type"] == "Microsoft.Resources/resourceGroups")
    assert deployment["resourceGroup"] == group["name"]


def test_account_is_private_entra_only_lrs_hot(state):
    account = next(item for item in resources(state) if item.get("name") == "ingestionStateAccount")
    parameters = {key: item["value"] for key, item in account["properties"]["parameters"].items()}
    assert parameters["skuName"] == "Standard_LRS"
    assert parameters["kind"] == "StorageV2"
    assert parameters["accessTier"] == "Hot"
    for key in ("allowBlobPublicAccess", "allowSharedKeyAccess", "allowCrossTenantReplication", "enableHierarchicalNamespace"):
        assert parameters[key] is False
    assert parameters["defaultToOAuthAuthentication"] is True
    assert parameters["supportsHttpsTrafficOnly"] is True
    assert parameters["minimumTlsVersion"] == "TLS1_2"
    assert parameters["publicNetworkAccess"] == "Disabled"
    assert parameters["networkAcls"] == {
        "defaultAction": "Deny", "bypass": "None", "ipRules": [], "virtualNetworkRules": [],
    }


def test_versioning_soft_delete_and_private_empty_container(state):
    account = next(item for item in resources(state) if item.get("name") == "ingestionStateAccount")
    service = account["properties"]["parameters"]["blobServices"]["value"]
    assert state["parameters"]["softDeleteRetentionDays"]["defaultValue"] == 14
    assert service["isVersioningEnabled"] is True
    for prefix in ("deleteRetentionPolicy", "containerDeleteRetentionPolicy"):
        assert service[prefix + "Enabled"] is True
        assert service[prefix + "Days"] == "[parameters('softDeleteRetentionDays')]"
    assert service["containers"] == [{"name": "[parameters('containerName')]", "publicAccess": "None"}]
    assert "managementPolicyRules" not in account["properties"]["parameters"]
    assert "roleAssignments" not in account["properties"]["parameters"]
    assert "secretsExportConfiguration" not in account["properties"]["parameters"]


def test_only_explicit_container_writer_role_is_requested(state):
    role = next(item for item in resources(state) if item.get("name") == "ingestionStateWriter")
    assignments = role["properties"]["parameters"]["roleAssignments"]["value"]
    assert len(assignments) == 1
    assignment = assignments[0]
    assert assignment["principalId"] == "[parameters('writerPrincipalId')]"
    assert assignment["principalType"] == "[parameters('writerPrincipalType')]"
    assert assignment["resourceId"] == state["outputs"]["containerResourceId"]["value"]
    assert "/blobServices/default/containers/" in assignment["resourceId"]
    assert "StorageBlobDataContributor.guid" in state["variables"]["writerRoleDefinitionId"]
    role_constants = json.loads((ROOT / "infra" / "constants" / "roles.json").read_text())
    assert role_constants["StorageBlobDataContributor"]["guid"] == "ba92f5b4-2d11-453d-a403-e96b0029c9fe"
    helper = role["properties"]["template"]
    nested = resources(helper)[0]["properties"]["template"]
    grant = resources(nested)[0]
    assert grant["type"] == "Microsoft.Authorization/roleAssignments"
    assert grant["scope"] == "[if(empty(parameters('roleAssignments')[copyIndex()].resourceId), '', parameters('roleAssignments')[copyIndex()].resourceId)]"
    assert "guid(parameters('writerPrincipalId'), variables('writerRoleDefinitionId')" in state["outputs"]["writerRoleAssignmentResourceId"]["value"]


def test_private_endpoint_reuses_subnet_and_dns_without_vnet_mutation(state):
    endpoint = next(item for item in resources(state) if item.get("name") == "ingestionStatePrivateEndpoint")
    parameters = endpoint["properties"]["parameters"]
    assert parameters["subnetResourceId"]["value"] == "[parameters('privateEndpointSubnetResourceId')]"
    assert parameters["privateLinkServiceConnections"]["value"][0]["properties"]["groupIds"] == ["blob"]
    group = json.dumps(parameters["privateDnsZoneGroup"])
    assert "empty(parameters('blobPrivateDnsZoneResourceId'))" in group
    assert "privateDnsZoneResourceId" in group
    assert "parameters('blobPrivateDnsZoneResourceId')" in group
    assert {item["type"] for item in resources(state)} == {"Microsoft.Resources/deployments"}
    assert len(resources(state)) == 3


def test_no_search_indexer_document_ingestion_seeding_or_secrets(compiled):
    def walk(template):
        for item in resources(template):
            if item.get("existing", False):
                continue
            yield item
            properties = item.get("properties", {})
            nested = properties.get("template") if isinstance(properties, dict) else None
            if nested is not None:
                yield from walk(nested)

    kinds = {item["type"] for item in walk(compiled)}
    for forbidden in (
        "Microsoft.Search/searchServices", "Microsoft.Storage/storageAccounts/blobServices/containers/blobs",
        "Microsoft.Resources/deploymentScripts",
        "Microsoft.Network/virtualNetworks", "Microsoft.Network/privateDnsZones",
        "Microsoft.App/containerApps", "Microsoft.KeyVault/vaults",
    ):
        assert forbidden not in kinds
    outputs = compiled["outputs"]["ingestionState"]["value"]
    assert {"blobEndpoint", "containerResourceId", "writerPrincipalId", "privateEndpointResourceId"} <= outputs.keys()
    assert not any(term in json.dumps(outputs).lower() for term in ("listkeys", "connectionstring", "sas"))


@pytest.fixture(scope="module")
def integrated(tmp_path_factory):
    destination = tmp_path_factory.mktemp("integrated-state") / "main.json"
    subprocess.run(
        [shutil.which("az"), "bicep", "build", "--file", str(ROOT / "infra" / "main.bicep"),
         "--outfile", str(destination), "--only-show-errors"],
        check=True, capture_output=True, text=True,
    )
    return json.loads(destination.read_text(encoding="utf-8-sig"))


def test_integrated_store_is_optional_in_the_root_resource_group(integrated):
    assert integrated["parameters"]["deployIngestionStateStore"]["defaultValue"] is False
    module = next(item for item in resources(integrated) if item.get("name") == "ingestionControlState")
    assert module["condition"] == "[parameters('deployIngestionStateStore')]"
    assert "resourceGroup" not in module
    assert len(integrated["outputs"]) == 64
    assert module["properties"]["parameters"]["assignWriterRole"]["value"] is False
    assert module["properties"]["parameters"]["environmentName"]["value"] == "[parameters('environmentName')]"
    assert "privateEndpoints" in " ".join(module["dependsOn"])
    assert "aiFoundry" in " ".join(module["dependsOn"])


def test_integrated_module_defers_writer_grants_and_exports_exact_handoff(integrated):
    module = next(item for item in resources(integrated) if item.get("name") == "ingestionControlState")
    template = module["properties"]["template"]
    role = next(item for item in resources(template) if item.get("name") == "ingestionStateWriter")
    assert role["condition"] == "[parameters('assignWriterRole')]"
    handoff = template["outputs"]["ingestionState"]["value"]
    assert handoff["resourceGroupName"] == "[resourceGroup().name]"
    assert handoff["writerPrincipalType"] == "[parameters('writerPrincipalType')]"
    assert handoff["containerResourceId"] == template["outputs"]["containerResourceId"]["value"]
    parameters = module["properties"]["parameters"]
    assert parameters["softDeleteRetentionDays"]["value"] == "[parameters('ingestionStateSoftDeleteRetentionDays')]"
    subnet = json.dumps(parameters["privateEndpointSubnetResourceId"])
    assert "parameters('peSubnetName')" in subnet
    assert "parameters('existingVnetResourceId')" in subnet
    assert "reference('virtualNetwork').outputs.resourceId.value" in subnet
