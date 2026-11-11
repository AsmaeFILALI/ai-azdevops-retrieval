# Customer deployment handover: implementation plan

**Date:** 2026-11-10<br>
**Status:** Source implementation complete; offline checks verified; publication/live adoption gated<br>
**Platform baseline:** `develop` at `f6ce8eb7aaeffb306d83356e215910cdb8e5a9a1`<br>
**Planning branch:** `feature/customer-deployment-handover`<br>
**Scope source:** Customer-readiness assessment and the user's request to retain the current network addresses

## 1. Goal and boundaries

Enable a customer to obtain reviewed source, configure their own Azure tenant
and subscription, provision the same logical private POC infrastructure, deploy
the UI and orchestrator, and onboard their own Azure DevOps Markdown ingestion.
The deployment must not depend on our saved environment, sibling worktrees,
personal resource names, private registry, VPN profile, or manual portal edits.

This is a repository engineering plan, not a second copy of product deployment
documentation. Customer/operator instructions belong in the central
`Azure/AI-Landing-Zones` documentation source. The platform README should link
to that guidance and to sanitized, versioned examples.

The user subsequently requested implementation on 2026-11-10. Source
portability work and coordinated documentation are now in progress on the
planning branch. No Azure resource changes, component publication, Git tags,
GitHub releases, repository visibility or customer access changes are included.

### Implementation decisions and remaining gates

- Deliver the existing clean pinned runtime baseline. Preserve but exclude
  uncommitted UI/orchestrator packaging/citation experiments until separately
  reviewed, validated and published. No new component version is fabricated.
- Subsequent user approval on 2026-11-10 authorizes local component and
  coordinated handover commits. Focused runtime tests and credential-free feed
  checks are verified; publication, component pin changes, full image builds
  and deployment remain separate gates. The committed runtime candidate is
  therefore not yet part of the platform's selected upstream baseline.
- Main Cosmos naming is now portable; the existing POC's exact account was
  persisted to `COSMOS_ACCOUNT_NAME` in its ignored azd environment first.
- The tracked fresh-clone parameter seed is synchronized with root inputs.
  The clean-source rehearsal found the old seed was masked by local generation.
- The consumer checksum now matches Git's exact LF bytes, not the pre-existing
  CRLF working copy. Contract semantics/version are unchanged. Strict integrity
  verification remains enabled.
- The offline handoff refuses contradictory non-serving declarations against
  the recorded main binding. Current live serving status still needs validation.
- Customer context/access, registry image digests, clean component image builds,
  authenticated local startup, publication and live ingestion/recovery remain
  outstanding gates. No workload VPN route is currently available; registry
  digest lookup could not be completed. Do not infer success from image tags.
- Central site and worker edits are coordinated local source changes, not
  published customer documentation. The unrelated `golden-qa.jsonl` remains
  untouched and excluded.

Offline evidence is recorded under ignored `.local/customer-handover/`:
source decisions, image metadata limitations, source hashes and clean-snapshot
results, test logs, strict documentation build and delivery status. This path
is working evidence, not something to copy wholesale to the customer.

### Explicit scope adjustment: keep current addresses

Do not redesign, renumber, or introduce CIDR parameterization in this work.
Retain the following layout:

| Purpose | Existing address range |
| --- | --- |
| Workload VNet | `10.77.0.0/21` |
| Agent subnet | `10.77.0.0/24` |
| Container Apps environment subnet | `10.77.1.0/24` |
| Private endpoint subnet | `10.77.2.0/26` |
| Reserved Bastion subnet | `10.77.2.64/26` |
| Reserved Firewall subnet | `10.77.2.128/26` |
| Gateway subnet | `10.77.2.192/26` |
| Application Gateway subnet | `10.77.3.0/27` |
| Jumpbox subnet | `10.77.3.64/27` |
| Build-agent subnet | `10.77.3.96/27` |
| VPN DNS resolver subnet | `10.77.3.128/28` |
| VPN client pool | `172.27.240.0/24` |

Reserved subnets do not imply their optional services are deployed. Preserve
the dedicated `GatewaySubnet` restrictions. Resolver addresses and private
endpoint IPs must be obtained from each customer's deployment, not copied from
our environment.

Keeping these addresses does not waive connectivity validation. If the customer
later reports a conflict with connected networks, stop that deployment and
handle address changes as a separately approved follow-up.

