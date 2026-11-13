# Configuration and ownership

Return to the [deployment runbook](azure-devops-markdown-poc.md).
This page covers the delivered classic/private external-Markdown profile, not
the upstream hosted/native-Blob defaults.

## Where configuration lives

| Surface | Ownership |
| --- | --- |
| [Customer profile](../../samples/customer-poc/azd-env.example.json) | Operator inputs and separate bootstrap/connected phase overlays; copy/edit locally |
| `.azure/<environment>/` | Saved azd inputs, deployment outputs and bindings for that environment; never copy another customer's state |
| [Root parameters](../../main.parameters.json) | Shared template defaults, retained CIDRs and mapped environment placeholders |
| [Pre-provision hook](../../scripts/preProvision.ps1) | Regenerates infrastructure parameters from durable root inputs and the selected topology |
| [Manifest](../../manifest.json) and [application definition](../../app-definition.json) | Runtime source repositories, exact commits and application layout |
| Azure App Configuration, label `agent-lz` | Published runtime configuration; raw azd values are not automatically runtime settings |
| Azure Key Vault | Credentials resolved through approved references, not plaintext customer JSON |

Different azd environments can share one source checkout, but generated files,
default environment selection, component folders and local dependencies are
shared. Operate on one environment at a time; confirm tenant, subscription,
environment and destination resource groups before every write.

## Regions and resource identity

`AZURE_LOCATION=canadaeast` controls the primary region, including Foundry.
`AZURE_SEARCH_LOCATION=canadaeast` and `AZURE_COSMOS_LOCATION=canadacentral`
select the customer profile's other placements. Setting an unmapped variable
does not change Bicep; use the root parameter mappings. Model capacity and API
availability require validation in the customer's subscription.

Empty `COSMOS_ACCOUNT_NAME` uses generated naming for a new environment.
Existing environments must persist their actual account name before adopting
that parameter. `DATABASE_ACCOUNT_NAME` is a runtime/output binding, not the
input override. Canadian resource placement plus GlobalStandard chat deployment
does not establish Canada-only processing.

## Search index and embedding contract

The profile sets `SEARCH_RAG_SCHEMA=ado_markdown_v1`,
`SEARCH_RAG_INDEX_NAME=kb-sections-v1`,
`FOUNDRY_IQ_SEARCH_INDEX_NAME=kb-sections-v1`,
`FOUNDRY_IQ_SEMANTIC_CONFIGURATION_NAME=semantic-config`,
`RETRIEVAL_BACKEND=foundry_iq`, and both Foundry IQ pattern/kind to `searchIndex`.
The equal index names are required, not interchangeable overrides.

- The platform owns the schema, semantic/vectorizer definition and knowledge
  source/base. The [shared template](../../config/search/rag-index.j2) is the
  authoritative index definition.
- The [consumer contract](../../contracts/ado-markdown-index-consumer-v1.json)
  is a requirements contract, not the full deployable index body.
- The schema uses 3072-dimensional `contentVector`, HNSW/cosine and an Azure
  OpenAI query vectorizer. Ingestion/query embeddings must use the same
  `text-embedding-3-large` deployment/model/dimensions.
- Semantic priorities are title `title`, content `content`, then keywords
  `heading_path` and `category`.
- Connected [post-provision Search setup](../../config/search/setup.py) creates
  a missing Markdown index, or validates a compatible existing index without
  changing its schema or documents. Mismatches fail before knowledge cleanup.
- The [index-only command](../../config/search/markdown_index.py) exports a
  rendered schema/hash and validates the target. `--apply` conditionally creates
  only a missing named index. It does not reconcile knowledge objects, publish
  configuration or delete/recreate an existing index.
- Full post-provisioning also reconciles knowledge objects; do not use it just
  to create an unrelated test index. For incompatible schema changes use a
  reviewed new generation/cutover, not destructive repair.

