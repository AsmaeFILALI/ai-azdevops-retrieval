"""Render and conditionally create one platform-owned Markdown index."""

import argparse
import hashlib
import json
import logging
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlsplit

from azure.core.exceptions import AzureError
from azure.identity import AzureCliCredential, ChainedTokenCredential, ManagedIdentityCredential
from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateError
import requests

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "contracts" / "ado-markdown-index-consumer-v1.json"
LOGGER = logging.getLogger(__name__)


def load_contract() -> dict[str, Any]:
    raw = CONTRACT_PATH.read_bytes()
    expected_hash = CONTRACT_PATH.with_suffix(".json.sha256").read_text(encoding="ascii").split()[0]
    if hashlib.sha256(raw).hexdigest() != expected_hash:
        raise ValueError("Pinned Markdown consumer contract hash does not match; review the contract.")
    return json.loads(raw)


def validate_endpoint(endpoint: str, suffix: str) -> str:
    parsed = urlsplit(endpoint)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or not parsed.hostname.endswith(suffix)
        or parsed.username or parsed.password or parsed.port
        or parsed.path not in ("", "/") or parsed.query or parsed.fragment
    ):
        raise ValueError(f"Expected an HTTPS Azure endpoint ending in {suffix}, without path or credentials.")
    return endpoint.rstrip("/")


def render_index(
    index_name: str,
    embedding_endpoint: str,
    embedding_deployment: str,
) -> dict[str, Any]:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,126}[a-z0-9]", index_name) or "--" in index_name:
        raise ValueError("Index name must be 2-128 lowercase letters/digits/hyphens, with no adjacent hyphens.")
    endpoint = validate_endpoint(embedding_endpoint, ".openai.azure.com")
    if not embedding_deployment.strip():
        raise ValueError("An explicit embedding deployment name is required.")
    contract = load_contract()
    embedding = contract["embeddingRequirements"]
    environment = Environment(
        loader=FileSystemLoader(Path(__file__).parent),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )
    index = json.loads(environment.get_template("rag-index.j2").render(
        MARKDOWN_INDEX=True,
        SEARCH_RAG_INDEX_NAME=index_name,
        SEARCH_ANALYZER_NAME="standard.lucene",
        EMBEDDINGS_VECTOR_DIMENSIONS=embedding["dimensions"],
        EMBEDDING_MODEL_INFO={
            "endpoint": endpoint,
            "deployment_name": embedding_deployment,
            "model_name": embedding["model"],
        },
    ))
    validate_contract(index, contract)
    return index


def named_items(items: list[dict[str, Any]], label: str) -> dict[str, dict[str, Any]]:
    result = {item["name"]: item for item in items}
    if len(result) != len(items):
        raise ValueError(f"Duplicate names in {label}.")
    return result


def field_property(field: dict[str, Any], key: str) -> Any:
    if key == "key":
        return field.get(key) or False
    return field.get(key)


def validate_fields(
    actual: dict[str, Any],
    expected_fields: list[dict[str, Any]],
    *,
    check_key: bool = True,
) -> None:
    fields = named_items(actual["fields"], "index fields")
    for expected in expected_fields:
        current = fields.get(expected["name"])
        if current is None:
            raise ValueError(f"Missing index field: {expected['name']}.")
        for key, value in expected.items():
            if key == "fields":
                validate_fields(current, value, check_key=False)
            elif field_property(current, key) != value:
                raise ValueError(f"Index field {expected['name']}.{key} does not match the pinned definition.")
    if check_key and [field["name"] for field in actual["fields"] if field.get("key")] != ["id"]:
        raise ValueError("Only id may be the index key.")


def validate_contract(index: dict[str, Any], contract: dict[str, Any]) -> None:
    validate_fields(index, contract["requiredFields"])
    fields = named_items(index["fields"], "index fields")
    vector = contract["vectorRequirements"]
    vector_search = index.get("vectorSearch", {})
    profiles = named_items(vector_search.get("profiles", []), "vector profiles")
    profile = profiles.get(vector["profile"], {})
    algorithms = named_items(vector_search.get("algorithms", []), "vector algorithms")
    algorithm = algorithms.get(profile.get("algorithm"), {})
    if algorithm.get("kind") != vector["algorithmKind"] or algorithm.get("hnswParameters", {}).get("metric") != vector["metric"]:
        raise ValueError("Expected the pinned HNSW/cosine vector algorithm.")
    vectorizers = named_items(vector_search.get("vectorizers", []), "vectorizers")
    vectorizer = vectorizers.get(profile.get("vectorizer"), {})
    if vectorizer.get("kind") != vector["queryVectorizerKind"]:
        raise ValueError("The required Azure OpenAI query vectorizer is missing.")
    parameters = vectorizer.get("azureOpenAIParameters", {})
    if parameters.get("modelName") != contract["embeddingRequirements"]["model"]:
        raise ValueError("Query vectorizer model does not match ingestion.")
    if not parameters.get("deploymentId"):
        raise ValueError("Query vectorizer deployment is required.")
    validate_endpoint(parameters.get("resourceUri", ""), ".openai.azure.com")
    if parameters.get("apiKey") or parameters.get("authIdentity"):
        raise ValueError("Query vectorizer must use the Search system identity, without API keys or an identity override.")

    semantic = contract["semanticRequirements"]
    if index.get("semantic", {}).get("defaultConfiguration") != semantic["defaultConfiguration"]:
        raise ValueError("Default semantic configuration does not match the contract.")
    configurations = named_items(index.get("semantic", {}).get("configurations", []), "semantic configurations")
    priorities = configurations.get(semantic["name"], {}).get("prioritizedFields", {})
    expected = {
        "titleField": {"fieldName": semantic["titleField"]},
        "prioritizedContentFields": [{"fieldName": name} for name in semantic["contentFields"]],
        "prioritizedKeywordsFields": [{"fieldName": name} for name in semantic["keywordFields"]],
    }
    if priorities != expected:
        raise ValueError("Semantic title/content/keyword priorities do not match the contract.")
    for name in [semantic["titleField"], *semantic["contentFields"], *semantic["keywordFields"]]:
        if not fields.get(name, {}).get("searchable") or not fields[name].get("retrievable"):
            raise ValueError(f"Semantic field {name} must be searchable and retrievable.")