### Out of scope

- Changing the existing network layout or adding new networking products.
- Converting the POC to Foundry-hosted orchestration, native Blob ingestion,
  Content Understanding, or the bundled ingestion application.
- Implementing a new ingestion worker inside the platform repository.
- Automatically changing existing serving-index bindings or migrating data.
- Disabling authentication, opening public endpoints, granting broad roles, or
  suppressing policy controls to make deployment succeed.
- Claiming production document authorization or Canada-only inference.
- Publishing or deploying anything without the relevant human approval.

## 2. Evidence and technical context

The assessment established the following:

- The POC platform changes are merged into `develop`; the repository default
  `main` does not yet include them.
- [Root parameters](../../main.parameters.json) hardcode the current globally
  unique Cosmos account name. The customer needs generated naming or an
  explicit customer-specific override.
- [The tracked infrastructure seed](../../infra/main.parameters.json) is
  intentionally present for fresh initialization. The pre-provision hooks
  regenerate it and mark it skip-worktree. Keep root/seed changes consistent;
  do not remove the seed as a shortcut.
- Fresh unconfigured defaults select `hosted-no-panel`, native `azureBlob`
  ingestion and the standard schema, not this POC.
- [State storage](../../infra/ingestion-state.bicep) is a separate additive
  deployment. It is not invoked by [the main azd definition](../../azure.yaml).
- UI and orchestrator checkouts contain local packaging changes; the
  orchestrator also contains retrieval/citation work not represented by its
  pinned commit. Short image tags do not establish clean-source provenance.
- The worker is separate. Its current assessed source is on `generalisation`
  at `228731d9c12fbef132598252bc4cea99ecf0d73b`. Reconfirm that revision before
  selecting a customer pin; a branch name is not an immutable delivery.
- Platform/worker required fields, embedding requirements and vector
  requirements agreed during the assessment. Both contracts still identify
  permission enforcement as a separate unresolved concern.
- Central documentation changes exist in a separate local feature checkout;
  they are not automatically delivered with the platform repository.

Technical baseline: repository-owned Bicep, Python configuration modules,
PowerShell/Bash azd hooks, private Container Apps UI/orchestrator, Foundry IQ
`searchIndex`, Azure AI Search, Azure OpenAI embeddings, application Cosmos DB,
Key Vault, App Configuration, and a dedicated private Blob control-state store.
The worker requires Python 3.12 and its locked uv toolchain.

Use the existing architecture decisions:
[Markdown contract](../adr/ADR-0024-azure-devops-markdown-search-index.md),
[VPN/private migration](../adr/ADR-0025-point-to-site-vpn-private-migration.md),
and [control-state storage](../adr/ADR-0026-ingestion-control-state-storage.md).
Do not invent a replacement architecture or new service boundary.

## 3. Requirements

These IDs organize this plan; they are derived from the requested handover,
not from a separate formal specification.

| ID | Requirement |
| --- | --- |
| REQ-001 | Retain every existing CIDR and the current private POC topology. |
| REQ-002 | Remove dependence on our resource names and saved environment while preserving existing deployments. |
| REQ-003 | Provide an explicit, sanitized customer configuration profile. |
| REQ-004 | Deliver reproducible, accessible platform/UI/orchestrator/worker source revisions. |
| REQ-005 | Document private-network bootstrap, authentication, build and service configuration. |
| REQ-006 | Provide separate state-store deployment inputs and a nonsecret worker handoff. |
| REQ-007 | Onboard the worker with exact schema, identity, source and pipeline approval inputs. |
| REQ-008 | Publish consistent customer guidance in the central documentation site. |
| REQ-009 | Demonstrate a clean-checkout deployment with verifiable acceptance evidence. |
| REQ-010 | Preserve authorization boundaries, data, rollback options and human publication/deployment approvals. |

### Engineering constraints

- Feature branches start from `develop` and target `develop`. No automatic
  merge to `main`, version bump or release publication.
- Keep runtime changes in their component repositories and preserve the
  authoritative component pins in `manifest.json`.
- Use managed identity/WIF for service access and Key Vault references for
  secrets. Examples contain placeholders, never live credentials.
- Keep PowerShell and Bash behavior aligned when lifecycle hooks change.
- Preserve native JSON arrays and existing empty-value naming fallbacks.
- Publish runtime configuration under the existing `agent-lz` contract; do not
  assume an arbitrary azd environment variable becomes a runtime setting.
