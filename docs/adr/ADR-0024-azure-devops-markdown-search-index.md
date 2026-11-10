# ADR-0024: Accelerator-compatible indexing of Azure DevOps Markdown

**Status:** Implemented and validated for an isolated test index; serving adoption pending<br>
**Date:** 2026-10-26<br>
**Owners:** Platform and ingestion maintainers

## Context

The knowledge corpus will consist of Markdown files in an Azure DevOps Git
repository. A custom pipeline will read those files, produce chunks and
embeddings, and push documents into Azure AI Search. At the initial assessment,
neither the pipeline nor the index existed. The discussed `kb-sections-v1` JSON was a
proposal, not an existing compatibility constraint.

The application will use Foundry IQ with a `searchIndex` knowledge source.
Native Blob ingestion, Content Understanding, and Agent App Ingestion are not
required for this source. Orchestrator hosting is an independent decision:
using Foundry IQ does not require a Foundry-hosted orchestrator.

This record documents schema ownership and the subsequent isolated test-index
implementation below. It does not establish pipeline correctness, serving
adoption, retrieval quality or document authorization, and it does not authorize
production or sensitive-data ingestion.

The analysis used the `a7c8191` release snapshot. This ADR is recorded on the
`3ef6190` upstream `develop` baseline, whose relevant Search templates and
runtime component pins match the assessed contracts. Read current component
versions from [the release manifest](../../manifest.json), not this ADR.

Affected implementation boundaries:

- This platform repository owns the Search schema, knowledge-source
  registration, configuration, and compatibility tests.
- The custom ingestion pipeline owns source synchronization and document data.
- The orchestrator component owns retrieval normalization and application
  evidence handling. Runtime code remains in its component repository.

Prioritized characteristics and measures:

1. **Compatibility:** preserve the accelerator's query-facing field names and
   configuration bindings; contract tests must pass.
2. **Retrieval quality:** evaluate expected sections and correct source
   citations using representative Markdown questions, including Recall@3/5
   and answer-grounding checks. Set acceptance thresholds before evaluation.
3. **Reproducibility:** each chunk must identify its source revision, indexed
   text checksum, source location, and ingestion run.
4. **Lifecycle correctness:** retries must not duplicate documents; edits,
   renames, and deletions must not leave obsolete chunks searchable.
5. **Authorization:** independent allowed-user and denied-user tests must
   prove the chosen access policy before protected content is admitted.

## Alternatives considered

### Option A: Extend the bundled schema and keep compatible names (selected)

- Retain `contentVector`, `url`, `filepath`, `semantic-config`, and the existing
  provenance field names.
- Add typed Azure DevOps and Markdown metadata through reviewed templates.
- Let the platform own schema provisioning and the pipeline own documents.
- Preserve basic citation compatibility without adding a field-name adapter.
- Accept unused bundled fields rather than prematurely trimming the template.
- Review schema, identity, and component changes together; schema compatibility
  alone does not establish document authorization.
- Rebuild into a new physical index when an incompatible change is needed.

### Option B: Preserve the original custom-schema proposal

- Names such as `content_vector`, `wiki_url`, and `kb-semantic` are valid design
  choices, but are not the accelerator's current defaults.
- Requires explicit external-schema ownership, knowledge-source changes, and
  citation normalization changes in the orchestrator.
- Adds configuration, cross-repository coordination, and rollback complexity
  without preserving any already-deployed investment.
- Does not automatically preserve Azure DevOps permissions or audit fields.
- Remains viable if an independently owned index contract becomes a firm
  requirement, but is not justified for this greenfield pipeline.

### Do not change

- Keeps the accelerator's default native Blob source and requires no schema
  design work.
- Does not satisfy the intended direct Azure DevOps-to-Search ingestion path.
- Retains unnecessary ingestion dependencies and lacks explicit Markdown
  section, revision, and synchronization metadata.

## Decision

Adopt Option A as the design direction: use a versioned, heading-aware chunk
index with the accelerator's existing retrieval and citation contract, plus a
small set of typed metadata extensions.

### Serving provisioning adoption, 2026-10-30

The user has populated `kb-sections-ingestion-test-v1` and bound the existing
`azdo-markdown-ks`/`azdo-knowledge-base` to it. It is now a serving index despite
its name. The user approved aligning platform provisioning with that selection.

