"""Execute the documented state-file generator without Azure credentials."""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
SUBSCRIPTION = "11111111-1111-4111-8111-111111111111"
TENANT = "22222222-2222-4222-8222-222222222222"
WRITER = "33333333-3333-4333-8333-333333333333"
NETWORK_GROUP = "rg-customer-network"
VNET = (
    f"/subscriptions/{SUBSCRIPTION}/resourceGroups/{NETWORK_GROUP}"
    "/providers/Microsoft.Network/virtualNetworks/vnet-customer"
)
ZONE = (
    f"/subscriptions/{SUBSCRIPTION}/resourceGroups/{NETWORK_GROUP}"
    "/providers/Microsoft.Network/privateDnsZones/privatelink.blob.core.windows.net"
)


@pytest.fixture
def payload():
    return {
        "azdExitCode": 0,
        "failCommand": "",
        "environment": {
            "AZURE_ENV_NAME": "customer-test",
            "AZURE_SUBSCRIPTION_ID": SUBSCRIPTION,
            "AZURE_TENANT_ID": TENANT,
            "AZURE_NETWORK_RESOURCE_GROUP": NETWORK_GROUP,
            "VNET_RESOURCE_ID": VNET,
            "INGESTION_STATE_WRITER_PRINCIPAL_ID": WRITER,
            "AZURE_PRINCIPAL_ID": "44444444-4444-4444-8444-444444444444",
            "DEPLOYMENT_MODE": "standalone",
            "NETWORK_ISOLATION": "true",
            "USE_EXISTING_VNET": "false",
            "SIDE_BY_SIDE": "true",
            "AZURE_LOCATION": "canadacentral",
            "UNRELATED_SECRET": "must-not-be-exported",
        },
        "account": {"id": SUBSCRIPTION, "tenantId": TENANT},
        "vnet": {
            "id": VNET, "location": "canadaeast", "provisioningState": "Succeeded",
            "subnets": [
                {"name": "pe-subnet", "id": VNET + "/subnets/pe-subnet", "provisioningState": "Succeeded"},
                {"name": "other", "id": VNET + "/subnets/other", "provisioningState": "Succeeded"},
            ],
        },
        "zone": {"id": ZONE},
        "links": [{"virtualNetwork": {"id": VNET}, "provisioningState": "Succeeded"}],
        "writer": {"id": WRITER},
    }


