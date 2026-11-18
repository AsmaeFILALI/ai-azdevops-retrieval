# Customer deployment: private Azure DevOps Markdown POC

## What this profile delivers

Use the reviewed customer platform revision and its
[customer profile](../../samples/customer-poc/azd-env.example.json).
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
revision of the independent Markdown worker from
`https://github.com/AsmaeFILALI/ado-index-worker` (see [step 7](azure-devops-markdown-poc.md#7-onboard-the-independent-worker)).
If only this repository is accessible, see the [source-delivery blocker](README.md#documentation-is-local-application-source-is-still-separate).
Never copy a developer's dirty component checkout or registry credentials.

The customer branch selects runtime fixes from public forks:

| Component repository | Source branch | Required full commit |
| --- | --- | --- |
| `AsmaeFILALI/agent-app-ui` | `feature/customer-build-feeds` | `7ff09f49325d91018b2d443f993edf9b4cfd042d` |
| `AsmaeFILALI/agent-app-orchestrator` | `feature/citation-guard` | `a825e0bd2d0a7930da55a5ef9f7d20e2d4b036e2` |

These are reviewed source candidates, not newly published upstream releases.
Component tag fields are intentionally empty. The **full commit is the pin**;
the branch only locates the repository. `azd deploy` clones the branch history,
requires the pinned commit to be part of it, and checks out exactly that
commit; it stops if the pin is missing from the branch. Matching app-definition
commits are updated together with the manifest. Each fork records its genuine
upstream release repo/tag/commit separately for compatibility checks.

> The UI branch `feature/customer-build-feeds` has since moved past its pin
> (a 2026-11-13 merge of later upstream UI releases, not validated with this
> profile). Deployment still builds the validated pinned commit `7ff09f4`. Do
> not move a pin to a newer branch commit without a separate review, rebuild
> and acceptance cycle.

### Delivered versions

| Part | Version delivered and validated |
| --- | --- |
| Platform (this repository) | The reviewed handover revision you received; `manifest.json` umbrella tag `v4.4.0` |
| Incorporated AI Landing Zone foundation | `bicep-ptn-aiml-landing-zone` `v2.7.3` (`97e2375b89dcda4900d75aac9e7ffb7b20cce165`) |
| UI | Commit `7ff09f49325d91018b2d443f993edf9b4cfd042d` (upstream base `v3.3.0`); image tag `frontend:7ff09f4` |
| Orchestrator | Commit `a825e0bd2d0a7930da55a5ef9f7d20e2d4b036e2` (upstream base `v5.2.1`); image tag `orchestrator:a825e0b` |
| Markdown worker | Delivered source: `ado-index-worker` commit `fdbf2b225b9a5042971b664cd0db12ef92688745`, package `ado-markdown-ingestion` `0.2.0` ([step 7](azure-devops-markdown-poc.md#host-and-pin-the-worker)) |

Image tags are the first seven characters of the source commit and are mutable
names; record the pushed image **digests** from your own build as the
deployment evidence.

### Validation status at handover

| Check | Result |
| --- | --- |
| Local Linux/amd64 builds of both selected revisions through credential-free corporate PyPI/npm mirrors | Passed |
| `azd deploy` to a private validation environment; both active revisions Healthy at the versions above; UI and orchestrator HTTPS checks | Passed |
| First knowledge-base retrieval | **Failed** until Search's outbound private links were approved ([step 3](azure-devops-markdown-poc.md#approve-search-outbound-access-to-the-embedding-model)) |
| Chat retrieval after approval | Passed in the validation environment (operator-confirmed) |
| Fresh component checkout when the UI branch has moved past its pin | Passed: deployment checks out the pinned commits `7ff09f4` and `a825e0b` (PowerShell and Bash hooks) |
| Customer environment: retrieval smoke tests, grounded answers with citations, worker publication/recovery, access-mode and allow/deny tests | Customer acceptance gates |

The retrieval failure surfaced in the orchestrator only as a generic HTTP 502.
Search's response body reported that the query vectorizer received HTTP 403
from the embedding endpoint. Publishing source does not update an Azure
application; rebuild and redeploy the selected revisions on the customer runner.

### Order of operations

Steps are grouped by topic; follow this order:

1. Obtain approvals and tools ([step 1](azure-devops-markdown-poc.md#1-prerequisites-and-policy)).
2. Create the worker's Azure DevOps service connection and resolve its
   service-principal object ID ([step 5, first part](azure-devops-markdown-poc.md#create-the-azure-devops-service-connection-before-provisioning));
   provisioning needs it.
3. Create the azd environment from the customer profile ([step 2](azure-devops-markdown-poc.md#2-prepare-a-new-environment)).
4. Provision, connect the VPN, then complete connected post-provisioning
   ([step 3](azure-devops-markdown-poc.md#3-provision-connect-then-complete-service-configuration)).
5. Approve Search's outbound private links and pass the retrieval smoke tests
   ([step 3](azure-devops-markdown-poc.md#approve-search-outbound-access-to-the-embedding-model)).
6. Choose the access mode, set package registries and run `azd deploy`
   ([step 4](azure-devops-markdown-poc.md#4-configure-authentication-and-deploy-applications)).
7. Verify the state writer role, then export the schema and worker handoff
   ([steps 5](azure-devops-markdown-poc.md#writer-roles-are-part-of-post-provision) and [6](azure-devops-markdown-poc.md#6-export-a-reviewed-worker-handoff)).
8. Provide the private publishing agent, run the worker identity script, onboard
   the worker, publish and rerun the smoke tests
   ([step 7](azure-devops-markdown-poc.md#7-onboard-the-independent-worker)).
9. Complete [acceptance](azure-devops-markdown-poc.md#acceptance-troubleshooting-and-recovery) and record versions and digests.

## 1. Prerequisites and policy

Use Azure CLI, Azure Developer CLI, Git, PowerShell 7 or Bash with jq 1.7+, and
Python 3.12. The Bash environment loader uses jq's `--binary` option to preserve
saved values on Windows; jq 1.6 does not support it.
Local image builds require working Docker with Linux/amd64 support.
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
- Approval, by an administrator of the Foundry account, of the Search service's
  outbound private-endpoint requests created during provisioning
  ([step 3](azure-devops-markdown-poc.md#approve-search-outbound-access-to-the-embedding-model)).
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

If public PyPI is blocked, first set the approved, credential-free HTTPS
Python index in this shell so the initial host dependency installation also
uses it. Replace the example with your own registry's **simple index** URL:

```powershell
$env:PIP_INDEX_URL = 'https://packages.example.com/repository/pypi/simple/'
```

In Bash use `export PIP_INDEX_URL='https://packages.example.com/repository/pypi/simple/'`.
Omit this optional step when using public PyPI. The host setting alone is not
a durable customer configuration; save the inputs below for subsequent hooks
and container builds.

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

Before provisioning, complete [the worker service connection](azure-devops-markdown-poc.md#5-integrated-control-state-store-and-worker-identity)
and obtain its service-principal object ID. Copy the JSON profile to an ignored
location and replace every placeholder, including
`INGESTION_STATE_WRITER_PRINCIPAL_ID`:

```powershell
New-Item -ItemType Directory -Force .\.local | Out-Null
Copy-Item .\samples\customer-poc\azd-env.example.json .\.local\customer.json
```

Edit that local file before continuing. `inputs` contains nonsecret operator
choices; `bootstrap` and `connected` are mutually exclusive phase overlays.
Do not add generated service names, endpoints, secrets or old resource IDs.
Optional `inputs.PIP_INDEX_URL` and `inputs.NPM_CONFIG_REGISTRY` select your
approved Python/npm registries; replace their empty values with your own
credential-free HTTPS endpoints if needed. Empty values in a **new**
environment preserve the package managers' defaults. Do not copy another
organization's registry addresses. Keep `BUILD_MODE=local` for these overrides.

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

The profile's `bootstrap` group contains initial azd settings that deliberately
defer private service configuration because the VPN does not exist yet.
"Overlay" means applying that group of saved settings to the selected environment,
not an automatic connection or infrastructure operation:

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

**After connecting the VPN and verifying normal private DNS, resume the service
configuration skipped during provisioning. Do this before application deployment,
not at the end.** Connecting the VPN does not update saved azd settings.

The profile's `connected` group changes `RUN_FROM_JUMPBOX` from `false` to `true`
and `AZURE_SKIP_NETWORK_ISOLATION_WARNING` from `true` to `false`. The first
setting has a misleading legacy name: your VPN-connected laptop is supported;
it does not create or require a jumpbox. The second clears the legacy warning-skip
deferral. Neither setting connects the VPN or bypasses connectivity checks.
Leaving the bootstrap values in place makes the hook defer again rather than
complete service setup.

With the intended customer environment selected, save the two values explicitly
and run the hook from the repository root:

```powershell
azd env set RUN_FROM_JUMPBOX true
if ($LASTEXITCODE -ne 0) { throw 'Cannot clear post-provision deferral.' }
azd env set AZURE_SKIP_NETWORK_ISOLATION_WARNING false
if ($LASTEXITCODE -ne 0) { throw 'Cannot clear legacy warning deferral.' }
pwsh -NoProfile -File .\scripts\postProvision.ps1
```

On Bash hosts set the same two azd values, checking each command succeeds, then
use `bash ./scripts/postProvision.sh`. The hook configures roles, governance/Key
Vault, App Configuration, model/service references, the Markdown index and
knowledge objects; it does not reprovision the entire infrastructure.
It can reconcile platform-owned objects: do not run it against unrelated serving
resources as a generic repair step.

Verify `AGENT_STRATEGY=maf_lite` and `CHAT_BACKEND=orchestrator` under `agent-lz`,
the exact index/model/vectorizer, `semantic-config`, and source-data projection
including `url`, `filepath`, `content`, `heading_path` and provenance. Environment
variables affect runtime only when explicitly published/read by the component.
See [index ownership](configuration.md#search-index-and-embedding-contract).

### Approve Search outbound access to the embedding model

Every user question is vectorized **by Azure AI Search**, using the index's
Azure OpenAI vectorizer and the Search system identity. With public access
disabled on the Foundry account, Search reaches it only through its own
outbound shared private links. Provisioning **creates these requests, but they
stay `Pending`** until a Foundry account administrator approves them. The
UI/orchestrator private endpoint being `Approved` does not cover this path,
and post-provisioning does **not** check these links for the `searchIndex`
profile. While a request is pending, every retrieval fails: the orchestrator
logs `Foundry IQ retrieve failed status=502`, and Search reports
`The vectorization endpoint returned status code '403' (Forbidden)`.

| Group ID (Search shared link) | Target | Purpose |
| --- | --- | --- |
| `openai_account` | Foundry account | Query-time vectorization; **required** for this profile |
| `foundry_account`, `cognitiveservices_account` | Foundry account | Other Foundry IQ model calls |
| `blob` | Application document storage | Native Blob indexing; not used by this profile |

List both sides of each request. These are management-plane reads; the VPN is
needed only for the App Configuration lookup:

```powershell
$ErrorActionPreference = 'Stop'
$rawEnvironment = & azd env get-values --output json
if ($LASTEXITCODE -ne 0) { throw 'Cannot load the selected azd environment.' }
$azdEnvironment = ($rawEnvironment -join "`n") | ConvertFrom-Json -AsHashtable

function Get-PlatformSetting([string]$Key) {
    $raw = & az appconfig kv show `
        --endpoint $azdEnvironment.APP_CONFIG_ENDPOINT `
        --subscription $azdEnvironment.AZURE_SUBSCRIPTION_ID `
        --key $Key --label agent-lz --auth-mode login `
        --query value --output tsv --only-show-errors
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace(($raw -join "`n"))) {
        throw "Cannot read required App Configuration setting $Key."
    }
    return ($raw -join "`n").Trim()
}

$searchId = Get-PlatformSetting 'SEARCH_SERVICE_RESOURCE_ID'
$foundryId = Get-PlatformSetting 'AI_FOUNDRY_ACCOUNT_RESOURCE_ID'

# Search side: deployment-owned outbound requests.
az rest --method get `
    --url "https://management.azure.com$searchId/sharedPrivateLinkResources?api-version=2025-05-01" `
    --query "value[].{name:name, groupId:properties.groupId, status:properties.status, state:properties.provisioningState}" `
    --output table
if ($LASTEXITCODE -ne 0) { throw 'Cannot read Search shared private links.' }

# Target side: connections waiting on the Foundry account.
az network private-endpoint-connection list --id $foundryId `
    --query "[].{id:id, status:properties.privateLinkServiceConnectionState.status, description:properties.privateLinkServiceConnectionState.description}" `
    --output table
if ($LASTEXITCODE -ne 0) { throw 'Cannot read Foundry private endpoint connections.' }
```

A Foundry account administrator then approves the `openai_account` request,
plus any other listed request the network owner accepts. Approve only a
`Pending` connection whose name matches the exact Search shared-link name above
(for example `spl-<search-service>-openai_account-1.<guid>`) and whose
description is the deployment's request message. Never approve unknown
requests or approve by prefix alone. Approval needs
`Microsoft.CognitiveServices/accounts/privateEndpointConnectionsApproval/action`
on the account; the portal path is **Foundry account > Networking > Private
endpoint connections**. The equivalent command is:

```powershell
az network private-endpoint-connection approve `
    --id '<exact-pending-connection-id-from-the-list>' `
    --description 'Approved: Search query vectorization for <environment>'
```

Rerun the Search-side list until each approved link reports `Approved` and
`Succeeded`; propagation can take several minutes. Keep Foundry public network
access disabled. Do not use API keys or open public access as a workaround.
Rejected or failed links must be investigated, not recreated by prefix.

Then run both smoke tests from the VPN-connected host, in the same shell. They
print only counts, never document content. The deployer identity needs Search
index read access.

```powershell
$searchEndpoint = (Get-PlatformSetting 'SEARCH_SERVICE_QUERY_ENDPOINT').TrimEnd('/')
$foundryIqApi = Get-PlatformSetting 'FOUNDRY_IQ_API_VERSION'
$indexName = $azdEnvironment.SEARCH_RAG_INDEX_NAME
$knowledgeBase = $azdEnvironment.KNOWLEDGE_BASE_NAME
$knowledgeSource = $azdEnvironment.FOUNDRY_IQ_KNOWLEDGE_SOURCE_NAME
$bodyPath = Join-Path ([IO.Path]::GetTempPath()) "agentlz-smoke-$([guid]::NewGuid().ToString('N')).json"
try {
    # 1. Query-time vectorization through the Search shared private link.
    '{"vectorQueries":[{"kind":"text","text":"connectivity check","fields":"contentVector","k":1}],"select":"id","top":1}' |
        Set-Content -LiteralPath $bodyPath -Encoding utf8NoBOM
    az rest --method post --resource https://search.azure.com `
        --url "$searchEndpoint/indexes/$indexName/docs/search?api-version=2025-05-01-preview" `
        --headers Content-Type=application/json --body "@$bodyPath" `
        --query '{returned: length(value || `[]`)}'
    if ($LASTEXITCODE -ne 0) { throw 'Vector query failed; check shared-link approval and the Search identity''s model access.' }

    # 2. The same knowledge-base retrieve request the orchestrator sends.
    (@{
        intents = @(@{ search = 'connectivity check'; type = 'semantic' })
        knowledgeSourceParams = @(@{
            knowledgeSourceName = $knowledgeSource; kind = 'searchIndex'
            includeReferences = $true; includeReferenceSourceData = $false
        })
    } | ConvertTo-Json -Depth 5) | Set-Content -LiteralPath $bodyPath -Encoding utf8NoBOM
    az rest --method post --resource https://search.azure.com `
        --url "$searchEndpoint/knowledgebases/$knowledgeBase/retrieve?api-version=$foundryIqApi" `
        --headers Content-Type=application/json --body "@$bodyPath" `
        --query '{references: length(references || `[]`), failedSources: length((activity || `[]`)[?error])}'
    if ($LASTEXITCODE -ne 0) { throw 'Knowledge-base retrieve failed; Search returns the failing source in its error body.' }
} finally {
    Remove-Item -LiteralPath $bodyPath -Force -ErrorAction SilentlyContinue
}
```

Both commands must succeed with `failedSources: 0`. Zero results are expected
before the worker's first publication; repeat both checks afterwards, because
an empty index does not prove relevance or citations. If vectorization still
returns 403 after `Approved`/`Succeeded`, check that the Search system identity
has **Cognitive Services OpenAI User** (or an equivalent role) on the Foundry
account, then review Microsoft's current Foundry IQ private-outbound guidance
with the network owner. Do not enable public access to work around it.

## 4. Configure authentication and deploy applications

### Choose the application access mode

The POC **defaults to anonymous access** inside the private network. Users with
access to the customer VPN can chat without signing in. Authenticated
Entra sign-in is an opt-in mode. The decision is a runtime App Configuration
setting under label `agent-lz`; `azd env set ALLOW_ANONYMOUS ...` on its own
changes nothing, because the platform does not publish that key.

| | Anonymous (default) | Authenticated (opt-in) |
| --- | --- | --- |
| Who can chat | Anyone who can reach the private UI through the VPN | Signed-in customer-tenant users, optionally restricted by allowed-user lists |
| `ALLOW_ANONYMOUS` (App Configuration, `agent-lz`) | `true` | `false` |
| `OAUTH_AZURE_AD_*`, `CHAINLIT_AUTH_SECRET` | **Must stay unset** | Required; see [application authentication](application-auth.md) |
| Retrieval identity | Service identity only; every user can retrieve all indexed content | Service identity plus the user's forwarded token; the index has no permission filter, so results are not trimmed per document |
| Conversation history | Not tied to a person | Per signed-in user |

The pinned UI enables sign-in whenever OAuth client ID, tenant ID and client
secret are all configured, **even if `ALLOW_ANONYMOUS=true`**. To stay
anonymous, do not publish OAuth settings. With `ALLOW_ANONYMOUS=false` and no
OAuth configuration, the UI starts in an "authentication required" mode that
answers HTTP 503. In both modes the VPN, not the application, is the network
boundary, and both modes are limited to the approved common-audience content
described under [acceptance](azure-devops-markdown-poc.md#acceptance-troubleshooting-and-recovery).

For the default anonymous mode, record the decision explicitly so a later
change is deliberate:

```powershell
$appConfigEndpoint = (& azd env get-values --output json | ConvertFrom-Json).APP_CONFIG_ENDPOINT
az appconfig kv set --endpoint $appConfigEndpoint --auth-mode login `
    --key ALLOW_ANONYMOUS --value true --label agent-lz --yes
if ($LASTEXITCODE -ne 0) { throw 'Cannot publish the application access mode.' }
```

For authenticated mode, follow [application authentication](application-auth.md)
for the customer-owned single-tenant Entra web app, consent and allowed users,
then publish `ALLOW_ANONYMOUS=false` the same way. The canonical UI callback
is `<UI-HTTPS-origin>/auth/oauth/azure-ad/callback`. Credentials belong in Key
Vault through approved references, not the JSON profile.

Both applications read this setting at startup. When changing modes on running
applications, restart both active revisions (portal: **Container App >
Revisions and replicas > Restart**) or rerun `azd deploy`, then verify the
expected behavior in a fresh browser session. VPN authentication is not
application login.

### Configure package registries before building

The customer profile supports the following build-time settings, saved in the
**selected root azd environment**, not Azure App Configuration:

| Setting | Used by | Default when unset |
| --- | --- | --- |
| `PIP_INDEX_URL` | UI and orchestrator Python image dependencies; platform host pip installs | Package manager configuration, normally `https://pypi.org/simple` |
| `NPM_CONFIG_REGISTRY` | Orchestrator dashboard frontend dependencies | npm configuration, normally `https://registry.npmjs.org/` |
| `BUILD_MODE` | Both component deployers | This customer profile explicitly selects `local` |

For an existing environment, or instead of editing the profile before its
initial import, save your own endpoints from the repository root:

```powershell
azd env set BUILD_MODE local
if ($LASTEXITCODE -ne 0) { throw 'Cannot select local image builds.' }
azd env set PIP_INDEX_URL 'https://packages.example.com/repository/pypi/simple/'
if ($LASTEXITCODE -ne 0) { throw 'Cannot save Python package registry.' }
azd env set NPM_CONFIG_REGISTRY 'https://packages.example.com/repository/npm/'
if ($LASTEXITCODE -ne 0) { throw 'Cannot save npm package registry.' }
```

These `azd env set` commands also work in Bash; check their exit status there.
The addresses are examples, not this project's or a customer's actual feeds.
If the profile was already imported, editing its JSON alone does not update
the selected environment. Use the commands above or explicitly reimport the
changed inputs.

The parent hook loads saved settings and passes them to the clean, pinned
component deployers. Local Docker builds receive the Python index in both
images and the npm registry in the orchestrator frontend stage. Registry
overrides do not change dependency versions or runtime configuration.
The pinned components do not forward these overrides to ACR Task builds:
the parent now stops rather than silently ignoring a configured registry when
`BUILD_MODE` is not explicitly `local`. Healthy local Linux/amd64 Docker and
access to the private ACR are required; there is no remote-build fallback for
this configuration. No component source edits or pin changes are needed.

Only credential-free HTTPS URLs without user information, query strings or
fragments are supported. Do not embed usernames, passwords or tokens in these
values, `.env` files, Docker build arguments or source. Authenticated registries
need a separately reviewed build-secret path; these inputs do not implement
registry authentication. Install approved corporate CA trust on both the host
and build images when required; do not disable pip/npm TLS verification.

The reported `files.pythonhosted.org` TLS handshake failure occurred inside
the UI image build. Changing the host's pip configuration alone does not
configure that image. The approved Python feed must serve/proxy **artifacts as
well as the index**; an index that redirects wheels to blocked public hosts
still fails. Likewise, check npm tarball URLs in the lockfile when using a
mirror. These settings do not redirect base images, Debian/Microsoft package
feeds, the platform's `bootstrap.pypa.io` pip bootstrap or tokenizer downloads;
their egress is still required. They also do not configure the independent
Markdown worker.

To return to public/default package manager configuration:

```powershell
azd env unset PIP_INDEX_URL --force
if ($LASTEXITCODE -ne 0) { throw 'Cannot remove Python registry override.' }
azd env unset NPM_CONFIG_REGISTRY --force
if ($LASTEXITCODE -ne 0) { throw 'Cannot remove npm registry override.' }
Remove-Item Env:PIP_INDEX_URL, Env:NPM_CONFIG_REGISTRY -ErrorAction SilentlyContinue
```

In Bash clear inherited overrides with `unset PIP_INDEX_URL NPM_CONFIG_REGISTRY`
after the same `azd env unset` commands. Remove matching values from the local
profile if it will be imported again. Also check host pip/npm configuration
files and any `PIP_EXTRA_INDEX_URL` before assuming public or mirror-only access.

### Component checkouts

`azd deploy` builds the UI and orchestrator from sibling folders next to this
repository (`..\agent-app-ui`, `..\agent-app-orchestrator`). When a folder is
missing, it clones the repository and checks out the **exact pinned commit**
(a detached checkout is expected). When a folder already exists, it builds it
only if that folder is a clean checkout of the pinned commit; it never resets
or switches an existing folder. If deployment reports that a component "must
resolve to" its pin, move that folder aside (do not discard someone's work)
and rerun `azd deploy`. The bundled ingestion component is not deployed by this
profile.

### Build or retry application deployment

From a connected build host, after saving any registry overrides:

```powershell
azd deploy --no-prompt
```

The parent deployment fetches the pinned components and checks tracked and
untracked source cleanliness before copying the environment or building.
Dirty component source fails without resetting files. Use a separate clean
checkout or review/commit changes first. Do not hide source edits with ignore flags.
The selected revisions exclude ignored local environment/configuration files
from their Docker contexts. Exclusions are not a general secret scanner.

After a package-download failure, correct the settings above and rerun
`azd deploy`; registry changes do not require another `azd provision`.
See also the [local-build constraints](configuration.md#local-image-builds).
Verify both active revisions, recorded image digests, UI access in the selected
[access mode](azure-devops-markdown-poc.md#choose-the-application-access-mode), orchestrator connectivity
and a known-answer query after the
[retrieval smoke tests](azure-devops-markdown-poc.md#approve-search-outbound-access-to-the-embedding-model)
pass. Container Apps provisioning state alone does not establish application
readiness.

## 5. Integrated control-state store and worker identity

The customer profile enables `DEPLOY_INGESTION_STATE_STORE=true`.
`azd provision` creates the dedicated account, private container and Blob private
endpoint **in the main application resource group**, not a new ingestion group.
It reuses the deployment's endpoint subnet and Blob DNS configuration, including
the policy-managed DNS mode. General deployments keep this feature disabled
unless explicitly selected. No separate state parameter file or
`az deployment sub create` command is required.

The [storage module](../../infra/modules/storage/ingestion-control-state.bicep)
keeps private LRS/Hot storage, Entra-only access, versioning and 14-day
Blob/container soft delete. Infrastructure creates an empty container, never
Markdown staging, a Search indexer or worker checkpoint blobs. LRS is not a
reviewed regional disaster-recovery strategy.

### Create the Azure DevOps service connection before provisioning

Use a dedicated publishing identity approved by the tenant administrator.
Do not reuse the UI, orchestrator, Search or deployment identity.

1. In the Azure portal, open **Microsoft Entra ID > App registrations** and
   create or select the worker's single-tenant app registration. Record its
   **Application (client) ID** and **Directory (tenant) ID**. An administrator
   must allow app registration and federated credential management.
2. Ensure the corresponding enterprise application/service principal exists.
   For a newly approved registration only, an administrator can create it with
   `az ad sp create --id <application-client-id>`. Do not create a client secret.
3. In Azure DevOps, open **Project settings > Service connections > New service
   connection > Azure Resource Manager**. Select the manual/existing app
   registration option and **Workload identity federation**. Enter the customer
   subscription, tenant and **application/client ID**. Choose a stable service
   connection name. Authorize only the intended publishing pipeline, not all
   pipelines. Save it as a draft if identity verification is not ready.
4. Copy the exact **Issuer** and **Subject identifier** generated by Azure
   DevOps. In the app registration's **Certificates & secrets > Federated
   credentials**, add the federation for this service connection using those
   values and audience `api://AzureADTokenExchange`. Do not construct the
   issuer/subject from memory; the values depend on the connection.
5. Return to Azure DevOps and save/verify the connection after federation and
   its approved Azure permissions are in place. If verification requires an
   ARM read grant, have an administrator grant only the reviewed scope. This
   state-store feature grants no Contributor, Search or inference permissions.

The state writer input is the **service-principal object ID** of that enterprise
application, **not** the service-connection ID, application/client ID, app
registration object ID, tenant ID or deployer's `AZURE_PRINCIPAL_ID`.
Resolve it from the service connection's application/client ID while signed
into the correct tenant:

```powershell
$workerClientId = '<service-connection-application-client-id>'
$writerId = az ad sp show --id $workerClientId --query id --output tsv
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($writerId)) {
    throw 'Cannot resolve the worker service-principal object ID in this tenant.'
}
$writerId = $writerId.Trim()
$verifiedWriter = az ad sp show --id $writerId --query id --output tsv
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($verifiedWriter) -or $verifiedWriter.Trim() -ine $writerId) {
    throw 'Worker object ID verification failed.'
}
```

For a **new** environment, put that value in the ignored customer profile's
`INGESTION_STATE_WRITER_PRINCIPAL_ID` placeholder before applying step 2.
For an **existing selected** environment, save the inputs before the next
provision:

```powershell
azd env set DEPLOY_INGESTION_STATE_STORE true
azd env set INGESTION_STATE_WRITER_PRINCIPAL_ID $writerId
# Refresh generated parameters through the normal pre-provision hook before preview.
azd hooks run preprovision --no-prompt
azd provision --preview
# Review the preview before applying:
azd provision --no-prompt
```

Optional inputs are `INGESTION_STATE_STORAGE_ACCOUNT_NAME` (stable custom
account name), `INGESTION_STATE_CONTAINER_NAME` (default `ingestion-state`) and
`INGESTION_STATE_SOFT_DELETE_RETENTION_DAYS` (default `14`, range `1..365`).
These are nonsecret azd operator inputs, not application runtime settings.
There is no separate resource-group override in the integrated path.

### Writer roles are part of post-provision

Both platform hooks validate the approved service-principal object ID before
provisioning. During connected post-provision, the
[state configuration module](../../config/deployment/ingestion_state.py) reads
the successful `ingestionControlState` deployment, verifies the exact account
and container, then idempotently grants **Storage Blob Data Contributor at the
container scope only** to that writer. It never substitutes the deployer.
Application capability roles explicitly exclude the state account.

Bootstrap deferral also defers this writer grant. Complete the connected phase
in step 3; rerunning the normal hook reconciles it without a separate role
assignment command:

```powershell
azd hooks run postprovision --no-prompt
```

Verify the account security flags, Approved private endpoint, private DNS,
exact writer grant and authenticated Blob access from the publishing agent.
The deployment principal needs role-assignment authority at that container
(or an authorized ancestor), management-plane reads and permission to read the
approved Entra service principal. State access alone does not grant the worker
Search schema-read/document-write, embedding inference or repository access.
The worker's identity script grants those after provisioning
([step 7](azure-devops-markdown-poc.md#map-platform-values-into-the-worker-configuration)).

If a standalone state store already contains checkpoints in another resource
group, stop and review migration before enabling this path. No account is moved,
copied or deleted automatically, and changing the store can lose publication
coordination. Do not generate a second store as a retry shortcut. Preserve the
approved name/container, freeze the worker for any migration, and validate its
recovery protocol before resuming.

## 6. Export a reviewed worker handoff

Capture **full successful deployment snapshots**, not raw environment dumps.
`azd provision` names the main deployment after the environment followed by a
number (for example `<environment>-1794597765`); look up the latest successful
one first:

```powershell
$environment = '<environment>'
$deployments = az deployment group list --subscription <subscription> --resource-group <app-rg> --output json | ConvertFrom-Json
if ($LASTEXITCODE -ne 0) { throw 'Cannot list deployments.' }
$mainDeployment = ($deployments |
  Where-Object { $_.name -match "^$([regex]::Escape($environment))-\d+$" -and $_.properties.provisioningState -eq 'Succeeded' } |
  Sort-Object { [datetime]$_.properties.timestamp } | Select-Object -Last 1).name
if ([string]::IsNullOrWhiteSpace($mainDeployment)) { throw 'Main deployment not found.' }
az deployment group show --subscription <subscription> --resource-group <app-rg> `
  --name $mainDeployment --output json > .\.local\main-deployment.json
az deployment group show --subscription <subscription> --resource-group <app-rg> `
  --name ingestionControlState `
  --output json > .\.local\state-deployment.json
```

The second snapshot is the nested group deployment automatically created by
`azd provision`, not a separately provisioned store. Reading its outputs avoids
changing the root template's existing 64-output contract. Confirm the connected
post-provision writer grant separately; a successful ARM snapshot is not proof
of worker access.

### Generate the ingestion index schema from the azd environment

Give the ingestion pipeline the **full rendered index schema** and its
SHA-256 file, not the [consumer requirements contract](../../contracts/ado-markdown-index-consumer-v1.json)
or the unrendered [platform template](../../config/search/rag-index.j2).
The template is authoritative; the rendered JSON includes the actual index
name, fields, vector dimensions, semantic configuration and embedding binding.

Run this PowerShell 7 block from the repository root with the intended azd
environment selected, Azure CLI signed in and the customer VPN connected.
It reads the selected environment through `azd env get-values`, rather than
executing or printing the `.env` file. The environment supplies the index name
and App Configuration endpoint; Search and embedding endpoints are read from
that environment's published settings under label `agent-lz`. No credentials
or unrelated environment values are exported.

```powershell
$ErrorActionPreference = 'Stop'
$rawEnvironment = & azd env get-values --output json
if ($LASTEXITCODE -ne 0) { throw 'Cannot load the selected azd environment.' }
$azdEnvironment = ($rawEnvironment -join "`n") | ConvertFrom-Json -AsHashtable
if ($azdEnvironment -isnot [System.Collections.IDictionary]) {
    throw 'Expected an azd environment object.'
}
foreach ($key in @(
    'AZURE_ENV_NAME', 'AZURE_SUBSCRIPTION_ID', 'APP_CONFIG_ENDPOINT',
    'SEARCH_RAG_SCHEMA', 'SEARCH_RAG_INDEX_NAME', 'FOUNDRY_IQ_SEARCH_INDEX_NAME'
)) {
    if ([string]::IsNullOrWhiteSpace($azdEnvironment[$key])) {
        throw "Missing $key in the selected azd environment."
    }
}
if ($azdEnvironment.AZURE_ENV_NAME -notmatch '^[A-Za-z0-9_-]+$') {
    throw 'Environment name cannot be used as an export filename.'
}
if ($azdEnvironment.SEARCH_RAG_SCHEMA -ne 'ado_markdown_v1' -or
    $azdEnvironment.SEARCH_RAG_INDEX_NAME -ne $azdEnvironment.FOUNDRY_IQ_SEARCH_INDEX_NAME) {
    throw 'Expected the Markdown schema and matching Search/Foundry IQ index names.'
}

function Get-IndexExportSetting([string]$Key) {
    $raw = & az appconfig kv show `
        --endpoint $azdEnvironment.APP_CONFIG_ENDPOINT `
        --subscription $azdEnvironment.AZURE_SUBSCRIPTION_ID `
        --key $Key --label agent-lz --auth-mode login `
        --query value --output tsv --only-show-errors
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace(($raw -join "`n"))) {
        throw "Cannot read required App Configuration setting $Key."
    }
    return ($raw -join "`n").Trim()
}

$searchEndpoint = Get-IndexExportSetting 'SEARCH_SERVICE_QUERY_ENDPOINT'
$modelDeployments = (Get-IndexExportSetting 'MODEL_DEPLOYMENTS') | ConvertFrom-Json
$embedding = @($modelDeployments | Where-Object {
    $_.canonical_name -eq 'EMBEDDING_DEPLOYMENT_NAME'
})
if ($embedding.Count -ne 1 -or
    $embedding[0].model.name -ne 'text-embedding-3-large' -or
    [string]::IsNullOrWhiteSpace($embedding[0].endpoint) -or
    [string]::IsNullOrWhiteSpace($embedding[0].name)) {
    throw 'Expected one explicit text-embedding-3-large deployment and endpoint.'
}

New-Item -ItemType Directory -Force .\.local | Out-Null
$schemaPath = ".\.local\$($azdEnvironment.AZURE_ENV_NAME)-index.schema.json"
if ((Test-Path -LiteralPath $schemaPath) -or
    (Test-Path -LiteralPath "$schemaPath.sha256")) {
    throw 'An export already exists. Review it and choose a new schemaPath before rerunning.'
}
python -m config.search.markdown_index `
    --search-endpoint $searchEndpoint `
    --index-name $azdEnvironment.SEARCH_RAG_INDEX_NAME `
    --embedding-endpoint $embedding[0].endpoint `
    --embedding-deployment $embedding[0].name `
    --schema-output $schemaPath
if ($LASTEXITCODE -ne 0) {
    throw 'Schema export/read-back failed. Any generated files are not validated for handoff.'
}
Get-FileHash -LiteralPath $schemaPath -Algorithm SHA256
Get-Content -LiteralPath "$schemaPath.sha256"
```

For an environment named `customer-preflight`, the pipeline inputs are:

- `.local/customer-preflight-index.schema.json`: the full index schema.
- `.local/customer-preflight-index.schema.json.sha256`: the SHA-256 of those
  exact JSON bytes. Do not reformat the JSON after reviewing the checksum.

The [index-only command](../../config/search/markdown_index.py) renders locally
and reads back an existing index to check compatibility. Without `--apply` it
does not create, update or delete an index. If the index is missing, it only
plans creation; that is not proof of a deployed publishing target. It writes
the files **before** live validation, so file existence alone is not success:
do not hand off files after a failed command. Resolve VPN, permissions or schema
mismatches first; do not delete/recreate an existing index as a retry shortcut.

Keep the exports local and transfer only the reviewed schema/checksum and
allowlisted handoff through the customer's approved artifact process. Never
give the pipeline the `.env` file or raw deployment snapshots. The schema
does not provision the pipeline, grant access or authorize publication.

After independently reviewing the full schema and checksum, continue with the
handoff exporter in the same shell (`$schemaPath` is set above):

```powershell
python -m config.deployment.ingestion_handoff `
  --platform-deployment .\.local\main-deployment.json `
  --state-deployment .\.local\state-deployment.json `
  --platform-schema $schemaPath `
  --schema-sha256 <owner-reviewed-sha256> --index-name $azdEnvironment.SEARCH_RAG_INDEX_NAME `
  --serving-status serving `
  --search-schema-api-version 2025-05-01-preview `
  --output .\.local\ingestion-handoff.json
```

Use `serving` for this profile: the knowledge base and chat application query
this index directly, and the exporter refuses `non-serving` for an index the
main deployment binds. Use `<owner-reviewed-sha256>` from the `.sha256` file
reviewed above.

This exporter is offline and allowlists bindings. It verifies successful
snapshots, environment/subscription/account consistency, embedding settings
and exact pinned schema. It refuses to overwrite inputs or existing outputs.
It does not prove live access, change an index or authorize publication.
`serving-status` is an explicit owner assertion, not an inference from a name
containing `test`. Verify current Azure bindings separately.

Treat deployment snapshots as private working evidence; only the allowlisted
handoff is intended for transfer. Review it under the customer's data policy.
[Step 7](azure-devops-markdown-poc.md#map-platform-values-into-the-worker-configuration)
maps each handoff value into the worker's files.

## 7. Onboard the independent worker

The worker publishes your Markdown into the index. It comes from its own public
repository, `https://github.com/AsmaeFILALI/ado-index-worker`, and its
`docs/deployment.md` is the step-by-step guide. Follow it, with the decisions
and values below. They replace the choices that guide leaves open, so the two
guides agree.

### Decisions for this POC

| Topic | This POC | Worker guide reference |
| --- | --- | --- |
| Approval | **Waiver only.** Set `admission_waiver` to a recorded owner decision. Do not create admission files or their secure files. Admission can be added later | Steps 5.4 and 5.6 |
| Target index | The serving `kb-sections-v1` index that chat uses (see the note below) | Step 1 |
| Content | Synthetic or explicitly approved common-audience content only | Step 1 |
| Network | Private-only Search, OpenAI and Storage: **self-hosted agent required** for publishing | Steps 1 and 4.3 |
| Worker pin | Optional for the POC; pin before real content | Step 7 |
| Service connection | Create it once, in [step 5](azure-devops-markdown-poc.md#create-the-azure-devops-service-connection-before-provisioning) here; **skip the worker guide's Step 3.1** | Step 3 |

> **Waiver on the serving index.** The worker guide describes the waiver for a
> *non-serving* test index. In this POC the same index also serves chat, so
> the waiver is used under an explicit owner decision with these conditions:
> the content is synthetic or approved for every user who can reach the
> application (in anonymous mode, everyone on the VPN), there are no
> production users, and no document permissions are claimed. Record the
> decision in the waiver text, for example
> `"POC owner decision <date>: serving POC index, common-audience content only, no permissions claimed"`.
> The waiver also refuses a first publication over documents that already
> exist for the same repository and branch; publish each source into an index
> that has none of its documents yet. Before
> real or restricted content or production users, replace the waiver with an
> admission (worker `docs/operations.md` section 4).

### Host and pin the worker

Worker guide Step 2 imports the code into a repository in the **customer's**
Azure DevOps project. Import the delivered source revision: commit
`fdbf2b225b9a5042971b664cd0db12ef92688745`, package `ado-markdown-ingestion`
`0.2.0`. Record it as the delivered source; it is not the pipeline pin.
Step 5 then adds `config/<name>/` to that repository, which creates a new
commit there. Any pin (worker guide Step 7: a tag such as `v0.2.0` plus
`workerCommit`) refers to that **customer repository** commit, not to the
GitHub commit. For the POC the pipeline may track `main` unpinned; protect
`main` with required review.

### Map platform values into the worker configuration

| Worker value | Take it from | Note |
| --- | --- | --- |
| `search_endpoint`, `index_name`, `embedding_endpoint`, `openai_api_version`, `state_account_url`, `state_container`, `schema_sha256` (worker Step 5.4) | `publishing` in `.local\ingestion-handoff.json` ([step 6](azure-devops-markdown-poc.md#6-export-a-reviewed-worker-handoff)) | Copy exactly. `embedding_endpoint` has no trailing slash and must equal the schema's vectorizer `resourceUri`; do not copy the endpoint from App Configuration |
| `search_schema_api_version` | `publishing.search_schema_api_version`: `2025-05-01-preview` | **Not** the worker example's `2025-09-01`. The platform schema uses preview permission properties; a stable version fails with "Deployed schema differs" |
| `deployment`, `model`, `dimensions` (worker Step 5.3) | `embedding` in the handoff | `text-embedding`, `text-embedding-3-large`, `3072` |
| Schema file `config/<name>/<index>.schema.json` (worker Step 5.5) | The exported `.local/<environment>-index.schema.json` | Copy the bytes unchanged (LF). The worker recomputes the same SHA-256 |
| `tenant_id`, `client_id`, `service_connection_id` | The service connection from step 5 | Look them up as in worker Step 8.2 |
| `admission_waiver` | The recorded owner decision above | 20+ characters, not the template placeholder |

Then run the worker's identity script (worker Steps 3.2 and 3.3) **after
provisioning**, from the worker repository, with these values:

| Script parameter | Value |
| --- | --- |
| `TenantId`, `SubscriptionId` | `tenant_id` and `subscription_id` in the handoff |
| `SearchServiceResourceId` | App Configuration key `SEARCH_SERVICE_RESOURCE_ID` (label `agent-lz`) |
| `IndexName` | `publishing.index_name` |
| `OpenAIResourceId` | `resources.openai_resource_id` in the handoff (the Foundry account) |
| `StateContainerResourceId` | `resources.state_container_resource_id` in the handoff |
| `ExistingAppId` | The service connection's application (client) ID from step 5 |

Run it in preview first, then with `-Apply`. It grants the index, model and
schema-reader roles; its container role duplicates the grant that platform
post-provisioning already made, which is harmless. The script creates a custom
role on the Search resource group, so it needs an administrator with
role-definition and role-assignment rights there.

### Provide the private publishing agent

Publishing must run on a self-hosted Azure DevOps agent that resolves the
private endpoints and reaches them on port 443 (worker Step 4.3). Microsoft-hosted
agents cannot reach them, and your laptop's VPN does not extend to them. For
short POC runs, a self-hosted agent on a machine connected to the
[point-to-site VPN with private DNS](private-access.md#prepare-windows-split-dns-settings)
works while that machine stays connected. For anything sustained, the platform reserves
`devops-build-agents-subnet` (`10.77.3.96/27`) in the workload VNet for this,
but **does not deploy an agent**. A VM in that subnet resolves private
endpoints through the VNet's linked private DNS zones.

The agent also needs outbound HTTPS to Azure DevOps, Microsoft Entra ID and its
package/tokenizer sources (or the worker's offline `toolchain: local`). In the
validated deployment, the NAT gateway is attached only to `jumpbox-subnet` and
`aca-environment-subnet`. Have the network owner provide approved egress for
the agent subnet, for example by associating the existing NAT gateway, before
installing the agent. Then install Python 3.12, `uv`, Git, PowerShell 7 and the
Azure CLI, and register the agent in a pool authorized only for the ingestion
pipeline. Verify name resolution and port 443 to the Search, OpenAI and Blob
endpoints from the agent before the first publication.

### Run and verify

Start with `enablePublishing=false` and validate offline (worker Steps 6 and 8).
With owner sign-off, run the first `sync` (worker Step 9), then the worker
Step 10 checks: documents and citations, state blobs, an unchanged rerun with
`upserts: 0` and `embedding_calls: 0`, and a single changed file. Rerun the
[retrieval smoke tests](azure-devops-markdown-poc.md#approve-search-outbound-access-to-the-embedding-model)
and ask a known-answer question in chat. Rehearse interrupted-run recovery.

| Worker file | Use |
| --- | --- |
| `docs/deployment.md` | Step-by-step setup; follow it with the decisions and mappings above |
| `docs/operations.md`, `docs/limitations.md` | Day-2 operation, recovery, the waiver and later admission models, known limits |
| `examples/pipeline-source.toml`, `examples/publishing-config.toml` | Templates for the two configuration files |
| `examples/content-repo/azure-pipelines.yml` | Pipeline for each content repository |
| `scripts/New-IngestionIdentity.ps1` | Worker role assignments |
| `pyproject.toml`, `uv.lock` | Locked Python 3.12 dependencies |

Use the platform-rendered schema, never the worker's `examples/index-schema*.json`.
If the customer cannot reach GitHub, arrange an approved mirror of the delivered
commit. Repository Build Service checkout permissions are separate (worker Step 4.2).

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
Startup in the customer's selected access mode remains an acceptance check.

## Acceptance, troubleshooting and recovery

- Check a clean second checkout reproduces profile composition and builds.
- Verify public-network-disabled resources, normal private DNS/TLS and scoped
  runtime/worker permissions; a 403 can be networking or authorization.
- Confirm every required Search shared private link is `Approved`/`Succeeded`
  and both [retrieval smoke tests](azure-devops-markdown-poc.md#approve-search-outbound-access-to-the-embedding-model)
  pass, before and after first publication.
- Confirm the selected [access mode](azure-devops-markdown-poc.md#choose-the-application-access-mode):
  anonymous chat works without sign-in, or signed-out callers are refused and
  approved users sign in.
- Confirm generated names, no accidental old POC accounts, exact image digests,
  completed configuration and persisted runtime strategy.
- Validate full schema, identical ingestion/query embeddings and source citations.
- Validate no-change ingestion and interruption recovery with synthetic content.
- Preserve content/state on failed setup; do not delete/recreate accounts/indexes.
- Restore compatible image/config/schema bindings deliberately. Do not run full
  hooks as destructive index repair or interpret Blob restore as Search rollback.

| Symptom | Likely cause and check |
| --- | --- |
| Orchestrator logs `Foundry IQ retrieve failed status=502` | Run the knowledge-base smoke test to see Search's actual error. A vectorization `403` means the `openai_account` link is not approved or the Search identity lacks model access. |
| UI returns HTTP 503 "authentication required" | `ALLOW_ANONYMOUS=false` without complete OAuth settings; choose a mode deliberately |
| Sign-in appears although anonymous was intended | OAuth settings are published; remove them through the approved configuration process and restart |
| `azd deploy` reports `<component> must resolve to <commit> but ... is at ...` | An existing sibling folder is at another commit; move it aside and rerun so [deployment checks out the pin](azure-devops-markdown-poc.md#component-checkouts) |
| `azd deploy` reports `pinned commit ... is not in the history of branch ...` | The source branch was rewritten or the pin is wrong; restore the branch or review the pin; do not edit the hook |
| Build fails downloading Python/npm packages | [Package registry settings](azure-devops-markdown-poc.md#configure-package-registries-before-building) |
| Hooks report public DNS answers | [Private access](private-access.md#verify-dns-routing-and-service-access) |
| Worker reports "Deployed schema differs" | `search_schema_api_version` is not `2025-05-01-preview`, or the schema file was edited; [use the handoff values](azure-devops-markdown-poc.md#map-platform-values-into-the-worker-configuration) |
| Worker run cannot resolve or reach Search, OpenAI or Blob | The job ran on a Microsoft-hosted agent or an agent without private DNS/egress; [use the private agent](azure-devops-markdown-poc.md#provide-the-private-publishing-agent) |
| Exporter refuses `non-serving` | This index is bound by the main deployment; use `serving` as in [step 6](azure-devops-markdown-poc.md#6-export-a-reviewed-worker-handoff) |

Azure DevOps permissions are not automatically copied into Search. Until an
approved permission contract and allow/deny tests pass, use synthetic or
explicitly approved common-audience non-sensitive content only. This POC
publishes under an owner waiver, not an admission
([step 7](azure-devops-markdown-poc.md#decisions-for-this-poc)). Authentication,
private networking and fluent answers do not establish document authorization.
In anonymous mode every VPN user can retrieve everything in the index.

Before delivery record platform/component/worker commits, image digests,
documentation revision, schema/hash, nonsecret bindings, tested commands and
outstanding gates. Publication, a paid validation deployment and customer access
changes require separate authorization.
