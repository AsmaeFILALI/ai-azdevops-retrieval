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
- Publish approved tested component commits before adopting them in matching
  `manifest.json` and `app-definition.json` references. Dirty image tags cannot
  establish provenance or be used as evidence of deployed behavior.

### Customer source adoption, 2026-11-11

The customer forks now expose UI `132f70bf862a482433faf4fccbdbf09cf8f1e12a`
on `feature/customer-build-feeds` and orchestrator
`72204060a055ed6081d0cc4d08d221275e907d1f` on `feature/citation-guard`,
under `AsmaeFILALI/agent-app-ui` and `AsmaeFILALI/agent-app-orchestrator`.
Both commits passed clean Linux/amd64 builds, dependency checks and offline
smoke checks. The upstream bundled ingestion pin and foundation provenance
remain unchanged.

Use the existing branch-ref plus expected-full-commit deployment path; leave
component tags empty rather than attaching old upstream version tags to new
source. Branch movement fails closed at the commit verification. This avoids
inventing a release and needs no new source resolver. Formal release adoption
must choose approved real tags and update the combination deliberately.

Only the incorporated-normalization fixture's expected loaded manifest metadata
is updated. Original historical resource/output fingerprints and before-values
remain unchanged; the compiled loaded manifest still must match the root
manifest exactly. No Azure resource or application deployment follows from
source pin adoption.

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

### Customer-local documentation delivery, 2026-11-12

The customer can access only this platform repository. At the user's explicit
request, provide the profile's deployment, configuration, VPN/private-access
and application-authentication guidance under `docs/customer/`, linked locally
from README. This is a scoped customer-handover exception to the central-site
documentation policy, not a change to runtime repository ownership.

Consolidate the relevant central-source material with its original provenance
and MIT attribution; do not make a separate docs checkout or website build a
prerequisite. Validate all local guide links and source/profile consistency.
Keep this bundle aligned with future changes to the delivered platform.
The customer still needs an approved delivery of UI/orchestrator and worker
source or artifacts; local documentation alone does not resolve that blocker.
No source pins, deployment hooks, resources or access permissions change.

### PR #2 review remediation

- Record genuine `upstream` repo/tag/commit metadata for each fork. Verify it is
  real ancestry of the selected source. Compatibility checks use that version,
  while source fetching still uses the explicit branch and exact current commit.
  Do not attach an old release locator tag to new source.
- Exclude root/nested environment files, local config/state, uploads and logs
  from both component Docker contexts. Git cleanliness alone does not establish
  context safety. Add explicit exclusion contracts and synthetic COPY/export
  tests; the latter require a healthy Docker engine.
- Bound overlong citation buffering without emitting a usable Markdown opening
  delimiter. Preserve observation/off modes and test actual renderer behavior,
  chunk splits, image syntax and history extraction.
- Compare portability against the committed Git seed, not the intentionally
  generated working parameters. Reproduce ordinary pre-provision generation in
  a separate Git fixture.
- Link customer instructions to immutable accessible source in the central
  documentation fork until the official site publishes the page.

The new source fixes pass regression/lint checks. Docker engine HTTP 500/readiness
timeouts prevent fresh layer-export/image verification here; that limitation is
explicitly reported, not converted into a passing integration check.

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
