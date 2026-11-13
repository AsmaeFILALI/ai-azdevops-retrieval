# Customer deployment: private Azure DevOps Markdown POC

## What this profile delivers

Use the reviewed customer platform revision and its
[customer profile](../../samples/customer-poc/azd-env.example.json) and
[state-store parameters](../../samples/customer-poc/ingestion-state.parameters.example.json).
Do not assume upstream `main` contains fork-specific changes.
The deployment uses private classic Container Apps UI/orchestrator, Foundry IQ
`searchIndex`, externally published Markdown chunks, and separate private Blob
control state. It does not need Content Understanding, a Search Blob indexer,
conversation uploads, the bundled ingestion app or hosted Agent Service.

All platform deployment guidance for this profile is local:
[configuration](configuration.md), [private access](private-access.md) and
[application authentication](application-auth.md). Run commands from the
repository root. No separate documentation checkout or website build is needed.

The platform and runtime components are separate repositories. Obtain the UI
and orchestrator revisions pinned by [manifest.json](../../manifest.json) and
[app-definition.json](../../app-definition.json), plus a reviewed immutable
revision of the independent Markdown worker. Customer access to that worker,
its templates and the component source must be arranged separately. If only
this repository is accessible, see the [source-delivery blocker](README.md#documentation-is-local-application-source-is-still-separate).
Never copy a developer's dirty component checkout or registry credentials.

The customer branch selects runtime fixes from public forks:

| Component repository | Source branch | Required full commit |
| --- | --- | --- |
| `AsmaeFILALI/agent-app-ui` | `feature/customer-build-feeds` | `7ff09f49325d91018b2d443f993edf9b4cfd042d` |
| `AsmaeFILALI/agent-app-orchestrator` | `feature/citation-guard` | `a825e0bd2d0a7930da55a5ef9f7d20e2d4b036e2` |

These are reviewed source candidates, not newly published upstream releases.
Component tag fields are intentionally empty. The deployer uses the branch
to fetch source and verifies its full commit before building; moving a branch
to a different commit fails the pin check. Matching app-definition commits
are updated together with the manifest. Each fork records its genuine upstream
release repo/tag/commit separately for compatibility checks.

Initial candidate images at UI `132f70b` and orchestrator `7220406` passed
clean Linux/amd64 builds with a credential-free HTTPS mirror. The later
review fixes selected above pass focused regression/renderer and explicit
build-exclusion checks. Docker engine errors prevented rebuilding those latest
revisions and executing their synthetic layer-export checks during handover
validation. Run those tests and build the selected revisions on a working
customer runner. Publishing source does not update an Azure application.

## 1. Prerequisites and policy

Use Azure CLI, Azure Developer CLI, Git, PowerShell 7 or Bash with jq, and
Python 3.12. Local image builds require working Docker with Linux/amd64 support.
The worker requires its reviewed uv version, Python 3.12 and `uv.lock`.
Allow approved package/container registry and tokenizer-download egress during
dependency preparation. The platform hooks also bootstrap pip over HTTPS;
an entirely offline build path is not provided.

Before any writes, have administrators approve:

- Customer tenant/subscription and deployment principal **object ID**. An
  application/client ID is not a service-principal object ID.
- Resource deployment permissions and scoped role-assignment authority;
  configuration operations additionally need the relevant service data roles.
- Required provider registration, model/version/SKU capacity, Search semantic
  capabilities and subscription policy. ARM validation does not guarantee capacity.
- Ongoing VPN gateway, DNS resolver, NAT, private endpoint, database, model,
  Search and application costs.
- Primary/Search region Canada East and application Cosmos DB Canada Central,
  or a separately reviewed region selection.
- Model processing policy: the configured GlobalStandard chat SKU does
  **not** guarantee Canada-only inference.
- Preview API use. Embedding inference, Search schema administration, knowledge
  retrieval and ARM APIs have different versions; do not interchange them.

The retained address profile is:

| Purpose | Range |
| --- | --- |
| VNet | `10.77.0.0/21` |
| Agent / Container Apps | `10.77.0.0/24` / `10.77.1.0/24` |
| Private endpoints | `10.77.2.0/26` |
| Reserved Bastion / Firewall / Gateway | `10.77.2.64/26` / `10.77.2.128/26` / `10.77.2.192/26` |
| App Gateway / jumpbox / build agents | `10.77.3.0/27` / `10.77.3.64/27` / `10.77.3.96/27` |
| DNS resolver | `10.77.3.128/28` |
| VPN clients | `172.27.240.0/24` |

Reserved subnets do not imply those optional services are deployed. Keep these
ranges for this POC; check that customer connected networks do not overlap.
If there is a conflict, stop and request a separate network design change.

## 2. Prepare a new environment

Use the customer-accessible platform checkout at the exact handover revision.
Do not copy someone else's `.azure` directory. From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r .\config\requirements.txt
az login --tenant <customer-tenant>
az account set --subscription <customer-subscription>
azd auth login --tenant-id <customer-tenant>
```

In Bash, activate with `source .venv/bin/activate` and use native paths.
Confirm both tools target the customer context. Clear unrelated global Azure
CLI location filters; resource discovery must not hide services located outside
the primary region.

A separate clean checkout is recommended to rehearse customer delivery, but a
new azd environment in the same checkout is supported. Environments have
separate saved inputs/outputs; the root source, generated infrastructure
parameters and sibling component checkouts are shared. Do not deploy different
environments concurrently from that checkout. A separate clone needs a separate
parent directory to avoid reusing the same sibling component folders.

Copy the JSON profile to an ignored location and replace every placeholder:

```powershell
New-Item -ItemType Directory -Force .\.local | Out-Null
Copy-Item .\samples\customer-poc\azd-env.example.json .\.local\customer.json
```

Edit that local file before continuing. `inputs` contains nonsecret operator
choices; `bootstrap` and `connected` are mutually exclusive phase overlays.
Do not add generated service names, endpoints, secrets or old resource IDs.

```powershell
$profile = Get-Content -Raw .\.local\customer.json | ConvertFrom-Json
if (($profile | ConvertTo-Json -Depth 10) -match '<[^>]+>') {
    throw 'Replace every profile placeholder before creating an environment.'
}
azd env new $profile.inputs.AZURE_ENV_NAME --no-prompt
if ($LASTEXITCODE -ne 0) { throw 'Environment initialization failed.' }
foreach ($section in @($profile.inputs, $profile.bootstrap)) {
    foreach ($entry in $section.PSObject.Properties) {
        # Empty optional inputs use the Bicep fallback in this fresh environment.
        if ($entry.Value -eq '') { continue }
        azd env set $entry.Name $entry.Value --no-prompt
        if ($LASTEXITCODE -ne 0) { throw "Cannot set $($entry.Name)." }
    }
}
```

Fresh defaults are hosted orchestration/native Blob/standard schema, so the
explicit profile is essential. It selects `classic`, `maf_lite`, private
`searchIndex`, `ado_markdown_v1`, equal `SEARCH_RAG_INDEX_NAME` and
`FOUNDRY_IQ_SEARCH_INDEX_NAME`, and `semantic-config`. It disables optional
ingestion/uploads, hosted backing services, panel, jumpbox/Bastion/VM/firewall
and ACR Tasks pool while retaining NAT egress and local Docker builds.

`COSMOS_ACCOUNT_NAME` is empty for generated globally unique names. For an
**existing** environment, first set it to the actual selected account before
adopting the portable parameters, and review a no-replacement preview.
`DATABASE_ACCOUNT_NAME` is an output, not the override. Do not change database
identity as a retry shortcut.

## 3. Provision, connect, then complete service configuration

Review the selected [root parameters](../../main.parameters.json),
[application definition](../../app-definition.json) and foundation conditions
in [infra/main.bicep](../../infra/main.bicep). The
[pre-provision hook](../../scripts/preProvision.ps1) validates/binds the
application and resource destinations, resolves topology and generates
infrastructure parameters. Do not edit the generated file as the durable input.
Check permissions, regional model capacity and network policy before applying.

The bootstrap overlay deliberately defers post-provision data-plane setup
because the VPN does not exist yet:

```powershell
azd provision --no-prompt
```

Successful foundation provisioning with deferral is **not application readiness**.
No application image is built by that step. Keep public access disabled.
Do not replace this staged process with an unattended `azd up`: application
deployment requires the private connection and completed configuration.

Follow the local [private-access procedure](private-access.md) to read the
gateway/resolver outputs, add the resolver and service DNS suffixes to the
downloaded customer VPN profile, import/reconnect it and verify normal OS DNS,
private routing and TLS. The gateway download alone can have an empty
`clientconfig`; a successful direct-resolver query does not prove normal
applications use it. Do not copy our full VPN profile, resolver address or
private endpoint IPs.

After connecting, apply the connected overlay and run the matching hook:

```powershell
$profile = Get-Content -Raw .\.local\customer.json | ConvertFrom-Json
foreach ($entry in $profile.connected.PSObject.Properties) {
    azd env set $entry.Name $entry.Value --no-prompt
    if ($LASTEXITCODE -ne 0) { throw "Cannot set $($entry.Name)." }
}
pwsh -NoProfile -File .\scripts\postProvision.ps1
```

On Bash hosts use `bash ./scripts/postProvision.sh`. The hook configures roles,
governance/Key Vault, App Configuration, model/service references, the Markdown
index and knowledge objects. It can reconcile platform-owned objects: do not
run it against unrelated serving resources as a generic repair step.

Verify `AGENT_STRATEGY=maf_lite` and `CHAT_BACKEND=orchestrator` under `agent-lz`,
the exact index/model/vectorizer, `semantic-config`, and source-data projection
including `url`, `filepath`, `content`, `heading_path` and provenance. Environment
variables affect runtime only when explicitly published/read by the component.
See [index ownership](configuration.md#search-index-and-embedding-contract).

## 4. Configure authentication and deploy applications

Follow [application authentication](application-auth.md) for a customer-owned
single-tenant Entra web app, consent and allowed users. The canonical UI callback
is `<UI-HTTPS-origin>/auth/oauth/azure-ad/callback`. Configure OAuth client/tenant,
scopes, `CHAINLIT_URL` and a persistent session-signing secret. Credentials belong
in Key Vault through approved references, not this JSON profile.
Keep `ALLOW_ANONYMOUS=false`; VPN authentication is not application login.

From a connected build host:

```powershell
azd deploy --no-prompt
```

The parent deployment fetches the pinned components and checks tracked and
untracked source cleanliness before copying the environment or building.
Dirty component source fails without resetting files. Use a separate clean
checkout or review/commit changes first. Do not hide source edits with ignore flags.
The selected revisions exclude ignored local environment/configuration files
from their Docker contexts. Exclusions are not a general secret scanner.

For blocked package downloads, use the [approved local-build feed settings](configuration.md#local-image-builds)
rather than disabling TLS or putting credentials in Docker build arguments.
Verify both active revisions, recorded image digests, authenticated UI access,
orchestrator connectivity and a known-answer query. Container Apps provisioning
state alone does not establish application readiness.

## 5. Deploy the independent control-state store

The state store is **not automatically deployed by `azd provision` or `azd up`**.
Create/select the customer WIF publishing service principal with the
administrator before supplying `writerPrincipalId`. Copy and fill
[the native ARM parameter example](../../samples/customer-poc/ingestion-state.parameters.example.json)
in an ignored location such as `.local/state.parameters.json`.
Use the actual workload private-endpoint subnet and linked Blob private-DNS
zone ARM IDs. Defaults generate new account/resource-group names.

After preview review and explicit write approval:

```powershell
az deployment sub validate --location canadaeast --subscription <subscription> `
  --template-file .\infra\ingestion-state.bicep --parameters .\.local\state.parameters.json
az deployment sub what-if --location canadaeast --subscription <subscription> `
  --template-file .\infra\ingestion-state.bicep --parameters .\.local\state.parameters.json
az deployment sub create --name <state-deployment> --location canadaeast `
  --subscription <subscription> --template-file .\infra\ingestion-state.bicep `
  --parameters .\.local\state.parameters.json
```

The [state template](../../infra/ingestion-state.bicep) creates private LRS/Hot
storage with Shared Key/anonymous access disabled, versioning and 14-day
Blob/container soft delete. It is not Markdown staging or a Search indexer
source. The worker creates publisher/checkpoint/run blobs; infrastructure leaves
the container empty. Verify flags, Approved private endpoint, DNS record, exact
writer role and private authenticated access. Preserve identities on redeployment;
LRS is not a reviewed regional disaster-recovery strategy.

## 6. Export a reviewed worker handoff

Capture **full successful deployment snapshots**, not raw environment dumps:

```powershell
az deployment group show --subscription <subscription> --resource-group <app-rg> `
  --name <main-deployment> --output json > .\.local\main-deployment.json
az deployment sub show --subscription <subscription> --name <state-deployment> `
  --output json > .\.local\state-deployment.json
```

Render/read-back the customer index through the
[index-only command](../../config/search/markdown_index.py):

```powershell
python -m config.search.markdown_index `
  --search-endpoint https://<search-service>.search.windows.net `
  --index-name <explicit-index> `
  --embedding-endpoint https://<foundry-account>.openai.azure.com `
  --embedding-deployment text-embedding `
  --schema-output .\.local\customer-index.schema.json
```

Without `--apply` this command does not create or update an index. Transfer the
exact full schema and its independently reviewed SHA-256; a consumer requirements
JSON is not a deployable schema.

```powershell
python -m config.deployment.ingestion_handoff `
  --platform-deployment .\.local\main-deployment.json `
  --state-deployment .\.local\state-deployment.json `
  --platform-schema .\.local\customer-index.schema.json `
  --schema-sha256 <owner-reviewed-sha256> --index-name <explicit-index> `
  --serving-status <serving-or-non-serving> `
  --search-schema-api-version 2025-05-01-preview `
  --output .\.local\ingestion-handoff.json
```

This exporter is offline and allowlists bindings. It verifies successful
snapshots, environment/subscription/account consistency, embedding settings
and exact pinned schema. It refuses to overwrite inputs or existing outputs.
It does not prove live access, change an index, create admission or declare a
test target safe. `serving-status` is an explicit owner assertion, not an
inference from a name containing `test`. A serving target must match the main
deployment's recorded binding; verify current Azure bindings separately.

The `publishing` object maps to the worker publishing TOML, except that local
schema path, WIF client/service-connection IDs and admission remain owner inputs.
Use `embedding` for source model/deployment/dimensions. Ensure the actual
publishing principal has its own grants. Treat deployment snapshots as private
working evidence; only the allowlisted handoff is intended for transfer.
Review it under the customer's data policy.

## 7. Onboard the independent worker

Obtain the delivered worker's `docs/deployment.md`, `docs/operations.md`,
templates, configuration examples and identity tooling together with its code.
They are not files in this platform repository. Pin its template ref and full
commit. Arrange an approved delivery if the customer cannot access the worker
repository; do not treat this guide as a replacement for that implementation.

Prepare source repository ID, full ref, immutable commit and include/exclude
rules; platform schema/hash; owner admission; protected environment; and WIF
connection authorized only to the ingestion pipeline.
The worker needs selected-index document access, separate read-only schema
permission, OpenAI inference and exact container-scoped Blob permission.
Search's query-vectorizer identity also needs platform-managed embedding access.
Repository Build Service checkout permissions are separate.

Private publication requires an approved VNet-connected agent with private DNS.
A laptop VPN does not connect Microsoft-hosted agents. Start with
`enablePublishing=false`; validate the exact source offline. Only after owner
approval run first publication, verify checkpoints/documents, repeat unchanged
and verify no new embedding/document work. Rehearse interrupted-run recovery.
Never use an unsigned test waiver against an index already serving users.

## 8. Local development

Use separate clean component checkouts at the delivered pins, independent
Python 3.12 virtual environments and the component's documented dependencies.
On the connected workstation, sign into the customer tenant and arrange scoped
developer access to configuration, Key Vault and the required services. Managed
identity in Azure and local CLI credentials are separate authentication paths.

For the delivered upstream baseline, run from each component root:

```text
# UI: install requirements and the package using its Python development guide
uvicorn main:app --host 127.0.0.1 --port 8080
# Orchestrator: install its requirements in a separate environment
uvicorn main:app --app-dir src --host 127.0.0.1 --port 9000
```

Set `APP_CONFIG_ENDPOINT` explicitly for each process and follow component
instructions for runtime references. For local UI-to-orchestrator calls, review
the local URL/caller authentication settings rather than changing shared Azure
bindings. Configure the local OAuth callback/allowed origins and localhost
scheme according to the component's supported auth flow. Do not weaken the
deployed app or fabricate identity headers to make local chat work.

For worker-only development use `uv sync --locked --python 3.12 --group dev`,
prepare its verified tokenizer cache, then run `uv run --locked ado-ingest plan`
with the reviewed source TOML. `plan` is offline after dependencies/cache are
prepared. `sync`/`reconcile`/`rebuild` publish; they are not preview commands.
Customer-specific authenticated startup remains an acceptance check.

## Acceptance, troubleshooting and recovery

- Check a clean second checkout reproduces profile composition and builds.
- Verify public-network-disabled resources, normal private DNS/TLS and scoped
  runtime/worker permissions; a 403 can be networking or authorization.
- Confirm generated names, no accidental old POC accounts, exact image digests,
  completed configuration and persisted runtime strategy.
- Validate full schema, identical ingestion/query embeddings and source citations.
- Validate no-change ingestion and interruption recovery with synthetic content.
- Preserve content/state on failed setup; do not delete/recreate accounts/indexes.
- Restore compatible image/config/schema bindings deliberately. Do not run full
  hooks as destructive index repair or interpret Blob restore as Search rollback.

Azure DevOps permissions are not automatically copied into Search. Until an
approved permission contract and allow/deny tests pass, use synthetic or
explicitly admitted common-audience non-sensitive content only. Authentication,
private networking and fluent answers do not establish document authorization.

Before delivery record platform/component/worker commits, image digests,
documentation revision, schema/hash, nonsecret bindings, tested commands and
outstanding gates. Publication, a paid validation deployment and customer access
changes require separate authorization.
