"""Markdown schema selection across provisioning, publishers and Search setup."""

from contextlib import ExitStack
from copy import deepcopy
import json
from pathlib import Path
from unittest.mock import Mock, patch

from jinja2 import Environment, FileSystemLoader, StrictUndefined
import pytest

from config.deployment import appconfig, composition
from config.search import markdown_index, schema_selection, setup

ROOT = Path(__file__).resolve().parents[3]
NAME = "kb-sections-ingestion-test-v1"
SELECTION = {
    "DEPLOYMENT_TOPOLOGY": "classic",
    "SEARCH_RAG_SCHEMA": "ado_markdown_v1",
    "SEARCH_RAG_INDEX_NAME": NAME,
    "FOUNDRY_IQ_SEARCH_INDEX_NAME": NAME,
    "RETRIEVAL_BACKEND": "foundry_iq",
    "FOUNDRY_IQ_PATTERN": "searchIndex",
    "FOUNDRY_IQ_KNOWLEDGE_SOURCE_KIND": "searchIndex",
    "FOUNDRY_IQ_KNOWLEDGE_SOURCE_NAME": "azdo-markdown-ks",
    "KNOWLEDGE_BASE_NAME": "azdo-knowledge-base",
}
EMBEDDING = {
    "endpoint": "https://embedding.openai.azure.com",
    "deployment_name": "text-embedding",
    "model_name": "text-embedding-3-large",
}


def rendered():
    environment = Environment(
        loader=FileSystemLoader(ROOT / "config" / "search"), undefined=StrictUndefined,
    )
    settings = json.loads(environment.get_template("search.settings.j2").render(
        **SELECTION, RESOURCE_TOKEN="abc", SEARCH_SERVICE_QUERY_ENDPOINT="https://test.search.windows.net",
    ))
    context = {
        **settings, "SEARCH_SERVICE_QUERY_ENDPOINT": "https://test.search.windows.net",
        "EMBEDDING_MODEL_INFO": EMBEDDING, "GPT_MODEL_INFO": {},
    }
    definitions = json.loads(environment.get_template("search.j2").render(**context))
    return definitions, context


def downstream(stack):
    mocks = {}
    for name in (
        "ensure_native_blob_private_links", "cleanup_knowledge_resources", "provision_datasources",
        "provision_skillsets", "provision_indexers", "filter_work_iq_sources",
        "provision_knowledge_sources", "enforce_private_execution_for_generated_indexers",
        "provision_knowledge_bases",
    ):
        mocks[name] = stack.enter_context(patch.object(setup, name, return_value=True))
    stack.enter_context(patch.object(setup, "ChainedTokenCredential"))
    return mocks


@pytest.mark.parametrize("value", [None, "", " ", "standard"])
def test_default_and_empty_schema_preserve_standard_behavior(value):
    assert schema_selection.public_settings({"SEARCH_RAG_SCHEMA": value}) == {"SEARCH_RAG_SCHEMA": "standard"}


@pytest.mark.parametrize("override", [
    {"SEARCH_RAG_SCHEMA": "typo"}, {"SEARCH_RAG_SCHEMA": True},
    {"SEARCH_RAG_INDEX_NAME": ""}, {"SEARCH_RAG_INDEX_NAME": 42},
    {"FOUNDRY_IQ_SEARCH_INDEX_NAME": "other"},
    {"FOUNDRY_IQ_PATTERN": "azureBlob"},
    {"FOUNDRY_IQ_KNOWLEDGE_SOURCE_KIND": "azureBlob"},
])
def test_invalid_selection_fails_before_deployment_or_app_discovery(override):
    environment = {**SELECTION, **override, "RESOURCE_TOKEN": "test", "AZURE_RESOURCE_GROUP": "rg-test"}
    source = json.loads((ROOT / "main.parameters.json").read_text())
    with patch.object(appconfig, "_container_app") as discover:
        with pytest.raises(ValueError):
            appconfig.build_settings(environment)
        with pytest.raises(ValueError):
            composition.compose_parameters(source, environment)
    discover.assert_not_called()


def test_direct_search_selection_is_supported():
    settings = schema_selection.public_settings({**SELECTION, "RETRIEVAL_BACKEND": "ai_search"})
    assert settings["SEARCH_RAG_SCHEMA"] == "ado_markdown_v1"