def validate_platform_index(actual: dict[str, Any], desired: dict[str, Any]) -> None:
    """Compare explicit platform properties, allowing unrelated service defaults."""
    validate_contract(actual, load_contract())
    if actual.get("name") != desired["name"]:
        raise ValueError("Read-back index name differs from the explicit target.")
    validate_fields(actual, desired["fields"])
    for key in ("permissionFilterOption", "corsOptions"):
        if actual.get(key) != desired.get(key):
            raise ValueError(f"Index {key} differs from the pinned platform definition.")
    expected_vector = desired["vectorSearch"]
    actual_vector = actual["vectorSearch"]
    for collection in ("profiles", "algorithms", "vectorizers"):
        current = named_items(actual_vector.get(collection, []), collection)
        for item in expected_vector[collection]:
            candidate = current.get(item["name"], {})
            for key, expected_value in item.items():
                actual_value = candidate.get(key)
                if key == "azureOpenAIParameters":
                    expected_value = {
                        prop: value.rstrip("/") if prop == "resourceUri" else value
                        for prop, value in expected_value.items()
                    }
                    actual_value = {
                        prop: value.rstrip("/") if prop == "resourceUri" else value
                        for prop, value in (actual_value or {}).items() if prop in expected_value
                    }
                if actual_value != expected_value:
                    raise ValueError(f"Index {collection}/{item['name']}.{key} differs from the platform definition.")


def ensure_index(
    endpoint: str,
    api_version: str,
    desired: dict[str, Any],
    credential: ChainedTokenCredential,
    *,
    apply: bool = False,
) -> str:
    from config.search import setup

    endpoint = validate_endpoint(endpoint, ".search.windows.net")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:-preview)?", api_version):
        raise ValueError("Search API version must be date-based, optionally suffixed -preview.")
    validate_platform_index(desired, desired)
    name = desired["name"]
    existing, _ = setup.get_search_resource(endpoint, api_version, "indexes", name, credential)
    if existing is not None:
        validate_platform_index(existing, desired)
        LOGGER.info("Index '%s' already matches; no write performed.", name)
        return "validated-existing"
    if not apply:
        LOGGER.info("Plan: create only index '%s'; no Azure changes performed.", name)
        return "create-planned"
    # Reuse the same conditional PUT path as post-provisioning, never its cleanup flow.
    updates = [(name, desired, [field["name"] for field in desired["fields"]], None, "*")]
    setup.provision_indexes({"indexes": [desired]}, {}, credential, endpoint, api_version, updates)
    actual, _ = setup.get_search_resource(endpoint, api_version, "indexes", name, credential)
    if actual is None:
        raise RuntimeError(f"Index '{name}' was not found after creation; rerun validation, not deletion.")
    validate_platform_index(actual, desired)
    LOGGER.info("Index '%s' created and read-back validated.", name)
    return "created-and-validated"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--search-endpoint", required=True)
    parser.add_argument("--index-name", required=True)
    parser.add_argument("--embedding-endpoint", required=True)
    parser.add_argument("--embedding-deployment", required=True)
    parser.add_argument("--api-version", default="2025-05-01-preview")
    parser.add_argument("--schema-output", required=True, type=Path)
    parser.add_argument("--apply", action="store_true", help="Create if missing; never update or delete an existing index.")
    args = parser.parse_args(argv)
    try:
        desired = render_index(args.index_name, args.embedding_endpoint, args.embedding_deployment)
        validate_endpoint(args.search_endpoint, ".search.windows.net")
        schema_bytes = (json.dumps(desired, indent=2, ensure_ascii=True) + "\n").encode("utf-8")
        args.schema_output.write_bytes(schema_bytes)
        schema_hash = hashlib.sha256(schema_bytes).hexdigest()
        args.schema_output.with_suffix(args.schema_output.suffix + ".sha256").write_text(
            f"{schema_hash}  {args.schema_output.name}\n", encoding="ascii",
        )
        LOGGER.info("Rendered schema %s; SHA256 %s", args.schema_output, schema_hash)
        with ChainedTokenCredential(AzureCliCredential(process_timeout=60), ManagedIdentityCredential()) as credential:
            outcome = ensure_index(args.search_endpoint, args.api_version, desired, credential, apply=args.apply)
        LOGGER.info("Index-only deployment result: %s", outcome)
        return 0
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, TemplateError, AzureError, requests.RequestException) as error:
        LOGGER.error("Markdown index deployment failed: %s", error)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