Introduce the setup selector `SEARCH_RAG_SCHEMA`, `standard` by default and
`ado_markdown_v1` as the explicit opt-in. Publish it under `agent-lz` through
the existing generic `additionalAppConfigurationSettings` infrastructure
parameter, both platform configuration publishers and Search settings.
No application component needs to interpret this setup-only key. Keep the
foundation workload-agnostic rather than adding a Markdown-specific Bicep
resource or parameter.

When opted in, post-provisioning renders the shared Markdown definition,
validates it against the pinned platform/consumer requirements, and uses the
same create-or-validate path as the standalone command before knowledge
reconciliation. Exclude that selected index from ordinary additive schema
updates. An existing mismatch, forbidden read or failed read-back must stop
before any index writes or knowledge cleanup; never delete/recreate the index
or alter document data. Other standard indexes retain their prior behavior.

Require an explicit index name and either direct Search retrieval or Foundry
IQ `searchIndex` selection. Reject conflicting legacy index-name overrides,
native Blob selection and unknown schema values. Keep all existing defaults.
Align both local index-name settings to the current serving target. This
change does not run full post-provisioning or update Azure configuration.

Alternatives: inferring the schema from the name is brittle; globally replacing
the standard definition changes unrelated deployments; retaining a manual
command alone leaves portal/configuration drift. The explicit selector is
reversible for an environment but is not a schema downgrade or data migration.
For incompatible revisions, provision a new generation and validate cutover;
do not switch a populated index back to standard merely to pass validation.
Review on embedding/schema changes, protected ingestion or serving cutover.

Implementation evidence:

- The selected index is excluded from additive schema updates; the shared
  create-or-validate path runs before other index writes and knowledge cleanup.
- Both local index-name settings now select `kb-sections-ingestion-test-v1`;
  the local schema selector is `ado_markdown_v1`. Composition materializes
  the matching settings through the native generic parameter under `agent-lz`.
- 386 affected Search, composition, configuration and lifecycle tests passed.
  Two existing Bash pre-deploy fixture failures were excluded after reproducing
  the same failure using the unchanged HEAD fixture. Separately, eight offline
  post-provision cases passed across PowerShell and Git Bash; both hooks parse.
- The standalone read-only check returned `validated-existing`, with no write,
  for the populated live index. An authenticated GET verified the current
  `azdo-markdown-ks` still targets that index.
- No full post-provision hook, infrastructure deployment or Azure configuration
  write was executed. The stored Azure selector/settings will be aligned by
  the next approved provisioning/configuration run. Standard defaults and the
  independent document-push ingestion model remain unchanged.

Source-data projection (2026-11-02): a knowledge source without
`sourceDataFields` returns only `id, content, title, category, heading_path`.
The orchestrator builds each citation link from `url` or `filepath`, so it sent
the model headers with no link, and the model invented `docs.microsoft.com`
URLs that returned 404. For `SEARCH_RAG_SCHEMA=ado_markdown_v1` the platform
template now projects `url, filepath, title, category, content, heading_path,
source_path, source_ref, source_version_id, start_line, end_line`; the standard
projection is unchanged. A knowledge source created outside the platform
(for example in the portal) must set the same projection.

### Isolated schema deployment approval, 2026-10-27

The user approved implementing the supplied `ado-markdown-ingestion`
`1.0.0-draft` consumer requirements and creating a separate non-serving
`kb-sections-ingestion-test-v1` index. Keep `kb-sections-v1`, application
configuration, and Foundry IQ source/base bindings unchanged.

Extract the existing RAG index template into a shared include, preserving its
default rendering. A render-only Markdown option adds the required fields,
explicit parent filtering and semantic priorities. It is not a new runtime
App Configuration contract at this isolated stage. The initial post-provision
path used the default schema; the subsequent serving adoption is recorded
above.

Provide a focused platform command that renders that same template, validates
the pinned consumer requirements, and reuses the existing conditional index
API helpers. It must create only a missing named index (`If-None-Match: *`),
read back and validate, or validate an existing index without mutation.
Incompatibility fails closed; no delete/recreate or automatic migration.
Do not invoke full Search setup, whose later stages reconcile knowledge
objects. A failed or ambiguous creation requires a fresh read/validation,
not resource deletion.

The reusable schema/include and conditional API implementation keep index
provisioning in the post-infrastructure phase without coupling every schema
deployment to infrastructure or ingestion execution. A separate definition
inside the worker would duplicate ownership; full post-provisioning would
unnecessarily touch serving resources; no change would leave the consumer
contract unmet.

Before creation, validate the full rendered platform definition and the
consumer-required subset, including service-normalized defaults, vectorizer
endpoint/deployment/model, HNSW cosine and semantic field ordering. Pin and
export the exact deployable schema bytes for the worker. The consumer contract
remains draft; its document-value, authorization and ingestion-runtime rules
are not established by index provisioning.

