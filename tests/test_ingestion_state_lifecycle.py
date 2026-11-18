"""Integrated state provisioning and post-provision grants use mocked Azure."""

import json
import os
from pathlib import Path
import shutil
import subprocess
from unittest.mock import patch

import pytest

from config.appdefinition.roles import resolve_scope
from config.deployment import ingestion_state
from config.deployment.context import ingestion_state_bindings

ROOT = Path(__file__).resolve().parents[1]
SUB = "11111111-1111-4111-8111-111111111111"
WRITER = "22222222-2222-4222-8222-222222222222"
CLIENT = "33333333-3333-4333-8333-333333333333"
RG = "rg-customer-test"
ACCOUNT = f"/subscriptions/{SUB}/resourceGroups/{RG}/providers/Microsoft.Storage/storageAccounts/stingtest"
CONTAINER = ACCOUNT + "/blobServices/default/containers/ingestion-state"
ENDPOINT = "https://stingtest.blob.core.windows.net/"
ENV = {
    "DEPLOY_INGESTION_STATE_STORE": "true", "NETWORK_ISOLATION": "true",
    "AZURE_ENV_NAME": "customer-test", "AZURE_SUBSCRIPTION_ID": SUB,
    "AZURE_RESOURCE_GROUP": RG, "INGESTION_STATE_WRITER_PRINCIPAL_ID": WRITER,
}


class StateAz:
    def __init__(self):
        self.calls = []
        self.assigned = False
        self.principal = {"id": WRITER}
        self.bindings = {
            "environmentName": "customer-test", "resourceGroupName": RG,
            "storageAccountName": "stingtest", "storageAccountResourceId": ACCOUNT,
            "blobEndpoint": ENDPOINT, "containerName": "ingestion-state",
            "containerResourceId": CONTAINER, "writerPrincipalId": WRITER,
            "writerPrincipalType": "ServicePrincipal",
            "privateEndpointResourceId": (
                f"/subscriptions/{SUB}/resourceGroups/{RG}/providers/Microsoft.Network/privateEndpoints/pep-stingtest"
            ),
        }
        self.deployment = {"properties": {
            "provisioningState": "Succeeded",
            "outputs": {"ingestionState": {"value": self.bindings}},
        }}
        self.account = {
            "id": ACCOUNT, "publicNetworkAccess": "Disabled", "allowSharedKeyAccess": False,
            "allowBlobPublicAccess": False, "primaryEndpoints": {"blob": ENDPOINT},
        }
        self.container = {"id": CONTAINER, "properties": {"publicAccess": "None"}}

    def __call__(self, arguments, *, required=True):
        self.calls.append(arguments)
        if arguments[:3] == ["deployment", "group", "show"]:
            assert arguments[arguments.index("--name") + 1] == "ingestionControlState"
            assert arguments[arguments.index("--resource-group") + 1] == RG
            return json.dumps(self.deployment)
        if arguments[:3] == ["ad", "sp", "show"]:
            return json.dumps(self.principal)
        if arguments[:3] == ["storage", "account", "show"]:
            return json.dumps(self.account)
        if arguments[:2] == ["resource", "show"]:
            return json.dumps(self.container)
        if arguments[:3] == ["role", "assignment", "list"]:
            return json.dumps([{"id": "existing"}] if self.assigned else [])
        if arguments[:3] == ["role", "assignment", "create"]:
            self.assigned = True
            return ""
        raise AssertionError(f"Unexpected Azure call: {arguments}")

    def writes(self):
        return [call for call in self.calls if "create" in call]


def test_disabled_feature_has_no_azure_calls():
    az = StateAz()
    assert ingestion_state.validate_inputs({}) is None
    assert not ingestion_state.assign_writer_role({}, run_az=az)
    assert ingestion_state_bindings({}, az) == {}
    assert az.calls == []


@pytest.mark.parametrize("override", [
    {"DEPLOY_INGESTION_STATE_STORE": "typo"},
    {"INGESTION_STATE_WRITER_PRINCIPAL_ID": ""},
    {"INGESTION_STATE_WRITER_PRINCIPAL_ID": "not-an-object-id"},
    {"INGESTION_STATE_WRITER_PRINCIPAL_ID": WRITER + " "},
    {"INGESTION_STATE_WRITER_PRINCIPAL_ID": "00000000-0000-0000-0000-000000000000"},
    {"NETWORK_ISOLATION": "false"},
    {"INGESTION_STATE_STORAGE_ACCOUNT_NAME": "INVALID"},
    {"INGESTION_STATE_STORAGE_ACCOUNT_NAME": "stingtest "},
    {"INGESTION_STATE_CONTAINER_NAME": "bad--container"},
    {"INGESTION_STATE_CONTAINER_NAME": "Uppercase"},
    {"INGESTION_STATE_CONTAINER_NAME": "ingestion-state "},
    {"INGESTION_STATE_SOFT_DELETE_RETENTION_DAYS": "0"},
    {"INGESTION_STATE_SOFT_DELETE_RETENTION_DAYS": "366"},
    {"INGESTION_STATE_SOFT_DELETE_RETENTION_DAYS": "not-a-number"},
    {"INGESTION_STATE_RESOURCE_GROUP_NAME": "rg-old-ingestion"},
])
def test_invalid_inputs_fail_before_azure_calls(override):
    az = StateAz()
    with pytest.raises(ValueError):
        ingestion_state.assign_writer_role({**ENV, **override}, run_az=az)
    assert az.calls == []