def test_composition_and_both_publishers_keep_selector_index_and_label_consistent():
    source = json.loads((ROOT / "main.parameters.json").read_text())
    environment = {**SELECTION, "RESOURCE_TOKEN": "test", "AZURE_RESOURCE_GROUP": "rg-test"}
    composed = composition.compose_parameters(source, environment)
    settings = {
        item["name"]: item for item in composed["parameters"]["additionalAppConfigurationSettings"]["value"]
    }
    with patch.object(appconfig, "_container_app", return_value={"fqdn": "app.example", "principalId": "id"}):
        published = appconfig.build_settings(environment)
    for key in ("SEARCH_RAG_SCHEMA", "SEARCH_RAG_INDEX_NAME"):
        assert settings[key]["value"] == published[key] == SELECTION[key]
        assert settings[key]["label"] == "agent-lz"
    script = (ROOT / "scripts" / "postProvision.ps1").read_text(encoding="utf-8")
    assert "SEARCH_RAG_SCHEMA = (Get-OptionalEnvValue 'SEARCH_RAG_SCHEMA' 'standard').Trim()" in script
    assert script.index("Invoke-PythonModule -ModuleName 'config.search.schema_selection'") < script.index(
        "Set-AgentLzAppConfiguration -Endpoint",
    )
    assert "config.deployment.appconfig" in (ROOT / "scripts" / "postProvision.sh").read_text(encoding="utf-8")
    assert "config.search.setup" in script
    assert "config.search.setup" in (ROOT / "scripts" / "postProvision.sh").read_text(encoding="utf-8")


def test_selected_rendering_binds_same_index_and_exact_pinned_schema():
    definitions, context = rendered()
    desired = markdown_index.render_index(NAME, EMBEDDING["endpoint"], EMBEDDING["deployment_name"])
    assert context["SEARCH_RAG_SCHEMA"] == "ado_markdown_v1"
    assert definitions["indexes"][0] == desired
    source = definitions["knowledgeSources"][0]
    assert source["name"] == "azdo-markdown-ks"
    assert source["searchIndexParameters"]["searchIndexName"] == NAME
    assert source["searchIndexParameters"]["semanticConfigurationName"] == "semantic-config"
    projected = {field["name"] for field in source["searchIndexParameters"]["sourceDataFields"]}
    # Without url/filepath the orchestrator emits no citation link and the model invents one.
    assert {"url", "filepath", "title", "content", "heading_path", "source_path", "source_version_id"} <= projected
    assert definitions["knowledgeBases"][0]["name"] == "azdo-knowledge-base"
    assert definitions["indexers"] == definitions["datasources"] == definitions["skillsets"] == []


def test_postprovision_accepts_the_trailing_slash_in_published_model_endpoints():
    definitions, context = rendered()
    rag = definitions["indexes"][0]
    rag["vectorSearch"]["vectorizers"][0]["azureOpenAIParameters"]["resourceUri"] += "/"
    context["EMBEDDING_MODEL_INFO"] = {**EMBEDDING, "endpoint": EMBEDDING["endpoint"] + "/"}
    with ExitStack() as stack:
        downstream(stack)
        stack.enter_context(patch.object(setup, "get_search_resource", return_value=(deepcopy(rag), '"etag"')))
        stack.enter_context(patch.object(setup, "prepare_index_updates", return_value=[]))
        stack.enter_context(patch.object(setup, "provision_indexes"))
        write = stack.enter_context(patch.object(setup, "call_search_api"))
        setup.execute_setup(definitions, context)
    write.assert_not_called()


def test_standard_schema_projection_is_unchanged():
    environment = Environment(loader=FileSystemLoader(ROOT / "config" / "search"), undefined=StrictUndefined)
    settings = json.loads(environment.get_template("search.settings.j2").render(
        **{**SELECTION, "SEARCH_RAG_SCHEMA": "standard"}, RESOURCE_TOKEN="abc",
        SEARCH_SERVICE_QUERY_ENDPOINT="https://test.search.windows.net",
    ))
    context = {**settings, "EMBEDDING_MODEL_INFO": EMBEDDING, "GPT_MODEL_INFO": {}}
    source = json.loads(environment.get_template("search.j2").render(**context))["knowledgeSources"][0]
    assert [field["name"] for field in source["searchIndexParameters"]["sourceDataFields"]] == [
        "metadata_storage_name", "metadata_storage_path", "filepath", "page", "title", "category", "url",
    ]


@pytest.mark.parametrize("existing", [True, False])
def test_postprovision_creates_or_validates_once_and_never_uses_additive_path_for_markdown(existing):
    definitions, context = rendered()
    live = {index["name"]: deepcopy(index) for index in definitions["indexes"] if existing or index["name"] != NAME}
    writes = []

    def get(_endpoint, _version, resource_type, resource_name, _credential):
        assert resource_type == "indexes"
        return deepcopy(live.get(resource_name)), '"etag"'

    def put(_endpoint, _version, resource_type, resource_name, method, _credential, body, **conditions):
        assert resource_type == "indexes" and method == "put"
        assert resource_name == NAME
        assert conditions["if_none_match"] == "*"
        assert conditions["if_match"] is None
        assert resource_name not in live
        writes.append(resource_name)
        live[resource_name] = deepcopy(body)
        return True

    with ExitStack() as stack:
        downstream(stack)
        stack.enter_context(patch.object(setup, "get_search_resource", side_effect=get))
        stack.enter_context(patch.object(setup, "call_search_api", side_effect=put))
        merge = stack.enter_context(patch.object(setup, "merge_additive_index_schema", wraps=setup.merge_additive_index_schema))
        setup.execute_setup(definitions, context)
        setup.execute_setup(definitions, context)
    assert writes == ([] if existing else [NAME])
    assert all(call.args[1]["name"] != NAME for call in merge.call_args_list)