def run_generator(tmp_path, payload):
    pwsh = shutil.which("pwsh")
    if not pwsh:
        pytest.skip("Documented PowerShell commands require PowerShell 7.")
    guide = (ROOT / "docs/customer/azure-devops-markdown-poc.md").read_text(encoding="utf-8")
    blocks = re.findall(r"^```powershell\n(.*?)^```", guide, re.MULTILINE | re.DOTALL)
    snippet = next(block for block in blocks if "# Generate ingestion-state parameters" in block)
    sample = tmp_path / "samples/customer-poc/ingestion-state.parameters.example.json"
    sample.parent.mkdir(parents=True)
    shutil.copyfile(ROOT / "samples/customer-poc/ingestion-state.parameters.example.json", sample)
    fixture = tmp_path / "fixture.json"
    fixture.write_text(json.dumps(payload), encoding="utf-8")
    driver = tmp_path / "generate.ps1"
    driver.write_text(
        r"""
$ErrorActionPreference = 'Stop'
$global:fixture = Get-Content -Raw $env:STATE_FIXTURE | ConvertFrom-Json -AsHashtable
function azd {
    if (($args -join ' ') -ne 'env get-values --output json') { throw 'Unexpected azd command' }
    $global:LASTEXITCODE = $global:fixture.azdExitCode
    return ConvertTo-Json -InputObject $global:fixture.environment -Depth 20
}
function az {
    $arguments = @($args)
    if ($arguments[0] -eq 'account' -and $arguments[1] -eq 'show') {
        $kind = 'account'
    } elseif ($arguments[0..2] -join ' ' -eq 'network vnet show') {
        $kind = 'vnet'
        if ($arguments[$arguments.IndexOf('--ids') + 1] -ne $global:fixture.environment.VNET_RESOURCE_ID) {
            throw 'VNet lookup used a different target'
        }
    } elseif ($arguments[0..3] -join ' ' -eq 'network private-dns zone show') {
        $kind = 'zone'
    } elseif ($arguments[0..4] -join ' ' -eq 'network private-dns link vnet list') {
        $kind = 'links'
    } elseif ($arguments[0..2] -join ' ' -eq 'ad sp show') {
        $kind = 'writer'
        if ($arguments[$arguments.IndexOf('--id') + 1] -ne $global:fixture.environment.INGESTION_STATE_WRITER_PRINCIPAL_ID) {
            throw 'Writer lookup did not use the explicitly approved object ID'
        }
    } else {
        throw 'Unexpected Azure command; only read-only lookups are allowed'
    }
    if ($kind -in @('vnet', 'zone', 'links')) {
        if ($arguments[$arguments.IndexOf('--subscription') + 1] -ne $global:fixture.environment.AZURE_SUBSCRIPTION_ID) {
            throw 'Azure lookup was not scoped to the selected subscription'
        }
    }
    if ($kind -in @('zone', 'links')) {
        if ($arguments[$arguments.IndexOf('--resource-group') + 1] -ne $global:fixture.environment.AZURE_NETWORK_RESOURCE_GROUP) {
            throw 'DNS lookup used a different resource group'
        }
        $nameOption = if ($kind -eq 'zone') { '--name' } else { '--zone-name' }
        if ($arguments[$arguments.IndexOf($nameOption) + 1] -ne 'privatelink.blob.core.windows.net') {
            throw 'DNS lookup used a different zone'
        }
    }
    if ($kind -eq $global:fixture.failCommand) {
        $global:LASTEXITCODE = 7
        return
    }
    $global:LASTEXITCODE = 0
    return ConvertTo-Json -InputObject $global:fixture[$kind] -Depth 20
}
""" + snippet,
        encoding="utf-8",
    )
    return subprocess.run(
        [pwsh, "-NoProfile", "-NonInteractive", "-File", str(driver)],
        cwd=tmp_path, env={**os.environ, "STATE_FIXTURE": str(fixture)},
        capture_output=True, text=True, timeout=30,
    )


@pytest.mark.parametrize("custom_names", [False, True])
def test_documented_commands_generate_exact_allowlisted_parameters(tmp_path, payload, custom_names):
    if custom_names:
        payload["environment"].update(
            INGESTION_STATE_RESOURCE_GROUP_NAME="rg-approved-state",
            INGESTION_STATE_STORAGE_ACCOUNT_NAME="approvedstate123",
        )
    result = run_generator(tmp_path, payload)
    assert result.returncode == 0, result.stdout + result.stderr
    output = tmp_path / ".local/state.parameters.json"
    raw = output.read_text(encoding="utf-8")
    actual = json.loads(raw)
    expected = json.loads(
        (ROOT / "samples/customer-poc/ingestion-state.parameters.example.json").read_text(encoding="utf-8")
    )
    parameters = expected["parameters"]
    for key, value in {
        "environmentName": "customer-test", "location": "canadaeast",
        "privateEndpointSubnetResourceId": VNET + "/subnets/pe-subnet",
        "blobPrivateDnsZoneResourceId": ZONE,
        "writerPrincipalId": WRITER, "writerPrincipalType": "ServicePrincipal",
        "ingestionResourceGroupName": "rg-approved-state" if custom_names else "",
        "storageAccountName": "approvedstate123" if custom_names else "",
    }.items():
        parameters[key]["value"] = value
    assert actual == expected
    assert not output.read_bytes().startswith(b"\xef\xbb\xbf")
    assert "must-not-be-exported" not in raw + result.stdout + result.stderr
    assert payload["environment"]["AZURE_PRINCIPAL_ID"] not in raw
    assert not re.search(r"<[^>]+>", raw)


