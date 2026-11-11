# ADR-0027: Portable customer inputs and evidence-based ingestion handoff

**Status:** Accepted for source implementation; publication/live adoption gated<br>
**Date:** 2026-11-10<br>
**Owners:** Platform and ingestion maintainers

## Context

The customer must reproduce the private classic/Markdown POC without personal
resource names, copied azd outputs, dirty sibling checkouts or manual schema
reconstruction. Keep existing CIDRs. Runtime and worker source remain in their
own repositories. Current uncommitted component experiments are not part of
the clean pinned baseline unless reviewed and published separately.

Priorities: portable naming, reproducible source, explicit identity, fail-closed
binding validation and recoverable adoption. Measure them with generated-name,
root/seed parity, paired clean-source guard and negative handoff tests.

## Alternatives

1. Copy the existing `.azure` environment: low effort but transfers resource
   identities and migration state and does not reproduce clean builds.
2. Create another monolithic deployment/ingestion system: hides existing
   ownership boundaries, duplicates provisioning, increases rollback cost.
3. Keep existing hooks and templates, provide reviewed input examples, reject
   dirty component source and export an allowlisted offline handoff (selected).
4. Do nothing: does not satisfy fresh-clone customer deployment.

## Decision

- Replace the fixed Cosmos input with optional `COSMOS_ACCOUNT_NAME`; preserve
  the existing output name and generated-name fallback. Existing environments
  must persist their selected account before adoption and review the preview.
- Publish explicitly selected `AGENT_STRATEGY` through both configuration
  paths; do not override existing runtime defaults when absent.
- Provide sanitized phase-specific customer input/state examples, unchanged
  network ranges and explicit connected/deferred stages.
- Require clean tracked/untracked component build contexts before copying
  environments or invoking child builds. Do not reset another contributor's work.
- Export a new nonsecret worker handoff from explicit successful main/state
  deployment snapshots and an owner-pinned full rendered schema. The command
  makes no Azure calls, changes no bindings, grants no roles and creates no
  source admission. Validate tenant/subscription/account, schema/index/model,
  endpoint and API-version consistency. Its JSON is an allowlist, not a dump of
  supplied deployment data. Offline validation cannot prove current Azure state,
  permissions, source admission or non-serving status.
- Retain current component pins. Dirty image tags cannot establish provenance;
  approve separate component fixes before changing pins or promising identical
  experimental runtime behavior.

## Adoption, recovery and documentation

Preserve current POC identity overrides locally; implement/test examples and
guards; generate the new customer's schema; review WIF/source admission; then
validate in an explicitly authorized new environment. Never delete existing
data or publish new versions as an implicit effect. Restore compatible code,
image digests and settings together on rollback.

No new paid services, network changes or privileges arise from this source
change. Document deployment/inference cost, model geography, private runner
requirements, unresolved document permissions and local development in the
central AI Landing Zones site, with a short README entry here.

## Fitness functions and review triggers

The clean-source rehearsal exposed a pre-existing checksum mismatch: Git
stores the consumer contract as LF under `.gitattributes`, but the original
sidecar described a CRLF working copy. Correct the sidecar to the exact
committed LF bytes and normalize the local file; JSON semantics/version do not
change. Keep strict byte hashing. Historical ADR hashes remain evidence of
earlier artifacts, not the current delivery pin.

Require root/seed equality, unchanged CIDRs, opt-in strategy defaults, dirty
source rejection in both shells, exact schema hash/endpoint/model/ARM scope
checks and no secret-bearing fields in exported JSON. Preserve historical
infrastructure graph fingerprints. Reassess on a contract/model revision,
sovereign cloud support, new identity mode, component publication or production
protected-content adoption.