### Isolated deployment evidence, 2026-10-27

The index-only command created `kb-sections-ingestion-test-v1` with HTTP 201
over the existing VPN/private endpoint and validated the complete live
definition against the rendered platform schema and pinned draft consumer
requirements. It contains 46 physical fields, including all 23 consumer
requirements, and zero documents.

The deployed schema uses `text-embedding-3-large`, 3072 dimensions, HNSW/cosine
and deployment `text-embedding`. The live model deployment reports revision
`1`. This confirms configuration, not successful vectorizer execution or
retrieval quality. Semantic title/content/keyword priorities match the contract.
The query vectorizer uses Search's system identity without an API key.

The exported deployable schema SHA-256 is
`1e64ce198f9e4550792c9c55eb863a31e7fc60caa89b9c45dae2eba6ede012dd`.
The pinned consumer artifact SHA-256 is
`578bf9390eba2b0e62df68b9c01d13f0b93b9b2540c4053121c864f3983f3f94`.
The consumer artifact is semantically identical to the supplied handoff;
its original proposed-status/gaps prose is preserved as historical context.

Validation evidence:

- All 191 Search regression tests passed, including create-only race failure,
  forbidden reads, incompatible fields/vectorizer/semantic settings, read-back
  failure, service defaults and idempotent no-write behavior.
- Six old/new default-rendering comparisons proved the template extraction
  leaves the standard full Search resource definitions unchanged.
- Live pre/post comparison proved all four pre-existing index definitions,
  all aliases, `azdo-markdown-ks` and `azdo-knowledge-base` unchanged.
- Published `SEARCH_RAG_INDEX_NAME`, label `agent-lz`, remains `kb-sections-v1`.
- A second invocation returned `validated-existing` without an Azure write.
- No document ingestion, app configuration update, role grant, indexer/source
  creation or full infrastructure/post-provision operation was performed.

At the isolated rollout, normal post-provisioning still rendered the standard
schema. Do not send
the Markdown worker to `kb-sections-v1` merely because its name appears in the
draft contract: it is not the validated non-serving target. Serving adoption,
projection changes, source authorization and worker/runtime validation remain
separate gates.

Use `kb-sections-v1` as the initial physical index name. The suffix represents
an index generation, not a Git revision. Normal document updates do not require
a new physical index.

### Ownership

The platform defines and versions the index schema and registers its Foundry IQ
knowledge source and knowledge base. The custom pipeline uploads, updates, and
deletes documents; it must not independently redefine the schema.

An external-schema reconciliation bypass is not required merely to preserve
the earlier proposal. The current Search setup deliberately reconciles the
bundled schema, so changes must be made in the authoritative
[Search template](../../config/search/search.j2), not by manually creating a
competing schema with the same name.

### Retrieval and citation fields

The pipeline must populate the following fields. Preserve bundled field
attributes unless an intentional template change is validated.

| Field | Azure Search type | Contract |
| --- | --- | --- |
| `id` | `Edm.String` | Deterministic, unique chunk key. Retain the bundled key and keyword-analyzer contract. |
| `parent_id` | `Edm.String` | Stable source-file identity; explicitly filterable for synchronization. |
| `title` | `Edm.String` | Human-readable document and section title. |
| `content` | `Edm.String` | Searchable, retrievable chunk text with sufficient heading context. |
| `contentVector` | `Collection(Edm.Single)` | Embedding of the chunk using the agreed embedding input and dimensions. |
| `url` | `Edm.String` | Valid Azure DevOps Git source link, preferably pinned to the exact source commit. |
| `filepath` | `Edm.String` | Compatibility citation alias populated with the same usable source URL. |

`filepath` is not the repository-relative path in this contract. Keeping
clickable URLs in both citation fields avoids the different link preferences
of the current direct-Search and Foundry IQ retrieval paths. Validate section
or line targeting against Azure DevOps rather than assuming GitHub anchor
syntax applies.

### Azure DevOps and Markdown fields

Add these fields through the platform template. All are retrievable; set
searchability and filtering attributes explicitly.

