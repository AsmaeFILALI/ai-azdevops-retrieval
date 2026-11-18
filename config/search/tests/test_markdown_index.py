"""Contract, schema-rendering and create-only Search deployment regressions."""

from copy import deepcopy
import hashlib
import json
from unittest.mock import Mock, patch

from jinja2 import Environment, FileSystemLoader, StrictUndefined
import pytest

from config.search import markdown_index as deploy
from config.search import setup


ENDPOINT = "https://test.search.windows.net"
EMBEDDING = "https://embedding.openai.azure.com"
NAME = "kb-sections-ingestion-test-v1"


@pytest.fixture
def desired():
    return deploy.render_index(NAME, EMBEDDING, "text-embedding")


def test_pinned_requirements_are_not_a_deployable_schema():
    contract = deploy.load_contract()
    assert contract["artifactKind"] == "consumer-contract-not-deployable-index"
    assert contract["contractVersion"] == "1.0.0-draft"
    assert len(contract["requiredFields"]) == 23


def test_all_consumer_and_platform_fields_validate(desired):
    deploy.validate_platform_index(desired, desired)
    assert len(desired["fields"]) == 46
    fields = {field["name"]: field for field in desired["fields"]}
    assert fields["parent_id"]["filterable"] is True
    assert fields["contentVector"]["dimensions"] == 3072
    assert fields["contentVector"]["vectorSearchProfile"] == "default"
    assert fields["heading_path"]["analyzer"] == "standard.lucene"
    assert "apiKey" not in desired["vectorSearch"]["vectorizers"][0]["azureOpenAIParameters"]
    priorities = desired["semantic"]["configurations"][0]["prioritizedFields"]
    assert priorities["titleField"] == {"fieldName": "title"}
    assert priorities["prioritizedContentFields"] == [{"fieldName": "content"}]
    assert priorities["prioritizedKeywordsFields"] == [
        {"fieldName": "heading_path"}, {"fieldName": "category"},
    ]


def test_default_postprovision_and_markdown_share_template_without_default_changes(desired):
    env = Environment(loader=FileSystemLoader(deploy.ROOT / "config" / "search"), undefined=StrictUndefined)
    settings = json.loads(env.get_template("search.settings.j2").render(
        RESOURCE_TOKEN="abc", SEARCH_SERVICE_QUERY_ENDPOINT=ENDPOINT,
        RETRIEVAL_BACKEND="foundry_iq", FOUNDRY_IQ_PATTERN="searchIndex",
        SEARCH_RAG_INDEX_NAME=NAME,
    ))
    context = {
        **settings,
        "EMBEDDING_MODEL_INFO": {
            "endpoint": EMBEDDING, "deployment_name": "text-embedding",
            "model_name": "text-embedding-3-large",
        },
        "GPT_MODEL_INFO": {},
    }
    ordinary = json.loads(env.get_template("search.j2").render(**context))
    default_fields = {field["name"]: field for field in ordinary["indexes"][0]["fields"]}
    assert "filterable" not in default_fields["parent_id"]
    assert "repo_id" not in default_fields
    assert len(default_fields) == 36
    assert "titleField" not in ordinary["indexes"][0]["semantic"]["configurations"][0]["prioritizedFields"]
    markdown = json.loads(env.get_template("search.j2").render(**context, MARKDOWN_INDEX=True))
    assert markdown["indexes"][0] == desired
    assert markdown["indexes"][1:] == ordinary["indexes"][1:]
    assert markdown["knowledgeSources"] == ordinary["knowledgeSources"]
    assert markdown["knowledgeBases"] == ordinary["knowledgeBases"]


def test_service_null_nonkey_and_extra_defaults_are_normalized(desired):
    actual = deepcopy(desired)
    for field in actual["fields"]:
        if field["name"] != "id":
            field["key"] = None
    actual["semantic"]["configurations"][0]["rankingOrder"] = "BoostedRerankerScore"
    actual["vectorSearch"]["vectorizers"][0]["azureOpenAIParameters"].update(
        apiKey=None, authIdentity=None, resourceUri=EMBEDDING + "/",
    )
    actual["fields"].append({"name": "extra_platform_field", "type": "Edm.String"})
    deploy.validate_platform_index(actual, desired)


@pytest.mark.parametrize("field,key,value", [
    ("parent_id", "filterable", False),
    ("repo_id", "filterable", False),
    ("contentVector", "dimensions", 1536),
    ("contentVector", "vectorSearchProfile", "other"),
    ("heading_path", "analyzer", "standard"),
    ("title", "retrievable", False),
    ("repo_id", "key", True),
])
def test_field_mismatch_fails_without_any_write(desired, field, key, value):
    actual = deepcopy(desired)
    next(item for item in actual["fields"] if item["name"] == field)[key] = value
    with patch.object(setup, "get_search_resource", return_value=(actual, '"etag"')), patch.object(
        setup, "provision_indexes",
    ) as write:
        with pytest.raises(ValueError):
            deploy.ensure_index(ENDPOINT, "2025-05-01-preview", desired, Mock(), apply=True)
    write.assert_not_called()