def test_exact_container_writer_grant_is_subscription_bound_and_idempotent():
    az = StateAz()
    assert ingestion_state.assign_writer_role(ENV, run_az=az)
    assert not ingestion_state.assign_writer_role(ENV, run_az=az)
    assert len(az.writes()) == 1
    grant = az.writes()[0]
    assert grant[grant.index("--scope") + 1] == CONTAINER
    assert grant[grant.index("--assignee-object-id") + 1] == WRITER
    assert grant[grant.index("--assignee-principal-type") + 1] == "ServicePrincipal"
    assert grant[grant.index("--role") + 1] == "ba92f5b4-2d11-453d-a403-e96b0029c9fe"
    for call in az.calls:
        if call[:2] != ["ad", "sp"]:
            assert call[call.index("--subscription") + 1] == SUB
    assert not any(term in " ".join(grant).lower() for term in ("search", "openai", "listkeys"))


@pytest.mark.parametrize("case", [
    "failed-deployment", "missing-output", "invalid-deployment", "foreign-environment",
    "foreign-account", "foreign-container", "foreign-endpoint", "missing-account", "wrong-writer", "wrong-writer-type", "client-id", "public-account",
    "shared-key", "anonymous", "wrong-endpoint", "wrong-container", "public-container",
])
def test_invalid_live_bindings_never_grant_roles(case):
    az = StateAz()
    environment = dict(ENV)
    if case == "failed-deployment":
        az.deployment["properties"]["provisioningState"] = "Failed"
    elif case == "missing-output":
        az.deployment["properties"]["outputs"] = {}
    elif case == "invalid-deployment":
        az.deployment = []
    elif case == "foreign-environment":
        az.bindings["environmentName"] = "other"
    elif case == "foreign-account":
        az.bindings["storageAccountResourceId"] = ACCOUNT.replace(RG, "foreign")
    elif case == "foreign-container":
        az.bindings["containerResourceId"] = CONTAINER.replace(SUB, CLIENT)
    elif case == "foreign-endpoint":
        az.bindings["privateEndpointResourceId"] = az.bindings["privateEndpointResourceId"].replace(RG, "foreign")
    elif case == "missing-account":
        del az.bindings["storageAccountResourceId"]
    elif case == "wrong-writer":
        az.bindings["writerPrincipalId"] = CLIENT
    elif case == "wrong-writer-type":
        az.bindings["writerPrincipalType"] = "User"
    elif case == "client-id":
        environment["INGESTION_STATE_WRITER_PRINCIPAL_ID"] = CLIENT
        az.bindings["writerPrincipalId"] = CLIENT
    elif case == "public-account":
        az.account["publicNetworkAccess"] = "Enabled"
    elif case == "shared-key":
        az.account["allowSharedKeyAccess"] = True
    elif case == "anonymous":
        az.account["allowBlobPublicAccess"] = True
    elif case == "wrong-endpoint":
        az.account["primaryEndpoints"]["blob"] = "https://other.blob.core.windows.net/"
    elif case == "wrong-container":
        az.container["id"] = CONTAINER + "-other"
    else:
        az.container["properties"]["publicAccess"] = "Blob"
    with pytest.raises(ValueError):
        ingestion_state.assign_writer_role(environment, run_az=az)
    assert not az.writes()


def test_cli_validation_checks_the_sp_object_id_without_role_writes():
    az = StateAz()
    with patch.dict(os.environ, ENV, clear=True), patch("config.deployment.appconfig._run_az", az):
        assert ingestion_state.main(["--validate"]) == 0
    assert [call[:3] for call in az.calls] == [["ad", "sp", "show"]]
    assert not az.writes()


def test_cli_surfaces_azure_read_errors_without_role_writes(caplog):
    with patch.dict(os.environ, ENV, clear=True), patch(
        "config.deployment.appconfig._run_az", side_effect=RuntimeError("AuthorizationFailed"),
    ):
        assert ingestion_state.main([]) == 1
    assert "AuthorizationFailed" in caplog.text


def test_application_storage_roles_exclude_the_exact_control_state_account():
    az = StateAz()
    app_id = ACCOUNT.replace("stingtest", "stapplication")

    def read(arguments, **kwargs):
        if arguments[:3] == ["storage", "account", "list"]:
            return json.dumps([
                {"id": ACCOUNT, "name": "stingtest"},
                {"id": app_id, "name": "stapplication"},
            ])
        return az(arguments, **kwargs)

    assert resolve_scope("storageAccount", ENV, RG, read) == app_id
    with pytest.raises(RuntimeError, match="found 0"):
        resolve_scope("storageAccount", {**ENV, "STORAGE_ACCOUNT_NAME": "stingtest"}, RG, read)
    assert not az.writes()