| Field | Azure Search type | Contract |
| --- | --- | --- |
| `source` | `Edm.String` | Existing exact-value field; populate with `azure_devops`. |
| `repo_id` | `Edm.String` | Immutable repository ID; filterable, not full-text searchable. |
| `source_ref` | `Edm.String` | Selected Git ref; filterable, not full-text searchable. |
| `source_path` | `Edm.String` | Repository-relative Markdown path; filterable, not full-text searchable. |
| `heading_path` | `Edm.String` | Searchable heading breadcrumb supporting arbitrary heading depth. |
| `section_id` | `Edm.String` | Deterministic section identity; filterable, not full-text searchable. |
| `chunk_id` | `Edm.Int32` | Existing field; zero-based chunk sequence within the file. |
| `part` | `Edm.Int32` | One-based part number within a section. |
| `part_count` | `Edm.Int32` | Number of parts produced for that section. |
| `start_line` | `Edm.Int32` | One-based, inclusive start of the source extent. |
| `end_line` | `Edm.Int32` | One-based, inclusive end of the source extent. |

Do not add fixed `h2` and `h3` fields initially. `heading_path` and `section_id`
support deeper structures without a schema change.

### Provenance fields

Reuse existing platform fields instead of introducing synonymous audit names.

| Field | Azure Search type | Contract |
| --- | --- | --- |
| `source_version_id` | `Edm.String` | Exact Git commit used to read the source; replaces proposed `commit_sha`. |
| `content_checksum_sha256` | `Edm.String` | SHA-256 of the canonical indexed chunk text; replaces proposed `content_hash`. |
| `ingested_at` | `Edm.DateTimeOffset` | Time this document version was indexed. |
| `ingest_run_id` | `Edm.String` | Correlation with pipeline execution evidence. |
| `pipeline_version` | `Edm.String` | Version of the parser/chunking implementation; a new typed field. |

Resolve the selected ref to an immutable commit before reading files. Record
that commit and a documented text-normalization/checksum convention. Keep the
embedding model, dimensions, schema generation, and source selection in an
index/run manifest when those values are uniform across the index.

Defer separate owner, approval, review-date, link-graph, and whole-file-hash
fields until an actual source contract or query requires them. Whole-file
checksums can initially live in pipeline synchronization state. If governance
metadata is needed, prefer the existing `data_classification` field over a
parallel `classification` field.

### Chunking and synchronization

- Parse Markdown structure rather than splitting on heading-like text inside
  fenced code blocks.
- Keep ordinary sections intact; split oversized sections into bounded parts.
  Do not create empty search documents for headings without content.
- Preserve useful code blocks, tables, lists, and heading context. No OCR or
  visual interpretation is implied.
- Include title and heading context in embedding inputs and document the
  relationship between embedding inputs and the canonical indexed text.
- Choose size limits through evaluation, accounting for the model tokenizer
  and the application's effective context budget. The assessed `maf_lite`
  runtime defaults to `MAX_CONTENT_CHARS=4000` per retrieved record.
- Derive IDs from stable source and section identity plus part number, not the
  Git commit or content checksum. Heading changes and duplicate headings must
  be handled deterministically.
- After successful upserts, query the file's existing document IDs using
  `parent_id` and delete obsolete keys. Renames and source deletions require
  equivalent cleanup. Partial failures must be visible and safely retryable.

The logical retrieval unit is a bounded, coherent chunk, not an unconditionally
large Markdown section.

### Semantic and vector configuration

Start with the compatible values in
[the Search settings template](../../config/search/search.settings.j2):

- Text analyzer: `standard.lucene`.
- Vector field: `contentVector`, initially 3,072 dimensions.
- Vector profile: `default`, with cosine HNSW and query-time vectorization.
- Embedding model: the configured `text-embedding-3-large` baseline.
- Deployment identifier: the actual deployment name, currently `text-embedding`
  in the assessed root parameters; do not confuse it with the model name.
- Semantic configuration name: `semantic-config`.

For the new index, improve semantic priorities to use `title` as the title
field, `content` as the main content field, and `heading_path` plus meaningful
`category` values as keyword fields. This is a planned template change, not a
claim about the current shipped priorities. Semantic fields must be searchable
and retrievable.

Ingestion and query-time vectorization must use the same embedding model and
compatible configuration. Matching dimensions alone is insufficient. The
custom pipeline generates document vectors; the Search vectorizer generates
query vectors. It does not replace ingestion.

Do not send vectors to the language model. Retain compatible index attributes
and use deliberate result projections. Exclude provenance and URL fields from
full-text query scope where appropriate.

### Foundry IQ registration

Use these explicit deployment selections:

| Setting | Value |
| --- | --- |
| `RETRIEVAL_BACKEND` | `foundry_iq` |
| `FOUNDRY_IQ_PATTERN` | `searchIndex` |
| `FOUNDRY_IQ_KNOWLEDGE_SOURCE_KIND` | `searchIndex` |
| `SEARCH_RAG_INDEX_NAME` | `kb-sections-v1` |
| `DEPLOY_INGESTION_CONTAINER_APP` | `false` |
| `FOUNDRY_IQ_CONVERSATION_UPLOAD_ENABLED` | `false` |

The knowledge base and index must be on the same Search service. Extend source
projections when section/provenance evidence is required, while preserving
required existing fields. Basic citations use the compatible `title`, `url`,
and `filepath` names.

The current orchestrator normalizes Foundry IQ results to title, link, and
content. Extra projected audit fields do not automatically reach application
responses or telemetry. Index-level accuracy checks can query those fields
directly; application-level structured evidence requires a separate reviewed
runtime contract.

## Consequences

### Positive

- Avoids unnecessary citation-field adapters and external-schema ownership
  logic for an index that has not yet been built.
- Preserves existing component compatibility while adding useful source
  identity, section structure, and reproducibility metadata.
- Separates platform provisioning from ingestion execution and supports
  independent pipeline scheduling.
- Enables deterministic synchronization and versioned rebuilds without
  requiring native Blob ingestion or Content Understanding.

### Negative or accepted

- The physical index retains bundled fields for capabilities not used by this
  Markdown corpus. Leaving them unpopulated does not enable those capabilities.
- Serving adoption and source projections still require reviewed
  implementation and contract tests; the isolated Markdown definition is
  implemented and tested as recorded above.
- Embeddings, Search, and application runtime remain billable dependencies.
  This ADR makes no cost or retrieval-quality improvement claim without data.
- A minimal standalone schema could contain fewer fields, but trimming the
  bundled template is a separate compatibility decision.

### Security and open decisions

Azure DevOps permissions are not automatically preserved when documents are
copied to Search. Do not assume that every application user can read the whole
corpus. The existing permission-field family is a possible implementation
surface, not proof of enforcement; classification and owner metadata are not
access controls.

Before protected ingestion, define principal/group mapping, permission
synchronization, deny behavior, and query-time enforcement. Do not populate
Azure resource RBAC scopes with Azure DevOps identifiers as a substitute.
Resolve the documented hosted-entrypoint identity gap if hosted orchestration
is selected; registering a knowledge source does not repair it.

The corpus language mix, approved refs, exact chunk budgets, and evaluation
thresholds remain open. Canada East and public endpoints have been selected for
POC configuration preparation, not resource deployment. The target subscription
and tenant have been confirmed and global inference is approved for this POC.
A Canadian resource location does not make `GlobalStandard` model processing
Canada-only.

### POC configuration preparation

The local azd environment is configured for:

| Concern | Selection |
| --- | --- |
| Primary and Search region | `canadaeast` |
| Application Cosmos DB region | `canadacentral` (approved capacity fallback) |
| Orchestrator hosting | `DEPLOYMENT_TOPOLOGY=classic` |
| Retrieval | `foundry_iq` with matching `searchIndex` pattern and source kind |
| Index and semantic configuration | `kb-sections-v1`, `semantic-config` |
| Knowledge objects | `azdo-knowledge-base`, `azdo-markdown-ks` |
| Bundled ingestion and conversation uploads | Disabled |
| Networking and image builds | `NETWORK_ISOLATION=false`, `BUILD_MODE=acr-task` |
| Hosted Agent Service backing resources | `DEPLOY_AAF_AGENT_SVC=false` |
| Private build pool, firewall, jumpbox, Bastion, and NAT gateway | Disabled |

Public endpoints do not authorize anonymous application access or removal of
document permission enforcement. Authentication and permission defaults remain
unchanged. The existing global chat model configuration is retained with
explicit user approval of global inference. The confirmed subscription and
tenant are saved only in the local azd environment, not in this decision record.

The unsupported `aiFoundryLocation` entry is removed from the platform parameter
file and infrastructure seed. The account follows `AZURE_LOCATION`, as the
current Bicep template implements. Do not use `AZURE_AI_FOUNDRY_LOCATION` to
request a separate account region with this parameter set.

This preparation does not implement the proposed Markdown schema extensions,
build the custom pipeline, create an index, or provision Azure resources. Those
remain implementation and validation gates before accepting the POC end to end.

### Live readiness snapshot: 2026-10-26

Read-only checks against the confirmed subscription verified:

- Azure CLI subscription/tenant alignment and active azd authentication.
- Owner and User Access Administrator grants for the signed-in deployment user.
- Registration of required resource providers and advertised Canada East support
  for the selected resource types.