- Use existing validation commands and conditional Search helpers.
- No migration/rewrite guidelines apply: this is portability and handover work,
  not a framework migration.

## 4. Target customer configuration package

### 4.1 Platform inputs versus outputs

Add a sanitized `samples/customer-poc/azd-env.example.json` containing only
documented operator inputs. Use documented `azd env set` operations to apply
reviewed entries; do not execute or source an untrusted `.env` file.
Do not build a new configuration framework or importer unless the example
cannot be applied safely with existing commands.

| Configuration area | Required treatment |
| --- | --- |
| Identity/context | Customer environment name, tenant, subscription, deployment principal object ID and principal type. |
| Regions | Example uses Canada East with application Cosmos DB in Canada Central; validate customer capacity and policy before deployment. |
| Resource names | Generated by default; optional explicit Cosmos override for approved capacity/adoption cases. |
| Network | Preserve the address table above; isolated standalone POC with template-managed Entra/OpenVPN and DNS resolver. |
| Hosting | Explicit `DEPLOYMENT_TOPOLOGY=classic` and `CHAT_BACKEND=orchestrator`. |
| Retrieval | Explicit Foundry IQ `searchIndex`, `SEARCH_RAG_SCHEMA=ado_markdown_v1`, matching index-name inputs and `semantic-config`. |
| Ingestion selection | Bundled ingestion and conversation uploads disabled. |
| Optional resources | Explicitly disable hosted orchestration/backing services, administrative panel, VM/software, jumpbox, Bastion, firewall and private ACR Tasks pool for this profile. |
| Egress/build | Preserve NAT egress; `BUILD_MODE=local` requires working Docker, customer ACR access and approved dependency egress. |
| App configuration | Publish `AGENT_STRATEGY=maf_lite` through an explicit supported runtime-configuration path, not an inert azd-only setting. |
| Authentication | Customer Entra registration/consent/redirect URI and secret references; no anonymous-mode shortcut. |
| Generated bindings | Endpoint URLs, service names, resource IDs, identity IDs, DNS addresses and application FQDNs come from the new deployment. |

Do not copy our migration-specific Container App names, existing failed Cosmos
account, old deployment names, local feed configuration or runtime outputs into
the customer profile.

### 4.2 Cosmos naming change

Propose one new **input**, `COSMOS_ACCOUNT_NAME`, mapped to `dbAccountName` in
both root parameters and the tracked seed. Empty means the existing Bicep
generated-name behavior. Keep the existing `DATABASE_ACCOUNT_NAME` runtime
output unchanged.

Before using the new parameters against an existing environment, persist that
environment's actual account name into the new input and verify a no-replacement
preview. Removing the hardcoded name must not silently switch our POC to a new
database account.

### 4.3 Separate state-store inputs

Add `samples/customer-poc/ingestion-state.parameters.example.json` for:

- Customer environment/location and optional dedicated RG/account overrides.
- Existing private endpoint subnet and Blob private DNS zone ARM IDs.
- Approved writer service-principal object ID/type.
- `ingestion-state` container and explicit recovery retention.

Have the customer create/select the publishing WIF identity before supplying
the writer principal. The state template requires an explicit principal; do not
invent one or silently default to the deployment user's identity.

Retain private networking, disabled Shared Key/anonymous access, LRS/Hot,
versioning and the current 14-day recovery window. Prefixes and blobs remain
worker-owned. Do not combine this store with Markdown/document storage.

### 4.4 Worker handoff

The final nonsecret handoff must contain:

| Binding | Source of truth |
| --- | --- |
| `search_endpoint`, physical `index_name` | Customer Search resource plus explicitly reviewed target selection. |
| `embedding_endpoint`, deployment/model/dimensions | Customer deployed model and matching platform vectorizer. |
| `openai_api_version` | Explicit owner-approved embedding inference version, not ARM API version or model revision. |
| `search_schema_api_version` | Version supporting the actual deployed schema; do not silently substitute the worker example's default. |
| `state_account_url`, `state_container` | Standalone state deployment output. |
| `platform_schema`, `schema_sha256` | Newly rendered full customer index schema and its exact bytes. |
| Tenant/client/service-connection IDs | Customer WIF service connection and its service principal. |
| Repository/ref/path rules | Customer content-owner-approved source configuration. |
| Admission file/hash or approved test waiver | Separate owner decision; never auto-generated approval. |

