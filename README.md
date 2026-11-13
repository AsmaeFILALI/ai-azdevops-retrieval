<!--
page_type: sample
languages:
- azdeveloper
- powershell
- bicep
products:
- azure
- azure-ai-foundry
- azure-openai
- azure-ai-search
urlFragment: agent-landing-zone
name: Agent Landing Zone
description: Secure, enterprise-ready landing zone for deploying AI agent applications on Microsoft Foundry, with Zero-Trust networking and IaC-first deployment.
-->
<img src="media/logo.png" alt="Agent Landing Zone logo" width="80" align="left"/>

# Agent Landing Zone

Secure, enterprise-ready landing zone for deploying AI agent applications on Microsoft Foundry.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Docs](https://img.shields.io/badge/docs-AI%20Landing%20Zones-0078D4.svg)](https://azure.github.io/AI-Landing-Zones/)
[![Azure Developer CLI](https://img.shields.io/badge/azd-compatible-0078D4.svg)](https://learn.microsoft.com/azure/developer/azure-developer-cli/)

> [!NOTE]
> **GPT-RAG has evolved into Agent Landing Zone.** Same project, broader scope: infrastructure and applications for enterprise agents on Azure. For Agent Landing Zone, use the [current documentation](https://azure.github.io/AI-Landing-Zones/agent-landing-zone/). For older GPT-RAG deployments, refer to the [legacy documentation](https://azure.github.io/agent-landing-zone/).

## Architecture

Reference architectures for private-network deployments. Resource selection and
reuse depend on deployment settings. Select an image to open the full-resolution PNG.

### Standalone

[![Standalone Agent Landing Zone architecture](media/AI-Landing-Zone-without-platform.png)](media/AI-Landing-Zone-without-platform.png)

### With Platform Hub

[![Agent Landing Zone with Platform Hub architecture](media/AI-Landing-Zone-with-platform.png)](media/AI-Landing-Zone-with-platform.png)

## Deploy

- [Full stack](https://azure.github.io/AI-Landing-Zones/agent-landing-zone/deploy-full-stack/) — Deploy the infrastructure and default agent application.
- [Infrastructure only](https://azure.github.io/AI-Landing-Zones/agent-landing-zone/deploy-infra-only/) — Provision the foundation without deploying application images.
- [Custom applications](https://azure.github.io/AI-Landing-Zones/agent-landing-zone/build-your-own-app/) — Deploy your own application on the foundation.

For the private Azure DevOps Markdown POC, start with the reviewed
[customer input examples](samples/customer-poc/) and the
[customer deployment runbook](docs/customer/azure-devops-markdown-poc.md).
The [complete customer documentation bundle](docs/customer/README.md) includes
configuration, private access and application authentication guidance locally;
access to the separate documentation repository is not required.
Use the platform revision supplied with the handover, not an unreviewed default
branch. The separate Markdown worker is not the bundled ingestion component.

This customer branch selects the tested UI/orchestrator fixes from public
customer forks through `manifest.json`: a feature-branch ref locates each source,
and its full commit pin is verified before building. These are source candidates,
not new upstream release tags. Moving a selected branch to another commit fails
the pin check until the references are deliberately updated.
Component `upstream` metadata records the genuine release provenance separately
from the branch used to fetch fixes. Application/component and worker source
access is still required: the local documentation bundle does not vendor those
implementations or provide an offline build.

## Components

Component repositories and commits are pinned in [manifest.json](manifest.json).
The UI/orchestrator links below open the selected customer source revisions.

| Component | Repository |
|---|---|
| UI | [AsmaeFILALI/agent-app-ui](https://github.com/AsmaeFILALI/agent-app-ui/tree/7ff09f49325d91018b2d443f993edf9b4cfd042d) |
| Orchestrator | [AsmaeFILALI/agent-app-orchestrator](https://github.com/AsmaeFILALI/agent-app-orchestrator/tree/a825e0bd2d0a7930da55a5ef9f7d20e2d4b036e2) |
| Bundled ingestion (disabled in this customer profile) | [Azure/agent-app-ingestion](https://github.com/Azure/agent-app-ingestion) |

## Documentation

For this customer POC, use the [repository-local documentation](docs/customer/README.md).

- [Deployment runbook](docs/customer/azure-devops-markdown-poc.md)
- [Configuration and ownership](docs/customer/configuration.md)
- [VPN and private access](docs/customer/private-access.md)
- [Application authentication](docs/customer/application-auth.md)

Deployment inputs and the separate pipeline state-store template:

- [Customer azd environment profile](samples/customer-poc/azd-env.example.json)
- [VPN client DNS configuration fragment](samples/customer-poc/vpn-clientconfig.example.xml)
- [Ingestion state-store parameters](samples/customer-poc/ingestion-state.parameters.example.json)
- [Ingestion state-store Bicep template](infra/ingestion-state.bicep)

The [AI Landing Zones documentation site](https://azure.github.io/AI-Landing-Zones/agent-landing-zone/)
is an optional general reference for other supported deployment modes.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md), and [SUPPORT.md](SUPPORT.md). Release history is in [CHANGELOG.md](CHANGELOG.md).

## Trademarks

This project may contain trademarks or logos for projects, products, or services. Authorized use of Microsoft trademarks or logos is subject to and must follow [Microsoft's Trademark & Brand Guidelines](https://www.microsoft.com/legal/intellectualpropertyandcustomerinfo/trademarks/usage/general). Use of Microsoft trademarks or logos in modified versions of this project must not cause confusion or imply Microsoft sponsorship. Any use of third-party trademarks or logos is subject to those third-party's policies.