- `gpt-5-nano` GlobalStandard availability with 5,000 quota units remaining
  against 100 requested, and `text-embedding-3-large` Standard availability with
  250 remaining against 100 requested. Units are model/SKU quota units, not a
  common tokens-per-minute conversion.
- Container Apps regional managed-environment usage of 2 against a limit of 50,
  sufficient for the one proposed environment.

The shipped regional and foundation preflights each reported zero failures
and three warnings. The general quota API could not run because Microsoft.Quota
was not registered; the Microsoft.App service-specific usage API independently
verified managed-environment headroom without modifying provider registration.
The Cognitive Services headroom warning concerned other model allocations, not
the selected chat and embedding models. Optional Bing registration is not
required for this selection.

Remaining limitations include live Search/Cosmos capacity, no Cosmos zonal
redundancy in this selection, and the free Foundry IQ retrieval allowance.
Policy/deployment-preview and runtime authorization checks are not established
by these preflights. This is evidence for proceeding to an initial foundation
deployment review, not proof of deployed application readiness or approval to
provision resources.

### Provisioning blocker: 2026-10-26

After the user authorized provisioning, `azd provision --preview` failed with
HTTP 409 `ReadOnlyDisabledSubscription` while attempting resource-group
creation. A fresh Azure Resource Manager subscription query confirmed state
`Disabled`; cached CLI state and successful read-only preflights had not proven
write eligibility.

No provisioning or application deployment proceeded. The target subscription
must be re-enabled by its billing/subscription administrator before preview and
validation can be completed. Do not switch subscriptions or weaken controls as
a workaround. This operational blocker does not change the proposed schema.

### Partial provisioning after reactivation: 2026-10-26

A later fresh subscription query returned `Enabled`. The composed deployment
preview, definition binding, Bicep build, parameter tests, and live preflights
passed. Preview does not run the composition hook automatically; the hook was
run explicitly and a fresh preview verified that the ingestion app was absent.

The authorized foundation provisioning attempt then failed on Cosmos DB
`ServiceUnavailable`: Azure could not allocate the account in Canada East and
directed the subscription owner to request region access. Search Standard,
the Container Apps environment, ACR, storage, Key Vault, App Configuration,
and monitoring resources were created. The overall ARM deployment is `Failed`,
and the Cosmos account is also `Failed`.

Foundry/model and application-container dependencies did not complete, and
post-provision Search index/knowledge-source setup did not run. The schema,
ingestion, and application remain unimplemented and unvalidated end to end.

Keep the approved region selection until Canada East Cosmos access is granted
or an explicit alternative is approved. Do not delete successful resources or
remove persistence as an automatic recovery shortcut. Partial resources can
incur charges; deployment details and recovery evidence are retained in the
private deployment plan.

### Approved Cosmos-only regional fallback: 2026-10-26

The user approved keeping the foundation in Canada East and creating application
Cosmos DB in Canada Central to avoid the East capacity restriction. This adds
cross-region latency and potentially inter-region transfer charges for
conversation persistence; it does not relocate Search, models, application
hosting, or document ingestion.

The failed East account cannot be recreated under its existing name without
deletion. Because explicit deletion approval was unavailable, retain that
failed resource and use a Central-specific account name through the existing
native `dbAccountName` input. Set `AZURE_COSMOS_LOCATION=canadacentral`;
all other regional inputs stay `canadaeast`. Do not change the shared naming
algorithm or delete successful resources.

This is creation of a replacement for a never-functional account, not a data
migration or an assertion that serverless Cosmos accounts can be moved in place.
Validate the new outputs, application references, identity grants, and actual
resource locations before declaring recovery complete. Any eventual deletion
of the failed resource remains a separate authorized cleanup action.

### Split-region recovery verification

The recovery ARM deployment succeeded. Live verification confirmed the new
application Cosmos account and database in Canada Central, with Search,
Foundry/model deployments, application placeholders, and the rest of the
regional foundation in Canada East. The failed East account is retained.
Application configuration and scoped Cosmos grants reference the new account.

Post-provision discovery required a fix for implicit Azure CLI location
filtering and explicit selection of the replacement account. The PowerShell
resource/project discovery now clears the inherited location filter, and
Cosmos selection honors `DATABASE_ACCOUNT_NAME`. A project-local CLI defaults
override prevents unrelated Python discovery from inheriting the workstation
location filter; the global preference was not changed. The regression was
reproduced before correction, and 56 affected tests plus both hook syntax
checks passed afterward.