Regenerate the schema/hash for each customer target because its name and
embedding endpoint are part of the definition. Do not reuse our artifact hash.
Use Entra authentication; no account keys, SAS or connection strings.

## 5. Implementation phases and tasks

Paths are relative to the owning repository. Runtime paths refer to sibling
`agent-app-ui`/`agent-app-orchestrator`; worker paths refer to the separate
`injection-pipeline` checkout. Central documentation paths refer to the
`Azure/AI-Landing-Zones` source repository.

### Phase 1: Establish the exact handover baseline

**Plan item 1.1:** Freeze evidence and decide the runtime change set.<br>
**Requirements:** REQ-004, REQ-010.<br>
**Prerequisites:** None.<br>
**Exit:** Required source changes and customer-accessible repository owners are
known; unpublished work is not mistaken for a released capability.

- [ ] T001 [Plan:1.1] Record platform/worker commits, actual deployed image digests, component worktree differences and nonsecret configuration selections in ignored `.local/customer-handover/baseline.json`; exclude secrets, tokens and retrieved content.
- [x] T002 [Plan:1.1] Review the UI `Dockerfile` and `scripts/deploy.ps1`/`scripts/deploy.sh`, plus orchestrator `Dockerfile`, deployment scripts, `src/strategies/retrieval_intent.py`, `src/strategies/maf_lite_strategy.py` and `src/util/citation_guard.py`; explicitly choose which existing local changes the customer must receive. Preserve unrelated work.
- [ ] T003 [Plan:1.1] Confirm customer read/build access to the repositories referenced by `manifest.json`, `app-definition.json` and the worker pipeline repository resource; record approved owners and delivery revisions without publishing or changing visibility yet.

### Phase 2: Make platform configuration portable

**Plan item 2.1:** Parameterize only the environment-specific resource name,
publish required runtime settings and supply a complete profile.<br>
**Requirements:** REQ-001, REQ-002, REQ-003, REQ-005, REQ-010.<br>
**Prerequisites:** T001 establishes the existing environment's preservation inputs.<br>
**Exit:** A fresh environment selects the intended POC and generates new resource
names; an existing environment retains its account/app identities and all CIDRs.

- [x] T004 [Plan:2.1] Replace the POC Cosmos literal with `${COSMOS_ACCOUNT_NAME=}` in `main.parameters.json` and the tracked `infra/main.parameters.json` seed; preserve `DATABASE_ACCOUNT_NAME` outputs and existing Bicep naming logic.
- [x] T005 [Plan:2.1] Add `samples/customer-poc/azd-env.example.json` with the complete reviewed POC input set, required placeholders, existing addresses and separate bootstrap/final connectivity settings; omit generated outputs and migration-only names.
- [x] T006 [Plan:2.1] Wire explicitly supplied `AGENT_STRATEGY` through existing configuration publication in `main.parameters.json`, `config/deployment/composition.py` and/or `config/deployment/appconfig.py` as required after tracing the current path; preserve other deployments' defaults and publish the customer selection as `maf_lite` under `agent-lz`. Keep paired hooks equivalent if touched.
- [x] T007 [Plan:2.1] Add `tests/test_customer_profile.py` for root/seed portability, complete profile composition, effective runtime strategy and exact retained address ranges; run it with existing infrastructure/composition/Search regressions.

### Phase 3: Make runtime source and images reproducible

**Plan item 3.1:** Package only the approved component fixes and bind them into
the platform's existing source contract.<br>
**Requirements:** REQ-004, REQ-005, REQ-010.<br>
**Prerequisites:** T002-T003; this phase can proceed independently of T004-T007.<br>
**Exit:** Clean component checkouts reproduce the selected behavior without
access to our worktrees or authenticated personal package feeds.