@pytest.mark.parametrize("section", ["model", "deployment", "endpoint", "algorithm", "semantic", "profile", "missing-vectorizer", "identity-override", "api-key"])
def test_nonfield_mismatch_is_not_treated_as_compatible(desired, section):
    actual = deepcopy(desired)
    vector = actual["vectorSearch"]
    parameters = vector["vectorizers"][0]["azureOpenAIParameters"]
    if section == "model":
        parameters["modelName"] = "text-embedding-ada-002"
    elif section == "deployment":
        parameters["deploymentId"] = "other-embedding"
    elif section == "endpoint":
        parameters["resourceUri"] = "https://different.openai.azure.com"
    elif section == "algorithm":
        vector["algorithms"][0]["hnswParameters"]["metric"] = "dotProduct"
    elif section == "semantic":
        actual["semantic"]["configurations"][0]["prioritizedFields"]["titleField"] = {"fieldName": "content"}
    elif section == "profile":
        vector["profiles"][0]["algorithm"] = "unbound"
    elif section == "identity-override":
        parameters["authIdentity"] = {"userAssignedIdentity": "/different"}
    elif section == "api-key":
        parameters["apiKey"] = "not-a-real-key"
    else:
        vector["vectorizers"] = []
    with pytest.raises(ValueError):
        deploy.validate_platform_index(actual, desired)


def test_plan_has_no_mutations(desired):
    with patch.object(setup, "get_search_resource", return_value=(None, None)), patch.object(
        setup, "provision_indexes",
    ) as write:
        assert deploy.ensure_index(ENDPOINT, "2025-05-01-preview", desired, Mock()) == "create-planned"
    write.assert_not_called()


def test_existing_compatible_index_has_no_mutations(desired):
    with patch.object(setup, "get_search_resource", return_value=(desired, '"etag"')), patch.object(
        setup, "provision_indexes",
    ) as write:
        assert deploy.ensure_index(ENDPOINT, "2025-05-01-preview", desired, Mock(), apply=True) == "validated-existing"
    write.assert_not_called()


def test_create_uses_only_index_put_with_if_none_match_and_reads_back(desired):
    credential = Mock()
    credential.get_token.return_value.token = "not-a-real-token"
    absent = Mock(status_code=404)
    created = Mock(status_code=200, headers={"ETag": '"etag"'})
    created.json.return_value = deepcopy(desired)
    written = Mock(status_code=201)
    with patch.object(setup.requests, "get", side_effect=[absent, created]) as read, patch.object(
        setup.requests, "put", return_value=written,
    ) as write, patch.object(setup, "cleanup_knowledge_resources") as cleanup:
        assert deploy.ensure_index(ENDPOINT, "2025-05-01-preview", desired, credential, apply=True) == "created-and-validated"
    assert read.call_count == 2
    write.assert_called_once()
    assert write.call_args.args[0] == f"{ENDPOINT}/indexes/{NAME}?api-version=2025-05-01-preview"
    assert write.call_args.kwargs["headers"]["If-None-Match"] == "*"
    assert write.call_args.kwargs["json"] == desired
    assert write.call_args.kwargs["timeout"] == 30
    cleanup.assert_not_called()


def test_failed_conditional_create_does_not_overwrite_winner(desired):
    credential = Mock()
    credential.get_token.return_value.token = "not-a-real-token"
    with patch.object(setup.requests, "get", return_value=Mock(status_code=404)), patch.object(
        setup.requests, "put", return_value=Mock(status_code=412, text="PreconditionFailed"),
    ) as write:
        with pytest.raises(RuntimeError, match="was not deleted"):
            deploy.ensure_index(ENDPOINT, "2025-05-01-preview", desired, credential, apply=True)
    assert write.call_count == 1


def test_failed_read_is_not_interpreted_as_missing(desired):
    with patch.object(setup.requests, "get", return_value=Mock(status_code=403)), patch.object(
        setup.requests, "put",
    ) as write:
        with pytest.raises(RuntimeError, match="HTTP 403"):
            deploy.ensure_index(ENDPOINT, "2025-05-01-preview", desired, Mock(), apply=True)
    write.assert_not_called()


def test_read_back_mismatch_is_reported(desired):
    actual = deepcopy(desired)
    actual["fields"] = [field for field in actual["fields"] if field["name"] != "repo_id"]
    with patch.object(setup, "get_search_resource", side_effect=[(None, None), (actual, None)]), patch.object(
        setup, "provision_indexes",
    ):
        with pytest.raises(ValueError, match="Missing index field"):
            deploy.ensure_index(ENDPOINT, "2025-05-01-preview", desired, Mock(), apply=True)


@pytest.mark.parametrize("name", ["kb/other", "kb--test", "UPPER", "a", "https://other", "test?x=y"])
def test_invalid_target_name_fails_before_network(name):
    with pytest.raises(ValueError):
        deploy.render_index(name, EMBEDDING, "text-embedding")


@pytest.mark.parametrize("endpoint", ["http://test.search.windows.net", "https://evil.test", "https://test.search.windows.net/x", "https://user@test.search.windows.net"])
def test_invalid_endpoint_fails_before_credentials(desired, endpoint):
    with patch.object(setup, "get_search_resource") as read:
        with pytest.raises(ValueError):
            deploy.ensure_index(endpoint, "2025-05-01-preview", desired, Mock())
    read.assert_not_called()


def test_cli_exports_exact_schema_and_hash_but_does_not_apply_by_default(tmp_path, desired):
    path = tmp_path / "schema.json"
    with patch.object(deploy, "ensure_index", return_value="create-planned") as ensure:
        assert deploy.main([
            "--search-endpoint", ENDPOINT, "--index-name", NAME,
            "--embedding-endpoint", EMBEDDING, "--embedding-deployment", "text-embedding",
            "--schema-output", str(path),
        ]) == 0
    assert ensure.call_args.kwargs["apply"] is False
    assert json.loads(path.read_bytes()) == desired
    assert path.with_suffix(".json.sha256").read_text().split()[0] == hashlib.sha256(path.read_bytes()).hexdigest()