@pytest.mark.parametrize("failure,message", [
    ("missing-writer", "Missing INGESTION_STATE_WRITER_PRINCIPAL_ID"),
    ("missing-vnet", "Missing VNET_RESOURCE_ID"),
    ("invalid-writer", "object GUID"),
    ("wrong-context", "different subscriptions or tenants"),
    ("wrong-tenant", "different subscriptions or tenants"),
    ("wrong-vnet-scope", "outside this customer network destination"),
    ("wrong-vnet", "VNet is not ready"),
    ("missing-subnet", "Expected one ready pe-subnet"),
    ("duplicate-subnet", "Expected one ready pe-subnet"),
    ("wrong-zone", "zone does not match"),
    ("unlinked-zone", "not linked"),
    ("wrong-zone-link", "not linked"),
    ("wrong-writer", "approved service-principal object ID"),
    ("unsupported-profile", "supplied standalone private customer profile"),
    ("azd-error", "Cannot load"),
    ("invalid-environment", "expected an object"),
    ("azure-error", "Azure lookup failed"),
])
def test_documented_commands_fail_before_writing_for_unsafe_inputs(tmp_path, payload, failure, message):
    if failure == "missing-writer":
        del payload["environment"]["INGESTION_STATE_WRITER_PRINCIPAL_ID"]
    elif failure == "missing-vnet":
        del payload["environment"]["VNET_RESOURCE_ID"]
    elif failure == "invalid-writer":
        payload["environment"]["INGESTION_STATE_WRITER_PRINCIPAL_ID"] = "not-an-object-id"
    elif failure == "wrong-context":
        payload["account"]["id"] = TENANT
    elif failure == "wrong-tenant":
        payload["account"]["tenantId"] = SUBSCRIPTION
    elif failure == "wrong-vnet-scope":
        payload["environment"]["VNET_RESOURCE_ID"] = VNET.replace(NETWORK_GROUP, "rg-unrelated")
    elif failure == "wrong-vnet":
        payload["vnet"]["id"] = VNET + "-other"
    elif failure == "missing-subnet":
        payload["vnet"]["subnets"] = []
    elif failure == "duplicate-subnet":
        payload["vnet"]["subnets"].append(payload["vnet"]["subnets"][0].copy())
    elif failure == "wrong-zone":
        payload["zone"]["id"] = ZONE.replace(NETWORK_GROUP, "rg-unrelated")
    elif failure == "unlinked-zone":
        payload["links"] = []
    elif failure == "wrong-zone-link":
        payload["links"][0]["virtualNetwork"]["id"] = VNET + "-unrelated"
    elif failure == "wrong-writer":
        payload["writer"]["id"] = payload["environment"]["AZURE_PRINCIPAL_ID"]
    elif failure == "unsupported-profile":
        payload["environment"]["USE_EXISTING_VNET"] = "true"
    elif failure == "azd-error":
        payload["azdExitCode"] = 1
    elif failure == "invalid-environment":
        payload["environment"] = []
    elif failure == "azure-error":
        payload["failCommand"] = "zone"
    result = run_generator(tmp_path, payload)
    assert result.returncode != 0
    assert message in result.stderr, result.stdout + result.stderr
    assert not (tmp_path / ".local/state.parameters.json").exists()
    assert "must-not-be-exported" not in result.stdout + result.stderr


def test_documented_commands_never_overwrite_an_existing_state_file(tmp_path, payload):
    path = tmp_path / ".local/state.parameters.json"
    path.parent.mkdir()
    path.write_text("existing-reviewed-parameters", encoding="utf-8")
    result = run_generator(tmp_path, payload)
    assert result.returncode != 0
    assert path.read_text(encoding="utf-8") == "existing-reviewed-parameters"