- [x] T008 [Plan:3.1] Commit and validate the approved UI/orchestrator source changes in their owning feature branches; focused runtime/feed tests, paired script syntax and Dockerfile static checks pass. Full image builds and publication remain T010/T011 gates.
- [x] T009 [Plan:3.1] Add fail-closed dirty-worktree checks for bundled and commit-pinned custom component build contexts in `scripts/preDeploy.ps1` and `scripts/preDeploy.sh`; add executable paired guards in `tests/test_component_source.py`, update custom-hook fixtures and preserve unrelated local edits instead of resetting them.
- [ ] T010 [Plan:3.1] Verify UI/orchestrator `Dockerfile` and child deployment scripts build from approved public sources or explicitly configured customer feeds; never pass authenticated feed credentials through committed files, logged arguments or persistent image layers.
- [ ] T011 [Plan:3.1] After component review and explicit publication approval, update `manifest.json` and matching `app-definition.json` source commits to the exact accessible validated component versions; extend existing pin contracts rather than selecting latest branches. Record matching image digests and compatibility evidence in the handover.

### Phase 4: Complete state-store and ingestion configuration handoff

**Plan item 4.1:** Add state parameters and export bindings from authoritative
customer artifacts without granting access or approving publication.<br>
**Requirements:** REQ-006, REQ-007, REQ-010.<br>
**Prerequisites:** T005 for naming/context; T003 for worker accessibility.<br>
**Exit:** The customer can configure the worker without manually copying our
service names or reconstructing the schema contract.

- [x] T012 [Plan:4.1] Add `samples/customer-poc/ingestion-state.parameters.example.json` matching the actual public parameters of `infra/ingestion-state.bicep`, with customer placeholders and the private POC recovery defaults.
- [x] T013 [Plan:4.1] Add a small read-only `config/deployment/ingestion_handoff.py` command, reusing existing output/ARM helpers, that requires an explicit target and combines main/state deployment outputs with the rendered schema/hash into a nonsecret JSON handoff. Reject conflicting identities/targets; do not deploy, assign roles, create approvals or change index bindings.
- [x] T014 [Plan:4.1] Cover handoff output shape, customer-derived endpoints, exact index/model/schema matching, missing or conflicting inputs and exclusion of secret-bearing fields in `tests/test_ingestion_handoff.py`; reuse `tests/test_ingestion_state.py` for state parameter/security contracts.

**Plan item 4.2:** Onboard the independently versioned worker and pipeline.<br>
**Requirements:** REQ-004, REQ-007, REQ-010.<br>
**Prerequisites:** T003, T012-T014.<br>
**Exit:** Reviewed worker source, source rules, schema and WIF configuration are
consistent; offline validation is distinct from live publication authorization.

- [x] T015 [Plan:4.2] Finalize the worker's `docs/deployment.md`, `docs/operations.md`, `examples/pipeline-source.toml` and `examples/publishing-config.toml` to consume the customer handoff and require matching schema/model/API versions and a reviewed immutable worker commit.
- [x] T016 [Plan:4.2] Review worker `scripts/New-IngestionIdentity.ps1` guidance and `examples/content-repo/azure-pipelines.yml` for customer-owned WIF, exact principal IDs, schema-read/document-write separation, container-scoped state permissions, private agent connectivity, protected environments and initial `enablePublishing=false`.
- [x] T017 [Plan:4.2] Document artifact delivery and schema/consumer-contract compatibility across platform `contracts/ado-markdown-index-consumer-v1.json` and worker `docs/index-contract.json`; preserve integrity sidecars and update them only with deliberate contract changes. Do not create a second index-definition owner.

### Phase 5: Publish the customer runbook and local development path

**Plan item 5.1:** Consolidate existing documentation edits and add one complete
customer journey in the central site.<br>
**Requirements:** REQ-003, REQ-005, REQ-006, REQ-007, REQ-008, REQ-010.<br>
**Prerequisites:** T004-T017 define the shipped interfaces; an initial outline
may be drafted earlier but must not be published ahead of those interfaces.<br>
**Exit:** An operator can follow the docs without our local files or portal
knowledge. Repository READMEs link to the correct versioned guidance.