@pytest.mark.parametrize("failure", ["schema", "semantic", "forbidden", "readback"])
def test_markdown_failures_stop_before_other_index_writes_and_knowledge_cleanup(failure):
    definitions, context = rendered()
    rag = deepcopy(definitions["indexes"][0])
    if failure == "schema":
        rag["fields"] = [field for field in rag["fields"] if field["name"] != "repo_id"]
    if failure == "semantic":
        rag["semantic"]["defaultConfiguration"] = "other"
    created = False

    def get(_endpoint, _version, _type, name, _credential):
        if name != NAME:
            return None, None
        if failure == "forbidden":
            raise RuntimeError("HTTP 403")
        if failure == "readback":
            return ({"name": NAME, "fields": []}, None) if created else (None, None)
        return rag, '"etag"'

    def put(*args, **kwargs):
        nonlocal created
        assert args[3] == NAME
        created = True
        return True

    with ExitStack() as stack:
        services = downstream(stack)
        stack.enter_context(patch.object(setup, "get_search_resource", side_effect=get))
        write = stack.enter_context(patch.object(setup, "call_search_api", side_effect=put))
        with pytest.raises((ValueError, RuntimeError)):
            setup.execute_setup(definitions, context)
    assert write.call_count == (1 if failure == "readback" else 0)
    services["cleanup_knowledge_resources"].assert_not_called()
    services["provision_knowledge_sources"].assert_not_called()


def test_normal_configuration_loader_persists_selector_and_renders_markdown():
    context = {
        **SELECTION, "RESOURCE_TOKEN": "abc", "SEARCH_SERVICE_QUERY_ENDPOINT": "https://test.search.windows.net",
        "MODEL_DEPLOYMENTS": json.dumps([{
            "canonical_name": "EMBEDDING_DEPLOYMENT_NAME", "name": "text-embedding",
            "model": {"name": EMBEDDING["model_name"], "format": "OpenAI"},
            "endpoint": EMBEDDING["endpoint"],
        }]),
    }
    client = Mock()
    client.list_configuration_settings.return_value = [Mock(key=key, value=value) for key, value in context.items()]
    with patch.dict(setup.os.environ, {"APP_CONFIG_ENDPOINT": "https://test.azconfig.io"}), patch.object(
        setup, "AzureAppConfigurationClient", return_value=client,
    ), patch.object(setup, "ChainedTokenCredential"):
        definitions, loaded = setup.prepare_context_and_render("search.j2", str(ROOT / "config" / "search"))
    markdown_index.validate_platform_index(
        definitions["indexes"][0],
        markdown_index.render_index(NAME, EMBEDDING["endpoint"], "text-embedding"),
    )
    assert loaded["SEARCH_RAG_SCHEMA"] == "ado_markdown_v1"
    published = {call.args[0].key: call.args[0] for call in client.set_configuration_setting.call_args_list}
    assert published["SEARCH_RAG_SCHEMA"].value == "ado_markdown_v1"
    assert published["SEARCH_RAG_SCHEMA"].label == "agent-lz"


def test_invalid_published_selector_stops_before_configuration_writes():
    client = Mock()
    client.list_configuration_settings.return_value = [Mock(key="SEARCH_RAG_SCHEMA", value="unsupported")]
    with patch.dict(setup.os.environ, {"APP_CONFIG_ENDPOINT": "https://test.azconfig.io"}), patch.object(
        setup, "AzureAppConfigurationClient", return_value=client,
    ), patch.object(setup, "ChainedTokenCredential"):
        with pytest.raises(ValueError, match="SEARCH_RAG_SCHEMA"):
            setup.prepare_context_and_render("search.j2", str(ROOT / "config" / "search"))
    client.set_configuration_setting.assert_not_called()


@pytest.mark.parametrize("selection,expected", [("ado_markdown_v1", 0), ("unsupported", 1)])
def test_standalone_selector_preflight_reports_invalid_values(selection, expected, monkeypatch):
    for key, value in SELECTION.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("SEARCH_RAG_SCHEMA", selection)
    assert schema_selection.main() == expected