The infrastructure success is not a completed accelerator deployment.
Post-provision governance is blocked by Key Vault HTTP 403
`ForbiddenByConnection`: public network access remains `Disabled` even after
the approved public-mode setting was applied through CLI and direct ARM.
The cause had not yet been established during that recovery attempt; no policy
bypass or authentication relaxation was attempted. The investigation below
subsequently identified the enforcing management-group policy.

Configuration publication and capability-role verification completed before
that failure, but Search service setup did not run. Direct Search API reads
confirmed that no indexes or knowledge objects exist yet. Application
containers still use sample placeholder images. Retain the schema/ingestion
and end-to-end authorization gates; do not interpret this regional recovery
as evidence that Markdown retrieval is ready.

### Key Vault network-policy investigation: 2026-10-27

Read-only investigation established that the persistent setting is caused by
an inherited Azure Policy, not by a later application write or insufficient
secret permissions:

| Evidence | Verified finding |
| --- | --- |
| Policy assignment | `MCAPSGovDeployPolicies` / "MCAPSGov Deploy and Modify Policies" |
| Assignment scope | Parent management group; `enforcementMode=Default` |
| Policy definition | `KeyVault_PublicNetwork_Modify` |
| Initiative reference | `KeyVaultPublicNetworkModify` |
| Policy display name | "SFI-NS2.2.1 Secure PaaS Resources - Key Vaults (excluding NSP configured resources)" |
| Effective operation | `modify`, using `addOrReplace` on `Microsoft.KeyVault/vaults/publicNetworkAccess` with value `Disabled` |
| Applicable exemption | None returned for the vault |
| Vault access state | Provisioning succeeded; RBAC enabled; public access disabled; no private endpoint |
| Intended deployment state | Successful deployment used `networkIsolation=false` and no IP allow-list |

The policy's default effect is `modify`; the initiative and assignment do not
override it. The rule applies to public-access values other than `Disabled`
or a correctly configured perimeter mode unless its governed exclusion
conditions apply. The vault and its resource group do not satisfy the tag
exclusion condition. Exclusion mechanisms are governance decisions, not
permission for deployment automation to bypass the rule.

Azure Activity Log contains successful policy modification and vault-write
events with the same correlation IDs:

| UTC vault write time | Correlation ID | Result |
| --- | --- | --- |
| 2026-10-27 11:49:41 | `0d24293f-1acc-4468-b696-1de2ce9f6ab8` | Public-access field modified by the named policy; vault write succeeded |
| 2026-10-27 11:50:06 | `3f1ee418-9108-4b5e-9d58-93dcfa1738fb` | Same policy modification; vault write succeeded |

These are modifications during request evaluation, explaining why the CLI and
ARM updates reported success but the resource continued to read `Disabled`.
The Bicep template already derives `Enabled` for the selected public topology;
repeating the update, assigning more secret roles, or recreating the vault
under the same governed scope would not remove this policy requirement.

The earlier subscription-only CLI policy listing was not sufficient evidence
about inherited enforcement. A direct ARM policy-assignment query at the vault
with `$filter=atScope()` returned the management-group assignments, and reading
the exact definition plus correlated modification events proved applicability.

A fresh secret-metadata listing, requesting no secret values, returned HTTP
403: public access is disabled and the request is not through an approved
private link. Request ID: `9bea124f-3b9a-48b0-80ef-b5e901aa47a3`. A preceding
plain HTTP client probe timed out during TLS and was inconclusive; the bounded
SDK retry provided the authenticated denial evidence. Resource Health could
not be retrieved, so no service-health verdict is claimed.

Safe next actions require an explicit governance/networking decision:

1. For the selected public POC, ask the policy owner for a narrowly scoped,
   time-limited exception for this vault and initiative reference. After approval
   and effective exemption, reapply the approved networking configuration,
   verify it persists, verify authenticated secret access, and rerun
   post-provision configuration. Retain RBAC and review any additional inherited
   policy conditions before applying changes.
2. Without such approval, design a private endpoint and private DNS/connectivity
   for both the deployment host and application workloads. A private endpoint
   alone is insufficient if the current Container Apps environment and runner
   cannot reach it. Review cost, network integration, and incremental rollout
   before changing the current public foundation.

This investigation changed no Azure resources, tags, policies, exemptions,
roles, secrets, or networking. Cosmos remains in Canada Central, and the other
regional infrastructure remains in Canada East. No redeployment or secret
value reads were performed.

## Adoption and migration