- [x] T018 [Plan:5.1] In the central docs feature branch, add `docs/agent-landing-zone/azure-devops-markdown-poc.md` and register it in `mkdocs.yml`; describe pinned source access, prerequisites, approved inputs, model-policy review, private bootstrap, app deployment, state deployment, worker onboarding and acceptance.
- [x] T019 [Plan:5.1] Update central `configuration.md`, `deploy-infra-only.md`, `private-access.md` and `network-isolation.md` for `COSMOS_ACCOUNT_NAME`, profile input/output ownership, retained CIDRs, Entra VPN profile/DNS setup, explicit post-provision deferral and its mandatory completion.
- [x] T020 [Plan:5.1] Update central `ingestion.md`, `foundry-iq.md` and `azure-devops.md` for the state/handoff commands, distinct platform/worker pipelines, schema hash/version selection, citation projections, approved source audience and deliberate non-serving-to-serving adoption.
- [x] T021 [Plan:5.1] Add a local development section to the central customer runbook covering component checkout pins, Python 3.12, required UI/orchestrator entrypoints, App Configuration/Key Vault access, local Entra developer identity, ports and worker offline `plan`; obtain commands from the pinned component docs instead of inventing new launch commands.
- [x] T022 [Plan:5.1] Update platform `README.md` with a short customer-profile entry and correct source/version link; coordinate component/worker README links to the central guide. Keep long product instructions out of platform/service READMEs.

### Phase 6: Validate from a clean checkout and assemble delivery

**Plan item 6.1:** Prove portability with isolated validation and an approved
new environment, not with the existing POC.<br>
**Requirements:** REQ-001 through REQ-010.<br>
**Prerequisites:** T007, T011, T014, T017 and T018-T022. Live steps additionally
require explicit customer/subscription, cost, identity and data approval.<br>
**Exit:** The delivery meets the acceptance checklist below, with remaining
risks recorded honestly.

- [x] T023 [Plan:6.1] Run the affected existing Python, lifecycle and Bicep checks, root/seed/profile consistency checks, full offline infrastructure contracts and central strict documentation build; record results in ignored `.local/customer-handover/validation.json`.
- [ ] T024 [Plan:6.1] Rehearse profile application, dependency setup and local component/worker startup in a clean checkout with no sibling directories, copied `.azure` environments, inherited shell configuration or private registry access; record missing prerequisites rather than compensating with our local files.
- [ ] T025 [Plan:6.1] After explicit authorization, follow azure-prepare, azure-validate and azure-deploy for a new validation environment; verify the retained CIDRs, generated names, private DNS/TLS, actual security flags, deployed identities, image digests and completed post-provision state. Do not deploy from this plan automatically.
- [ ] T026 [Plan:6.1] With separately approved synthetic content, run worker offline validation, first admitted publication, no-change rerun and recovery checks; verify grounded UI answers, working source citations and the approved user-access boundary. Use an actually non-serving target for any test-only waiver.
- [ ] T027 [Plan:6.1] Assemble a sanitized delivery manifest and acceptance record, including platform/component/worker commits, image digests, docs revision, schema hashes, output/configuration files and residual risks; obtain approval before source publication, customer access changes, tags/releases or production deployment.

## 6. Documentation content checklist

The central customer guide must cover:

1. What is included and which separate repositories the customer must obtain.
2. Exact reviewed revisions and the supported Python, azd, Bicep and build tools.
3. Operator permissions versus application, worker and end-user permissions.
4. Customer input values, generated outputs and Key Vault secret ownership.
5. Fixed address layout, approved network path and VPN DNS/profile bootstrap.
6. Regional service/model availability, quota, preview API dependencies and costs.
7. Two-stage private provisioning: foundation first, connected service setup next.
8. Authenticated application startup and local development.
9. Separate state-store deployment and identity prerequisites.
10. Schema rendering/hash transfer, worker configuration and source admission.
11. Pipeline setup, publication disabled by default, self-hosted agent access.
12. Known-answer/citation, repeat-run, failure/recovery and access acceptance.
13. Troubleshooting: policy-modified network flags, public DNS answers, RBAC
    propagation, model availability, schema mismatch and private registry builds.
14. Upgrade, rollback and deliberate serving-index adoption.

Explicitly state that `GlobalStandard` chat inference is not guaranteed to stay
in Canada, even when resources are located there. Do not treat VPN access,
Entra application sign-in or Azure DevOps repository access as proof of
document-level authorization.

## 7. Validation and acceptance

### Source implementation evidence, 2026-11-10

- Final affected platform/Search integration: **414 passed, 353 subtests passed**.
- Canonical LF contract/profile/handoff final checks: **28 passed**.
- Clean isolated Git source archive plus explicit source edits: **65 passed**,
  with no `.azure`, sibling component folders or inherited customer context.
  It uses the existing dependency interpreter, so this is not evidence of a
  separate online dependency restore or authenticated application startup.