Project citation/source fields including `url`, `filepath`, `title`, `content`
and `heading_path` into retrieval. Persist knowledge-source/base names and
embedding bindings in the selected environment. A name containing `test` does
not make an index non-serving if a knowledge base/application references it.
Search schema API `2025-05-01-preview` and embedding inference API
`2025-01-01-preview` have different roles.

## Retrieval strategy and citations

Explicit `AGENT_STRATEGY=maf_lite` is validated and published by both platform
configuration paths under `agent-lz`. If absent, the platform does not override
the component strategy default. The profile uses `CHAT_BACKEND=orchestrator`
and classic Container Apps; do not substitute hosted-specific auth settings.

The pinned orchestrator permits `NO_RETRIEVAL_FOLLOWUP` only after a nonempty
previous assistant answer; otherwise a factual first turn retrieves. Greetings
retain their normal no-retrieval behavior.

For `maf_lite`, `CITATION_GUARD_MODE` defaults to `enforce`. Unknown streaming
Markdown source links become plain label text and repeated links are simplified;
persisted answers match the sanitized stream. Overlong candidates stop buffering
and render their opening delimiter as literal text, with an `overlong` count.
`log_only` preserves output and logs counts; `off` disables inspection; unknown
values enforce. Publish through the component's supported configuration path and
restart/reload as required.

This is not factual verification, URL reachability or document authorization.
Bare URLs, autolinks and reference-style links are not covered. Links inherited
from old assistant messages lack independently proven retrieval provenance.
Test stream/history agreement, old conversations and each mode. Selecting new
source does not update running images; rollback needs compatible image/config.

## Local image builds

The customer profile selects `BUILD_MODE=local` and disables the ACR Tasks
agent pool. Use healthy Linux/amd64 Docker on a host connected to the private
registry. This does not make package-download egress unnecessary.

- UI accepts a local-build `PIP_INDEX_URL` override.
- Orchestrator accepts local-build `PIP_INDEX_URL` and `NPM_CONFIG_REGISTRY`.
- These overrides do not change ACR Task builds or dependency versions.
- Only credential-free HTTPS URLs without user information, query strings or
  fragments are accepted. Authenticated feeds require a separately reviewed
  build-secret mechanism. Never disable TLS to bypass download failures.
- The UI repeats dependency installation after building package metadata and
  runs `pip check`; this is not a dependency-version upgrade.
- Both components exclude root/nested `.env*`, local state/configuration,
  upload caches, logs and cache directories from Docker contexts. Git cleanliness
  does not detect ignored files. Keep context-export regression tests and never
  add credentials elsewhere in source.

## Pipeline and state ownership

The platform deploys the separate [control-state store](../../infra/ingestion-state.bicep)
only when explicitly invoked through Azure CLI. It grants the supplied writer
container-scoped Storage Blob Data Contributor, not Search/inference permissions.
It creates no Markdown staging source or Search indexer.

Step 5 of the [deployment runbook](azure-devops-markdown-poc.md#5-deploy-the-independent-control-state-store)
generates the state parameter file from selected azd values and read-only
network/DNS queries; no manual JSON edits or resource-ID copying is required.
`INGESTION_STATE_WRITER_PRINCIPAL_ID` must be the explicitly approved worker
service-principal object ID. Optional `INGESTION_STATE_RESOURCE_GROUP_NAME` and
`INGESTION_STATE_STORAGE_ACCOUNT_NAME` preserve custom existing state names.
These are operator-only azd metadata for parameter generation, not runtime
settings or automatic inputs to `azd provision`.

The independent worker owns document synchronization, embeddings, leases,
run intents and checkpoints. Its schema-read, document-write, inference, state,
repository checkout and WIF permissions are separate.
Use its delivered source/publishing TOML, source admission and publishing
templates. Application/foundation promotion YAML from the general documentation
is not that worker's ingestion pipeline.

The worker must run on an approved private-network-connected agent. A VPN on
a developer laptop does not give Microsoft-hosted agents private connectivity.
Do not admit protected documents until the permission contract and negative
retrieval tests are approved; source-repository permissions are not copied
automatically into Search.