@pytest.mark.parametrize("failure", ["", "resolution", "foreign"])
def test_powershell_configuration_uses_the_state_aware_document_resolver(tmp_path, failure):
    shell = shutil.which("pwsh")
    if not shell:
        pytest.skip("PowerShell 7 is unavailable.")
    text = (ROOT / "scripts" / "postProvision.ps1").read_text(encoding="utf-8")
    start = text.index("    $documentStorageId =")
    end = text.index("    $foundryStorageName =", start)
    snippet = text[start:end]
    script = tmp_path / "resolve-storage.ps1"
    app_id = ACCOUNT.replace("stingtest", "stapplication")
    script.write_text(
        "$ErrorActionPreference='Stop'\n"
        f"$subscriptionId='{SUB}'; $foundryResourceGroup='{RG}'\n"
        "function python {\n"
        "  if ($args[0] -ne '-c' -or $args[1] -notmatch 'resolve_scope' "
        "-or $args[1] -notmatch 'storageAccount') { throw 'Wrong resolver' }\n"
        f"  $global:LASTEXITCODE={1 if failure == 'resolution' else 0}\n"
        f"  return '{app_id.replace(RG, 'foreign') if failure == 'foreign' else app_id}'\n"
        "}\n" + snippet +
        "\nif ($storageName -ne 'stapplication') { throw 'Selected the wrong account' }\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [shell, "-NoProfile", "-NonInteractive", "-File", str(script)],
        capture_output=True, text=True, timeout=30,
    )
    assert (result.returncode == 0) == (not failure), result.stdout + result.stderr


@pytest.mark.parametrize("platform", ["ps1", "sh"])
@pytest.mark.parametrize("exit_code", [0, 7])
def test_post_hooks_run_state_reconciliation_and_propagate_failure(tmp_path, platform, exit_code):
    text = (ROOT / "scripts" / f"postProvision.{platform}").read_text(encoding="utf-8")
    start = text.index(
        'Write-Host "Assigning the ingestion' if platform == "ps1"
        else 'echo "Assigning the ingestion'
    )
    end = text.index(
        'Write-Host "🔐 Assigning capability' if platform == "ps1"
        else 'echo "🔐 Assigning capability', start,
    )
    snippet = text[start:end]
    if platform == "ps1":
        shell = shutil.which("pwsh")
        if not shell:
            pytest.skip("PowerShell 7 is unavailable.")
        script = tmp_path / "state-hook.ps1"
        script.write_text(
            "$ErrorActionPreference='Continue'\n"
            "function Invoke-PythonModule { param($ModuleName) "
            "Write-Host \"MODULE=$ModuleName\"; $global:LASTEXITCODE=[int]$env:TEST_STATE_EXIT }\n"
            + snippet, encoding="utf-8",
        )
        command = [shell, "-NoProfile", "-NonInteractive", "-File", str(script)]
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=30,
            env={**os.environ, "TEST_STATE_EXIT": str(exit_code)},
        )
    else:
        git_bash = Path(r"C:\Program Files\Git\bin\bash.exe")
        shell = str(git_bash) if os.name == "nt" and git_bash.exists() else shutil.which("bash")
        if not shell:
            pytest.skip("Bash is unavailable.")
        result = subprocess.run(
            [shell, "-s"], input=(
                f"PROJECT_ROOT=.\npython() {{ echo \"MODULE=$*\"; return {exit_code}; }}\n" + snippet
            ), capture_output=True, text=True, timeout=30,
        )
    assert (result.returncode == 0) == (exit_code == 0), result.stdout + result.stderr
    assert "config.deployment.ingestion_state" in result.stdout


def test_pre_hooks_validate_state_before_resource_group_writes():
    for platform in ("ps1", "sh"):
        text = (ROOT / "scripts" / f"preProvision.{platform}").read_text(encoding="utf-8")
        state = text.index("config.deployment.ingestion_state")
        assert "--validate" in text[state:state + 130]
        assert state < text.index("config.deployment.resource_groups")


def test_customer_runbook_has_no_separate_state_deployment():
    guide = (ROOT / "docs" / "customer" / "azure-devops-markdown-poc.md").read_text(encoding="utf-8")
    assert "az deployment sub create --" not in guide
    assert ".local/state.parameters.json" not in guide
    for term in (
        "Service connections", "Workload identity federation", "Issuer", "Subject identifier",
        "az ad sp show --id $workerClientId --query id", "service-principal object ID",
        "DEPLOY_INGESTION_STATE_STORE", "container scope only", "--name ingestionControlState",
    ):
        assert term in guide
