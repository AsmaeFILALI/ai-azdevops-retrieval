"""Validate integrated ingestion state and reconcile its exact worker grant."""

from __future__ import annotations

import argparse
import logging
import os
import re
from typing import Mapping
from uuid import UUID

from config.appdefinition.roles import RunAz, _ensure_rbac, _json, load_role_guids
from config.deployment.context import bound_resource_id, ingestion_state_bindings
from config.deployment.resource_groups import resource_group_for

LOGGER = logging.getLogger(__name__)
ENABLED = "DEPLOY_INGESTION_STATE_STORE"
WRITER = "INGESTION_STATE_WRITER_PRINCIPAL_ID"


def validate_inputs(environment: Mapping[str, str]) -> str | None:
    """Return the approved writer UUID, or None when this feature is disabled."""
    enabled = (environment.get(ENABLED) or "false").strip().lower()
    if enabled not in {"true", "false"}:
        raise ValueError(f"{ENABLED} must be 'true' or 'false'.")
    if enabled == "false":
        return None
    if (environment.get("NETWORK_ISOLATION") or "").strip().lower() != "true":
        raise ValueError("Ingestion control state requires NETWORK_ISOLATION=true.")
    writer = environment.get(WRITER) or ""
    try:
        parsed = UUID(writer)
    except ValueError as error:
        raise ValueError(f"{WRITER} must be an approved service-principal object UUID.") from error
    if parsed.int == 0 or str(parsed) != writer.lower():
        raise ValueError(f"{WRITER} must be a nonzero canonical service-principal object UUID.")
    account = environment.get("INGESTION_STATE_STORAGE_ACCOUNT_NAME") or ""
    if account and not re.fullmatch(r"[a-z0-9]{3,24}", account):
        raise ValueError("INGESTION_STATE_STORAGE_ACCOUNT_NAME must contain 3-24 lowercase letters/digits.")
    container = environment.get("INGESTION_STATE_CONTAINER_NAME") or "ingestion-state"
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,61}[a-z0-9]", container) or "--" in container:
        raise ValueError("INGESTION_STATE_CONTAINER_NAME must be a valid private Blob container name.")
    retention = environment.get("INGESTION_STATE_SOFT_DELETE_RETENTION_DAYS") or "14"
    if not re.fullmatch(r"\d+", retention) or not 1 <= int(retention) <= 365:
        raise ValueError("INGESTION_STATE_SOFT_DELETE_RETENTION_DAYS must be between 1 and 365.")
    legacy_group = (environment.get("INGESTION_STATE_RESOURCE_GROUP_NAME") or "").strip()
    if legacy_group and legacy_group.lower() != resource_group_for(environment, "application").lower():
        raise ValueError(
            "Integrated ingestion state must use AZURE_RESOURCE_GROUP. Review migration of the "
            "legacy separate state store; it is never moved or deleted automatically."
        )
    return str(parsed)


def _verify_writer(writer: str, run_az: RunAz) -> None:
    principal = _json(run_az, ["ad", "sp", "show", "--id", writer, "--query", "{id:id}"])
    if not isinstance(principal, dict) or str(principal.get("id", "")).lower() != writer:
        raise ValueError(
            f"{WRITER} must be the service-principal object ID, not its application/client ID "
            "or the Azure DevOps service-connection ID."
        )


def assign_writer_role(environment: Mapping[str, str], *, run_az: RunAz | None = None) -> bool:
    """Verify all bindings before creating a container-scoped data role."""
    writer = validate_inputs(environment)
    if writer is None:
        LOGGER.info("Integrated ingestion control-state storage is disabled.")
        return False
    if run_az is None:
        from config.deployment.appconfig import _run_az as run_az
    bindings = ingestion_state_bindings(environment, run_az)
    if bindings.get("writerPrincipalId", "").lower() != writer or bindings.get("writerPrincipalType") != "ServicePrincipal":
        raise ValueError("The deployed state writer differs from the approved object ID. Rerun azd provision.")
    account_id = bindings.get("storageAccountResourceId", "")
    container_id = bindings.get("containerResourceId", "")
    account = bound_resource_id(
        account_id, environment, "Microsoft.Storage/storageAccounts", area="application",
    )
    bound_resource_id(
        container_id, environment, "Microsoft.Storage/storageAccounts/blobServices/containers",
        area="application",
    )
    name = bindings.get("storageAccountName", "")
    preferred_name = (environment.get("INGESTION_STATE_STORAGE_ACCOUNT_NAME") or "").strip()
    container = (environment.get("INGESTION_STATE_CONTAINER_NAME") or "ingestion-state").strip()
    expected_container = f"{account_id}/blobServices/default/containers/{container}"
    if (
        account.name.lower() != name.lower()
        or (preferred_name and preferred_name != name)
        or bindings.get("containerName") != container
        or container_id.lower() != expected_container.lower()
    ):
        raise ValueError("Ingestion state account/container outputs conflict. Rerun azd provision.")
    endpoint = bindings.get("blobEndpoint", "").rstrip("/")
    if endpoint != f"https://{name}.blob.core.windows.net":
        raise ValueError("Ingestion state Blob endpoint does not match the provisioned account.")
    _verify_writer(writer, run_az)
    actual = _json(run_az, [
        "storage", "account", "show", "--ids", account_id, "--subscription", account.subscription,
    ])
    if (
        not isinstance(actual, dict)
        or str(actual.get("id", "")).lower() != account_id.lower()
        or actual.get("publicNetworkAccess") != "Disabled"
        or actual.get("allowSharedKeyAccess") is not False
        or actual.get("allowBlobPublicAccess") is not False
        or str((actual.get("primaryEndpoints") or {}).get("blob", "")).rstrip("/") != endpoint
    ):
        raise ValueError("Ingestion state account identity, private access or Entra-only settings differ.")
    actual_container = _json(run_az, [
        "resource", "show", "--ids", container_id, "--api-version", "2025-01-01",
        "--subscription", account.subscription,
    ])
    if (
        not isinstance(actual_container, dict)
        or str(actual_container.get("id", "")).lower() != container_id.lower()
        or (actual_container.get("properties") or {}).get("publicAccess") not in {None, "None"}
    ):
        raise ValueError("Ingestion state container identity or private access differs.")
    created = _ensure_rbac(
        writer, load_role_guids()["StorageBlobDataContributor"], container_id, run_az,
        subscription=account.subscription,
    )
    LOGGER.info("Ingestion state container writer role %s.", "assigned" if created else "already assigned")
    return created


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validate", action="store_true", help="Validate inputs and the writer without role writes.")
    args = parser.parse_args(argv)
    try:
        if args.validate:
            writer = validate_inputs(os.environ)
            if writer is not None:
                from config.deployment.appconfig import _run_az

                _verify_writer(writer, _run_az)
                LOGGER.info("Integrated ingestion state inputs and writer object ID validated.")
        else:
            assign_writer_role(os.environ)
        return 0
    except (ValueError, RuntimeError) as error:
        LOGGER.error("Ingestion control-state configuration failed: %s", error)
        return 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    raise SystemExit(main())
