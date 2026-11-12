# Customer deployment documentation

Start with the [private Azure DevOps Markdown POC runbook](azure-devops-markdown-poc.md).
All required platform deployment instructions for that profile are in this
directory and the linked source files in this repository. Access to the
separate `AsmaeFILALI/AI-Landing-Zones` documentation repository or its website
is not required.

| Local guide | Contents |
| --- | --- |
| [Deployment runbook](azure-devops-markdown-poc.md) | Prerequisites, new environment, phased deployment, state storage, worker handoff, development, acceptance and recovery |
| [Configuration and ownership](configuration.md) | Environment boundaries, component pins, index/schema, embeddings, retrieval/citations, build feeds and pipeline responsibilities |
| [Private access](private-access.md) | Template-managed VPN, DNS, connected configuration, private build/agent access and diagnosis |
| [Application authentication](application-auth.md) | Customer Entra registration, runtime settings, admission and authentication acceptance |

Commands assume the repository root, not this documentation directory.
Use the [customer profile](../../samples/customer-poc/azd-env.example.json) and
[state-store example](../../samples/customer-poc/ingestion-state.parameters.example.json);
replace placeholders in ignored local copies.

## What was in the other documentation repository?

The customer-specific work there affected these files. The relevant guidance
for this private classic/Markdown profile is consolidated into the local
guides above; this is not a copy of the entire general-purpose documentation site.

| Original source path | Local coverage |
| --- | --- |
| `docs/agent-landing-zone/azure-devops-markdown-poc.md` | Deployment runbook |
| `docs/agent-landing-zone/deploy-infra-only.md` | Foundation/bootstrap stages in the runbook |
| `docs/agent-landing-zone/configuration.md` | Configuration and ownership |
| `docs/agent-landing-zone/network-isolation.md` | Private access and build requirements |
| `docs/agent-landing-zone/private-access.md` | Private access |
| `docs/agent-landing-zone/foundry-iq.md` | Index/knowledge-object ownership and retrieval configuration |
| `docs/agent-landing-zone/ingestion.md` | Schema provisioning, control-state deployment and worker handoff |
| `docs/agent-landing-zone/azure-devops.md` | Pipeline ownership and private-agent requirements |
| `docs/agent-landing-zone/examples/azure-devops/azure-pipelines.yml` | General application promotion example, not the independent Markdown worker pipeline |
| `docs/bicep/parameterization.md` | Primary/Search/Cosmos regions and root/environment parameter mapping |
| `mkdocs.yml` | Website navigation only; not needed to read these Markdown files |

The source site also has generic material for other deployment modes, hosted
agents, integrations and the broader AI Landing Zone. Those are not prerequisites
for this POC. Its application-authentication reference informed the local
authentication guide.

## Documentation is local; application source is still separate

This change removes the **documentation-repository** access requirement. It
does not make the deployment an offline or single-repository source bundle:

- The deployer still fetches UI/orchestrator source from the repositories and
  full commits in [manifest.json](../../manifest.json). Access to approved
  package/container registries is also required.
- The independent Azure DevOps Markdown worker, its templates, deployment and
  operations guides, identity setup and source configuration remain a separate
  deliverable. This repository does not contain its executable implementation.
- If the customer can access **only this repository**, with no access to those
  sources or approved build artifacts, application/worker delivery is still
  blocked. Arrange a reviewed source mirror or artifact delivery before
  deployment. Do not substitute upstream defaults or dirty local checkouts.
- Do not use the general application-promotion pipeline as a replacement for
  the worker's publishing pipeline.

The [handover gates](../plans/customer-deployment-handover.md) track the
remaining cross-repository and customer acceptance work.

## Provenance and maintenance

Adapted from `AsmaeFILALI/AI-Landing-Zones` at commit
`4fac1bcc7b674ca45d5517a209b78f5ff063a608`, originally derived from the
Microsoft AI Landing Zones documentation. Copyright (c) Microsoft Corporation;
distributed under the repository's [MIT license](../../LICENSE).

This repository-local customer handover is the requested exception to the
general central-site documentation policy. Update it alongside profile, source
pin, deployment or contract changes. The upstream website remains an optional
general reference, not a dependency for following this handover.