- Worker configuration: **20 passed** through its existing environment. An
  initial `uv run --offline` could not rebuild editable metadata because the
  pinned build backend was not cached; no dependency/lockfile was changed.
- Both Bicep entry points build/lint, **4,796,138** / **629,038** bytes, below
  4.7 MiB. The existing historical graph projections still pass.
- Deterministic private preflight: **98 checks, zero failures**.
- Paired custom deployment fixtures: final isolated rerun **2 passed and
  4 subtests passed**. An earlier concurrent rerun reached fixture subprocess
  budgets; no product timeout or security setting was relaxed.
- Central documentation strict build succeeds; navigation includes the new
  guide. Its pages and the worker edits are not yet published.
- Pylance reports no diagnostics in the changed Python implementation modules.
- Full offline foundation suite: **all 16 entrypoints passed**. Eleven passed
  before a slow concurrent run was interrupted; the remaining five passed in
  a serial resume, including the original Storage and hosted graph checks.

### Explicitly incomplete/approval-gated tasks

| Tasks | Status and condition |
| --- | --- |
| T001 | Source and ARM image metadata captured; registry digest lookup unavailable over current private network path. |
| T003 | Public pinned component tags verified; customer-specific worker/repository access and ownership still need confirmation. |
| T011 | Local component source commits now exist, but the platform pins remain unchanged. Publication and compatible pin adoption still require explicit review/approval. |
| T010 | Source/feed handling reviewed; new clean component Docker builds and any corporate-feed integration still need validation. |
| T024 | Clean offline source validation passes; authenticated UI/orchestrator startup remains unverified. |
| T025, T026 | Require customer tenant/subscription, explicit paid deployment/data approval and working private connectivity. No Azure writes performed. |
| T027 | Local delivery-status evidence exists; final accepted package/publication awaits the above gates. |

Only the specific evidence above has been verified. The deployment acceptance
checklist below is not a claim of live customer readiness. Reuse existing tools;
restore dependencies only when required.

Representative existing commands from the platform root:

```powershell
python -m pytest tests/test_infra_checkout.py tests/test_deployment_modes.py tests/test_release_contracts.py config/search/tests -q
az bicep build --file .\infra\main.bicep --outfile .\.azure\customer-main.json
az bicep lint --file .\infra\main.bicep
az bicep build --file .\infra\ingestion-state.bicep --outfile .\.azure\customer-state.json
az bicep lint --file .\infra\ingestion-state.bicep
pwsh -NoProfile -File .\infra\tests\Invoke-OfflineContracts.ps1
```

Add the tests for implemented tasks to that selection, validate both hook
implementations if touched, and enforce the existing 4.7 MiB compiled-template
gate. Preserve original graph fingerprints; do not replace them to force a pass.
Use the documentation repository's strict build and the pinned component/worker
quality commands.

### Delivery acceptance checklist

- A new customer environment generates its own globally unique resource names;
  no existing POC endpoint/account name is required.
- All CIDRs exactly match section 1. VPN/DNS values come from the new deployment.
- The new profile selects classic/private/Markdown without hosted, Blob-indexer,
  upload or Content Understanding prerequisites.
- Existing environments preserve resource identity after the Cosmos input
  migration; no preview proposes unintended replacement or deletion.
- Application images are reproducible from clean, accessible source and their
  exact digests are recorded.
- The UI starts with approved authentication and reaches the intended
  orchestrator; the configured direct-model strategy is effective.
- The state store is private, keyless, recoverable and assigned only to the
  explicit approved writer; no Markdown is staged there.
- Search/vectorizer and worker use the same embedding deployment/model and
  3072-dimensional contract, with an exact customer schema/hash.
- First publication produces verified state/documents; an unchanged rerun
  performs no unnecessary embedding or document mutation.
- The approved recovery scenario does not mark incomplete publication as a
  successful checkpoint.
- Representative answers use real retrieved Azure DevOps citations.
- Allowed/denied access is validated for the intended content. Until a protected
  permission contract is implemented and approved, restrict the validation corpus
  to synthetic or explicitly approved common-audience non-sensitive documents.
- Documentation and examples match the exact delivered source combination.
- No credentials, source content, private profiles or live approval artifacts
  leak into source, logs or the delivery package.

## 8. Adoption order, rollback and residual decisions

### Adoption order

