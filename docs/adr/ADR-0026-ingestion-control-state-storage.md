# ADR-0026: Dedicated private Blob storage for ingestion control state

**Status:** Implemented and deployed; infrastructure verified, private data-plane checks deferred<br>
**Date:** 2026-10-27<br>
**Owners:** Platform and ingestion maintainers

## Context

The Azure DevOps Markdown worker publishes directly to Search. It needs durable
publication intents, successful snapshots, and a publisher lease. Blob is the
control-state store, not a document staging area or Search indexer source.

The user approved the recommended dedicated private account/container and
container-scoped access for the current signed-in user for POC development.
No pipeline principal was supplied; future worker access must be explicitly
assigned. UI, orchestrator, and Search identities are not consumers of this
store and receive no new grants.

Priorities are independent ownership (no app-storage changes), confidentiality
(Entra-only/private access), recoverable publication (lease/conditional-write
tests), non-destructive adoption (create-only targeted preview), and an explicit
boundary between infrastructure and worker state.

## Alternatives considered

### Dedicated account in a separate ingestion resource group (selected)

Separate access, retention, cost, and deletion boundaries. Reuses the existing
workload VNet private endpoint subnet and Blob private DNS zone; no duplicate
VNet, resolver, VPN gateway, or DNS zone. Costs include a private endpoint,
storage operations/capacity, and retaining old versions.

A targeted subscription-scope entry point creates the resource group and calls
a focused storage module. It does not execute application lifecycle hooks or
reconcile Search. Existing platform root parameters and outputs are unchanged.

### Add a container to the existing application account

Fewer resources, but existing account-level application grants and future
service reconciliation would share an ingestion-state boundary. Retention and
account lifecycle become coupled. Not selected for this extra state store.

### Do not change

No infrastructure cost, but no durable shared checkpoint or publisher lock.
Local state or pipeline artifacts alone do not satisfy the intended publisher
coordination/recovery protocol.

## Decision

Deploy one StorageV2, Standard_LRS, Hot account in Canada East, with a private
`ingestion-state` container, HTTPS/TLS 1.2+, no anonymous access, Shared Key
disabled, no hierarchical namespace, and public network access disabled.
Enable Blob versioning plus 14-day Blob/container soft-delete retention.
Do not enable WORM/legal hold or automatic deletion of control blobs.

Create a Blob private endpoint and associate it with the existing
`privatelink.blob.core.windows.net` zone. The account and endpoint belong to the
new ingestion resource group; the existing subnet and DNS zone are referenced,
not redeclared. The connected publishing host still needs private DNS/TLS.

Assign Storage Blob Data Contributor at the container scope to the explicitly
supplied principal and principal type. For this deployment the user selected
their current sign-in identity. Do not copy application identities or assign
subscription/account-wide data roles. Future pipeline WIF/managed identity
permissions need a deliberate principal assignment and validation.

The worker owns the following logical blob names:

```text
ingestion-state/
  indexes/
    <physical-index-id>/
      publisher.json
      scopes/
        <source-id>/
          checkpoints/
            <manifest-id>.json
          runs/
            <manifest-id>.json
```

Bicep creates only infrastructure and an empty container. It does not create
publisher blobs, manifests, checkpoint pointers, or fake directory markers.
Physical index IDs distinguish service/environment/generation; source IDs
distinguish repository/ref/path scope. Prefixes are not authorization boundaries.

The publisher control blob is mutable under a renewable lease. Run intents and
successful checkpoints use application-enforced create-only writes; a shared
container-wide WORM policy would conflict with mutable control state.
Write durable intent before Search mutations, verify all expected upserts and
deletions, create the checkpoint, then advance committed state conditionally.
Do not infer the committed checkpoint solely from timestamp/filename ordering.

A Blob lease protects that blob, not other blobs or in-flight Search writes.
Every worker must honor ownership and stop issuing new mutations after lease
loss. State and Search have no shared transaction; retries must reconcile
partial or ambiguous outcomes and never treat source-enumeration failure as
an empty corpus. Cleanup must retain referenced checkpoints and unresolved
intents for the approved recovery window.

## Consequences

The existing application storage and Search knowledge-source binding are
unmodified. Account discovery cannot become ambiguous in the app resource
group because this account is in a separate group.

The pipeline runner requires private network connectivity; a developer laptop
VPN does not connect an Azure DevOps hosted agent. No secret, SAS, connection
string, or storage key is required. Native Azure RBAC inheritance still applies;
the deployment creates no additional application grants but cannot negate
pre-existing ancestor permissions.

LRS is a POC durability choice, not a regional disaster-recovery strategy.
Soft delete/versioning do not make Search and state transactionally consistent.
No retrieval quality, source permissions, worker correctness, or application
readiness claim follows from successful account deployment.

## Adoption and recovery

1. Compile/lint and test the focused templates, exact role scope and private
   endpoint/DNS association.
2. Record private environment-specific parameters and validate the create-only
   targeted preview in the confirmed subscription.
3. Deploy the ingestion resource group/account/container incrementally, without
   invoking main accelerator provisioning or post-provision hooks.
4. Verify live account/container/endpoint/RBAC settings, then test conditional
   create/update and lease contention with disposable blobs over private access.
5. Hand off nonsecret endpoint, container and exact principal/scope to the
   worker. Implement its runtime protocol separately.

Keep the account, container and role identity stable on redeployment. Do not
recreate resources as a retry shortcut. Recovery of a committed state version
must be coordinated with the Search publication state. Deletion or data restore
requires explicit approval after the worker begins use.

## Compliance verification

Tests must prove LRS/Hot, private network, OAuth/Shared-Key restrictions,
versioning/retention, no indexer or data-seeding resources, exact container-scoped
role grants, existing zone reference, and outputs matching the intended worker
boundary. Preview must not modify the main accelerator services. Live Blob
tests must not touch real worker keys and must clean up disposable test blobs.
If the VPN is disconnected, report infrastructure verification separately from
pending data-plane verification.

### Deployment evidence

The targeted deployment succeeded in Canada East. The initial exact preview
contained seven resource creates, no modifications or deletions. Bicep lint,
ARM validation and six compiled-template contract tests passed; the targeted
compiled template was 629,038 bytes.

Live management-plane checks verified Standard_LRS/Hot, private networking,
Shared Key and anonymous access disabled, OAuth default, HTTPS/TLS 1.2,
infrastructure encryption, Blob versioning, 14-day Blob/container soft delete,
private container, an Approved Blob endpoint and its record in the existing
zone. The approved development user has the exact container-scoped writer role.
All 86 existing main platform resources remained in the original group.

A repeat preview contained no creates/deletes; its modifications were AVM/API
default/read-only-field and unresolved-expression noise, not changes to the
verified public-access, authentication, retention or role settings. No repeat
deployment was needed.

No publisher/checkpoint/run blobs were created. Private authenticated writes
and lease contention were not tested: this workstation had no workload VPN
route, its default resolver returned a public Blob address, and the user was
unavailable to reconnect. This is an explicit validation gate before worker
use, not a reason to enable public access or broaden permissions.

## Documentation impact

Update the central ingestion documentation with targeted deployment, control
state versus document ingestion, private-runner requirements, outputs and
worker-owned blob semantics. Keep credentials and signed URLs out of this ADR
and documentation. Current component pins and application runtime keys do not
change.

## Review trigger

Review before production use, adding another independent writer/trust boundary,
changing retention, enabling automatic cleanup, introducing geo-replication or
moving publication control into a different service.
