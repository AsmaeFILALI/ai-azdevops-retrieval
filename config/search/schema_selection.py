"""Validate the platform's explicit, setup-only RAG schema selection."""

import logging
import os
from typing import Any, Mapping

SCHEMA_SETTING = "SEARCH_RAG_SCHEMA"
STANDARD_SCHEMA = "standard"
MARKDOWN_SCHEMA = "ado_markdown_v1"


def _text(environment: Mapping[str, Any], name: str, default: str = "") -> str:
    value = environment.get(name)
    if value is not None and not isinstance(value, str):
        raise ValueError(f"{name} must be a string.")
    return (value or "").strip() or default


def public_settings(environment: Mapping[str, Any]) -> dict[str, str]:
    schema = _text(environment, SCHEMA_SETTING, STANDARD_SCHEMA)
    if schema not in (STANDARD_SCHEMA, MARKDOWN_SCHEMA):
        raise ValueError(f"{SCHEMA_SETTING} must be '{STANDARD_SCHEMA}' or '{MARKDOWN_SCHEMA}'.")
    index_name = _text(environment, "SEARCH_RAG_INDEX_NAME")
    if schema == MARKDOWN_SCHEMA:
        if not index_name:
            raise ValueError(f"SEARCH_RAG_INDEX_NAME is required for {SCHEMA_SETTING}={MARKDOWN_SCHEMA}.")
        backend = _text(environment, "RETRIEVAL_BACKEND", "foundry_iq")
        pattern = _text(environment, "FOUNDRY_IQ_PATTERN", "azureBlob")
        kind = _text(environment, "FOUNDRY_IQ_KNOWLEDGE_SOURCE_KIND", pattern)
        if backend != "ai_search" and not (
            backend == "foundry_iq" and pattern == "searchIndex" and kind == "searchIndex"
        ):
            raise ValueError(f"{SCHEMA_SETTING}={MARKDOWN_SCHEMA} requires ai_search or Foundry IQ searchIndex retrieval.")
        legacy_name = _text(environment, "FOUNDRY_IQ_SEARCH_INDEX_NAME")
        if legacy_name and legacy_name != index_name:
            raise ValueError("FOUNDRY_IQ_SEARCH_INDEX_NAME must match SEARCH_RAG_INDEX_NAME for the Markdown schema.")
    return {
        SCHEMA_SETTING: schema,
        **({"SEARCH_RAG_INDEX_NAME": index_name} if index_name else {}),
    }


def main() -> int:
    try:
        public_settings(os.environ)
    except ValueError as error:
        logging.error("Invalid Search schema selection: %s", error)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