The user subsequently approved and deployed private networking with a
point-to-site VPN. See [ADR-0025](ADR-0025-point-to-site-vpn-private-migration.md).
The public-POC settings and earlier failures above are historical context.
The private foundation is provisioned, while service configuration remains
deferred until the operator connects the VPN; the Markdown schema/ingestion
requirements below are unchanged.

1. Finalize source selection, authorization, embedding configuration, and
   measurable evaluation criteria before admitting sensitive data.
2. Update and test the platform schema, semantic priorities, and registration
   projections. Keep authoritative definitions in reviewed templates.
3. Provision `kb-sections-v1`, then implement the custom pipeline against that
   contract. Do not deploy an ingestion application or Blob knowledge source.
4. Validate indexing, citations, synchronization, retrieval quality, and
   allowed/denied-user behavior before enabling application traffic.
5. If runtime evidence handling changes, implement it in the orchestrator
   repository, validate the compatible commit combination, and bind it through
   the platform manifest. No component pin changes are made by this ADR.
6. For incompatible schema, analyzer, embedding, or chunking changes, populate
   `kb-sections-v2` alongside `v1`, validate it, update the stable knowledge-source
   binding and persistent deployment inputs, and retain `v1` for rollback.

The current Search setup cleans up and recreates knowledge objects during
reconciliation. Routine reprovisioning is not a zero-downtime cutover guarantee.
Design and test a deliberate source-update or blue/green procedure before
promising uninterrupted traffic.

Rollback restores the prior validated index binding and any paired application
configuration/component version; roll-forward reapplies the validated new
combination. Preserve old indexes and their compatible embedding configuration
until the rollback window is explicitly closed. Do not delete indexes as part
of this documentation change.

## Compliance verification

Assessment evidence, not live deployment validation:

- Rendering the existing templates confirmed `contentVector`, the `default`
  profile, 3,072 dimensions, and `semantic-config`.
- The actual schema-merge helper accepted ten additive Markdown/source fields
  while preserving the 36 bundled fields. Existing knowledge-source field
  references remained valid, and proposed semantic fields met type,
  searchability, and retrievability requirements.
- The focused tests
  `FoundryIqTemplateTests.test_conversation_upload_not_added_for_search_index_pattern`
  and
  `OptionalIngestionTests.test_explicit_alternative_index_is_preserved_and_not_inferred`
  passed on the assessed snapshot.

Implementation acceptance must additionally prove:

- Unique, repeatable IDs; correct line ranges; correct source commits and
  canonical text checksums; and no empty or oversized unhandled chunks.
- Correct embedding model, dimensions, vector profile, and query vectorizer.
- Idempotent reruns and removal of obsolete chunks after edits, renames,
  deletions, and partial-failure recovery.
- Known-answer retrieval and working Azure DevOps source citations, with
  measured Recall@3/5, grounding accuracy, and section coverage.
- Allowed-user access and negative tests excluding restricted content and
  citations from unauthorized responses.
- Safe index-generation cutover, persistent configuration, and rollback.

The initial schema analysis did not validate corpus quality, Azure index
creation, live quota, authorization integration or zero-downtime cutover.
Subsequent isolated creation evidence is recorded above; the remaining gates
are unchanged. Initial chunking and analyzer choices are evaluation baselines,
not empirically proven optima.

## Documentation impact

The isolated implementation updates ingestion, Foundry IQ and configuration
pages in the central AI Landing Zones documentation source on the coordinated
documentation feature branch. Serving adoption will require further guidance.
Do not duplicate product runbooks in this repository.

Related references:

- [ADR-0022: Optional ingestion application](ADR-0022-private-ingestion-options.md)
- [Foundry IQ integration and ownership](https://azure.github.io/AI-Landing-Zones/agent-landing-zone/foundry-iq/)
- [Agentic retrieval index requirements](https://learn.microsoft.com/en-us/azure/search/agentic-retrieval-how-to-create-index)
- [Chunking for RAG](https://learn.microsoft.com/en-us/azure/search/vector-search-how-to-chunk-documents)
- [Semantic field configuration](https://learn.microsoft.com/en-us/azure/search/semantic-how-to-configure)
- [Query vectorizers](https://learn.microsoft.com/en-us/azure/search/vector-search-how-to-configure-vectorizer)

## Review trigger

Review before first implementation and again when representative Markdown or
evaluation results are available. Reassess when the permission model, supported
languages, source refs, embedding model/dimensions, retrieval API, component
pins, context limits, or index-ownership requirements change, or when a
production availability or residency requirement is introduced.
