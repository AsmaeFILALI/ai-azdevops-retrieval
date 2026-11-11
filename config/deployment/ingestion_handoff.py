"""Export nonsecret worker bindings from explicit deployment/schema snapshots.

Offline consistency checks do not prove live access, non-serving status or
publication approval. This command never contacts or modifies Azure.
"""

from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
import logging
from pathlib import Path
import re
from typing import Any
from uuid import UUID

from config.search.markdown_index import render_index, validate_endpoint, validate_platform_index

LOGGER = logging.getLogger(__name__)


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object.")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{label} must be an explicit nonempty string.")
    return value


def _guid(value: Any, label: str) -> str:
    text = _text(value, label)
    if str(UUID(text)) != text.lower() or UUID(text).int == 0:
        raise ValueError(f"{label} must be a nonzero UUID.")
    return text.lower()


def _version(value: Any) -> str:
    text = _text(value, "API version")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:-preview)?", text):
        raise ValueError("API version must be date-based, optionally suffixed -preview.")
    date.fromisoformat(text.removesuffix("-preview"))
    return text


def _value(values: dict[str, Any], key: str) -> Any:
    return _object(values.get(key), key).get("value")


def _deployment(snapshot: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    properties = _object(_object(snapshot, "deployment").get("properties"), "deployment properties")
    if properties.get("provisioningState") != "Succeeded":
        raise ValueError("A successful full ARM deployment snapshot is required.")
    return _object(properties.get("outputs"), "outputs"), _object(properties.get("parameters"), "parameters")


def build_handoff(
    platform: dict[str, Any],
    state: dict[str, Any],
    schema_bytes: bytes,
    *,
    index_name: str,
    schema_sha256: str,
    serving_status: str,
    search_schema_api_version: str,
) -> dict[str, Any]:
    """Validate identities and the full pinned schema, then return an allowlist."""
    digest = hashlib.sha256(schema_bytes).hexdigest()
    if not re.fullmatch(r"[a-fA-F0-9]{64}", schema_sha256) or digest != schema_sha256.lower():
        raise ValueError("The schema SHA-256 differs from the independently supplied owner pin.")
    outputs, parameters = _deployment(platform)
    state_outputs, state_parameters = _deployment(state)
    subscription = _guid(_value(outputs, "SUBSCRIPTION_ID"), "subscription")
    tenant = _guid(_value(outputs, "TENANT_ID"), "tenant")
    environment = _text(_value(outputs, "ENVIRONMENT_NAME"), "environment")
    if _value(state_parameters, "environmentName") != environment:
        raise ValueError("Main and state deployments must identify the same environment.")
    if (
        _value(outputs, "NETWORK_ISOLATION") is not True
        or _value(outputs, "RETRIEVAL_BACKEND") != "foundry_iq"
        or _value(outputs, "FOUNDRY_IQ_PATTERN") != "searchIndex"
    ):
        raise ValueError("This handoff requires the private Foundry IQ searchIndex profile.")
    settings = _value(parameters, "additionalAppConfigurationSettings")
    if not isinstance(settings, list) or not any(
        isinstance(item, dict) and item.get("name") == "SEARCH_RAG_SCHEMA"
        and item.get("value") == "ado_markdown_v1" for item in settings
    ):
        raise ValueError("The deployment must explicitly select the Markdown schema.")
    if serving_status not in {"serving", "non-serving"}:
        raise ValueError("An owner-declared serving or non-serving target designation is required.")
    bound_index = _value(parameters, "foundryIqSearchIndexName")
    if serving_status == "serving" and bound_index != index_name:
        raise ValueError("The declared serving index differs from the main deployment binding.")
    if serving_status == "non-serving" and bound_index == index_name:
        raise ValueError("The declared non-serving index is referenced by the main deployment.")
    search_endpoint = validate_endpoint(
        _text(_value(outputs, "KNOWLEDGE_BASE_ENDPOINT"), "Search endpoint"), ".search.windows.net",
    )
    project_id = _text(_value(outputs, "AZURE_AI_PROJECT_RESOURCE_ID"), "Foundry project ID")
    prefix = rf"/subscriptions/{re.escape(subscription)}/resourceGroups/[^/\s]+/providers/"
    project = re.fullmatch(
        prefix + r"Microsoft\.CognitiveServices/accounts/([a-zA-Z0-9-]+)/projects/([^/\s]+)",
        project_id, re.IGNORECASE,
    )
    if project is None:
        raise ValueError("Foundry project ID does not belong to the deployment subscription.")
    account_name, project_name = project.groups()
    expected_project_endpoint = f"https://{account_name}.services.ai.azure.com/api/projects/{project_name}"
    if _text(_value(outputs, "AZURE_AI_PROJECT_ENDPOINT"), "project endpoint").rstrip("/").lower() != expected_project_endpoint.lower():
        raise ValueError("Foundry project endpoint and account ID differ.")
    embedding_endpoint = f"https://{account_name.lower()}.openai.azure.com"
    deployments = _value(parameters, "modelDeploymentList")
    if not isinstance(deployments, list):
        raise ValueError("Model deployment metadata is required.")
    embeddings = [
        item for item in deployments if isinstance(item, dict)
        and item.get("canonical_name") == "EMBEDDING_DEPLOYMENT_NAME"
    ]
    if len(embeddings) != 1:
        raise ValueError("Exactly one explicit embedding deployment is required.")
    embedding = embeddings[0]
    model = _object(embedding.get("model"), "embedding model")
    if model.get("name") != "text-embedding-3-large":
        raise ValueError("The embedding model must match the pinned Markdown contract.")
    deployment = _text(embedding.get("name"), "embedding deployment")
    api_version = _version(embedding.get("apiVersion"))
    desired = render_index(index_name, embedding_endpoint, deployment)
    schema = _object(json.loads(schema_bytes), "platform schema")
    validate_platform_index(schema, desired)

    store = _object(_value(state_outputs, "ingestionState"), "ingestionState")
    account = _text(store.get("storageAccountName"), "state account")
    if not re.fullmatch(r"[a-z0-9]{3,24}", account):
        raise ValueError("Invalid state account name.")
    account_id = _text(store.get("storageAccountResourceId"), "state account ID")
    if not re.fullmatch(prefix + rf"Microsoft\.Storage/storageAccounts/{account}", account_id, re.IGNORECASE):
        raise ValueError("State account ID/name/subscription differ.")
    container = _text(store.get("containerName"), "state container")
    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{1,61})[a-z0-9]", container) or "--" in container:
        raise ValueError("Invalid private container name.")
    container_id = f"{account_id}/blobServices/default/containers/{container}"
    if str(store.get("containerResourceId", "")).lower() != container_id.lower():
        raise ValueError("State container ID/name/account differ.")
    state_url = validate_endpoint(_text(store.get("blobEndpoint"), "Blob endpoint"), ".blob.core.windows.net")
    if state_url != f"https://{account}.blob.core.windows.net":
        raise ValueError("State account endpoint and ARM identity differ.")
    writer = _guid(store.get("writerPrincipalId"), "state writer principal")
    writer_type = store.get("writerPrincipalType")
    if writer_type not in {"User", "Group", "ServicePrincipal"}:
        raise ValueError("Explicit state writer principal type is required.")

    return {
        "schema_version": 1,
        "environment": environment,
        "tenant_id": tenant,
        "subscription_id": subscription,
        "serving_status": serving_status,
        "live_access_verified": False,
        "publication_authorized": False,
        "publishing": {
            "search_endpoint": search_endpoint,
            "index_name": index_name,
            "search_schema_api_version": _version(search_schema_api_version),
            "embedding_endpoint": embedding_endpoint,
            "openai_api_version": api_version,
            "state_account_url": state_url,
            "state_container": container,
            "schema_sha256": digest,
        },
        "embedding": {"deployment": deployment, "model": model["name"], "dimensions": 3072},
        "resources": {
            "openai_resource_id": project_id.rsplit("/projects/", 1)[0],
            "state_container_resource_id": container_id,
            "state_writer_principal_id": writer,
            "state_writer_principal_type": writer_type,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ("platform-deployment", "state-deployment", "platform-schema", "output"):
        parser.add_argument("--" + argument, type=Path, required=True)
    parser.add_argument("--schema-sha256", required=True)
    parser.add_argument("--index-name", required=True)
    parser.add_argument("--serving-status", choices=("serving", "non-serving"), required=True)
    parser.add_argument("--search-schema-api-version", required=True)
    args = parser.parse_args(argv)
    try:
        sources = (args.platform_deployment, args.state_deployment, args.platform_schema)
        if args.output.resolve() in {path.resolve() for path in sources}:
            raise ValueError("Handoff output must not overwrite an input.")
        result = build_handoff(
            json.loads(args.platform_deployment.read_text(encoding="utf-8-sig")),
            json.loads(args.state_deployment.read_text(encoding="utf-8-sig")),
            args.platform_schema.read_bytes(),
            index_name=args.index_name, schema_sha256=args.schema_sha256,
            serving_status=args.serving_status, search_schema_api_version=args.search_schema_api_version,
        )
        with args.output.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(result, indent=2) + "\n")
        LOGGER.info("Nonsecret handoff exported; live access and publication approval remain unverified.")
        return 0
    except json.JSONDecodeError:
        LOGGER.error("Cannot export ingestion handoff: an input is not valid JSON.")
        return 1
    except ValueError as error:
        LOGGER.error("Cannot export ingestion handoff: %s", error)
        return 1
    except (OSError, KeyError, TypeError) as error:
        LOGGER.error("Cannot export ingestion handoff (%s). Check paths, input shape and output availability.", type(error).__name__)
        return 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    raise SystemExit(main())