1. Approve included runtime fixes and customer-accessible repositories.
2. Implement portable inputs/profile and preserve existing POC identity overrides.
3. Validate and publish approved component sources before binding platform pins.
4. Finalize state-store and worker handoff, with compatible worker revision.
5. Review coordinated central docs and exact command examples.
6. Validate offline, then rehearse on a separately authorized new environment.
7. Deliver the accepted combination; use the normal release workflow only after
   explicit release approval.

### Rollback boundaries

- Record previous manifest/app-definition pins, image digests and nonsecret
  bindings before adoption; never rely only on mutable image tags.
- Restore compatible code/configuration together if runtime validation fails.
- Do not delete/recreate accounts or reset schema/state as an error workaround.
- Preserve Search indexes, Blob checkpoints and Cosmos data on rollback.
- Keep an index generation unpromoted until accepted; restoring a serving
  binding is a separate deliberate operation, not a side effect of setup.
- State recovery must reconcile the corresponding Search publication state;
  Blob soft delete alone does not provide a cross-service transaction.

### Decisions that do not block writing this plan

| Decision | Required by | Decision criterion |
| --- | --- | --- |
| Include/exclude each local runtime change | T002 | Demonstrated customer behavior, regression evidence and reviewable source. |
| Customer hosting/access for component and worker repositories | T003 | Customer can fetch exact reviewed commits and templates without our credentials. |
| Customer tenant/subscription/deployment identity | Before live preflight/deployment | Explicit administrator-approved context and role scopes. |
| Model SKU/preview API approval and inference geography | Before live model deployment | Customer policy, current service support and actual quota/capacity. |
| App registration, consent and content audience | Before authenticated/protected use | Owner-approved identity model and verifiable access behavior. |
| Worker schema/admission delivery and protected agent pool | T016 and first publication | Reviewed immutable artifacts, private connectivity and least privilege. |
| Release version and publication | T027 | Acceptance complete and explicit human authorization. |

Do not silently fill these decisions using our tenant, identities, permissive
defaults, current local worktrees, or the existence of a successful ARM deployment.

## 9. Requirement mapping

Evidence below is expected future implementation evidence, not completed work.

| Requirement | Plan items | Tasks | Expected evidence |
| --- | --- | --- | --- |
| REQ-001: retained addresses/topology | 2.1, 5.1, 6.1 | T005, T007, T019, T025 | Exact profile/parameter comparison, VPN contract and new-environment verification. |
| REQ-002: portable names/environment | 2.1, 6.1 | T004, T005, T007, T024, T025 | Cosmos input/root-seed parity, new-name and preserve-existing results. |
| REQ-003: explicit safe profile | 2.1, 5.1, 6.1 | T005-T007, T018-T019, T024 | Versioned sanitized profile, effective strategy and fresh-clone instructions. |
| REQ-004: reproducible accessible sources | 1.1, 3.1, 4.2, 6.1 | T001-T003, T008-T011, T015, T024, T027 | Reviewed commits, clean-tree checks, manifest/app-definition pins and image digests. |
| REQ-005: private bootstrap/app execution | 2.1, 3.1, 5.1, 6.1 | T006, T010, T018-T019, T021, T024-T025 | Runtime publication, authentication/local-start instructions and connected setup evidence. |
| REQ-006: state deployment/handoff | 4.1, 5.1, 6.1 | T012-T014, T020, T025, T027 | State parameter example, verified nonsecret handoff and deployed private-store checks. |
| REQ-007: worker onboarding | 4.1, 4.2, 5.1, 6.1 | T013-T017, T020, T026 | Exact schema hash/model, WIF/agent/source inputs and admitted publication evidence. |
| REQ-008: consistent published guidance | 5.1, 6.1 | T018-T024, T027 | Central source revision, registered guide, strict build and correct README links. |
| REQ-009: clean-checkout proof | 6.1 | T023-T027 | Offline results, isolated startup, approved deployment and behavioral acceptance record. |
| REQ-010: compatibility/security/approval | 1.1-6.1 | T001-T004, T006, T008-T020, T023-T027 | Least privilege, unchanged existing resources, no implicit publication, approved access and rollback record. |

## 10. Completion definition

The handover is complete only when the customer can follow the published guide
from a clean checkout, using their own inputs and permissions, and the agreed
acceptance results are recorded. An infrastructure deployment alone, a moving
branch URL, or a successful demo using our local worktree is not sufficient.
