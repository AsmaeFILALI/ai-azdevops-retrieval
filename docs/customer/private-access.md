# Private access for the customer POC

Follow the [deployment runbook](azure-devops-markdown-poc.md) first.
The [customer profile](../../samples/customer-poc/azd-env.example.json) selects
private standalone networking, an Entra/OpenVPN P2S gateway, an inbound DNS
resolver, NAT egress and local image builds. Jumpbox/Bastion/firewall are disabled.

## Before provisioning

Have the network owner approve the retained VNet/subnet/client ranges, check
overlap with corporate/local networks, approve ongoing costs and authorize
VPN users. The deployment identity needs the approved network/resource/DNS
permissions; a VPN user does not need infrastructure write permissions.

Use the profile's bootstrap overlay:

```text
RUN_FROM_JUMPBOX=false
AZURE_SKIP_NETWORK_ISOLATION_WARNING=true
```

This explicitly defers service data-plane configuration while the private path
is unavailable. Despite its legacy name, `RUN_FROM_JUMPBOX` also controls the
connected-workstation path. Deferral is not application readiness.
Keep public access disabled; do not enable public endpoints as a workaround.

## Connect the template-managed VPN

1. Provision the foundation from the repository root.
2. Read the nested deployment outputs in the selected network resource group:

   ```powershell
   az deployment group show --subscription <customer-subscription> `
     --resource-group <network-resource-group> --name pointToSiteVpnDeployment `
     --query properties.outputs --output json
   ```

3. Use the resulting gateway's Azure VPN configuration to generate/download the
   **Azure VPN Client** profile. Import it into Azure VPN Client and sign in
   with an authorized account in the customer's tenant.
4. Configure that client's custom DNS server using the deployed resolver inbound
   endpoint address. Use the approved VNet routes for the split tunnel.
5. Verify the active VPN route and normal OS DNS. Never copy a developer's VPN
   profile, resolver IP or old private endpoint addresses.

The template does not install/import the client or perform interactive sign-in.
Do not create a second gateway in the same VNet. VPN authentication is separate
from Azure CLI/azd login, application admission and document authorization.
Treat exported VPN profiles and signed download URLs as private working data.

## Verify DNS, routing and service access

Use **actual outputs** from this environment, not values from another POC.
Check App Configuration, Key Vault, Search, OpenAI, ACR and internal Container
Apps hostnames. On Windows, for example:

```powershell
Resolve-DnsName <service-hostname>
Test-NetConnection <service-hostname> -Port 443
```

Expect the private DNS chain to resolve to the correct workload private address.
A TCP connection is only a network check: follow it with authenticated HTTPS
operations using the approved customer identity. Do not bypass TLS validation,
use fabricated identity headers or grant broad permissions to mask a 403.

Internal Container Apps ingress also needs a private zone for the environment's
default domain, with a wildcard record to its static ingress address. This is
separate from service Private Link zones. Template-managed DNS creates it;
with policy-managed DNS the DNS owner must provide equivalent records.
DNS-zone links alone do not configure a laptop's resolver or VPN routes.

## Finish connected configuration

Apply the profile's connected overlay:

```text
RUN_FROM_JUMPBOX=true
AZURE_SKIP_NETWORK_ISOLATION_WARNING=false
```

Then run `pwsh -NoProfile -File .\scripts\postProvision.ps1` from the repository
root, or `bash ./scripts/postProvision.sh` on Bash hosts. The hook loads the
selected azd environment and checks private-network prerequisites before
data-plane configuration. Fix reported failures; do not interpret a deferred
or failed hook as completed setup.

After completing [application authentication](application-auth.md), run
`azd deploy` from the connected host. Local builds require healthy Docker,
access to approved package sources and private registry connectivity. See
[build requirements](configuration.md#local-image-builds).

## Pipeline agent and recovery

The Markdown worker needs an approved VNet-connected/self-hosted agent and the
same working private DNS path. Microsoft-hosted agents do not inherit a laptop
VPN. Worker WIF authorization, repository checkout permissions and Azure data
roles remain separate.

If resolution is public or absent, check VPN DNS settings, inbound resolver,
private-zone links and records. If DNS is correct but TCP fails, check VPN
routes, address overlap, NSGs and approved routing. If authenticated HTTPS is
denied, check both network policy and the exact identity/data roles. Record
correlation IDs, not tokens or document content.

Reconnect/reimport the approved client profile after approved routing changes.
Do not remove the last working access path, change CIDRs, recreate a populated
service, restart shared network services or weaken isolation as a retry shortcut.
