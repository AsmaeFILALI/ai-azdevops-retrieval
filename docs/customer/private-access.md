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

Before the VPN exists, use the customer profile's `bootstrap` settings.
Here, an "overlay" means a group of settings saved in the selected azd
environment; it is not an automatic VPN action:

```text
RUN_FROM_JUMPBOX=false
AZURE_SKIP_NETWORK_ISOLATION_WARNING=true
```

These settings let infrastructure provisioning finish while deliberately
skipping service configuration that needs access to private endpoints.
Despite its legacy name, `RUN_FROM_JUMPBOX` also controls a laptop connected
through VPN; this profile does not require or deploy a jumpbox.
Deferral is not application readiness.
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
   **Azure VPN Client** profile. Keep the original unchanged in a private local
   location; do not commit it.
4. **Before importing, prepare the DNS client configuration as described below.**
   A generated profile can contain only `<clientconfig i:nil="true" />`; the
   gateway download does not automatically include the deployment's private
   resolver and workload DNS suffixes.
5. Import the prepared full XML profile into Azure VPN Client, save it and sign
   in with an authorized account in the customer's tenant. If a connection was
   already imported, reimport/update that customer connection, then disconnect
   and reconnect it. Editing the downloaded XML does not update an imported
   connection.
6. Verify the active VPN route and normal OS DNS. Never copy a developer's full
   VPN profile, resolver IP or old private endpoint addresses. Do not connect
   simultaneously to old/new POC VPNs that use the same address ranges.

The template does not install/import the client or perform interactive sign-in.
Do not create a second gateway in the same VNet. VPN authentication is separate
from Azure CLI/azd login, application admission and document authorization.
Treat exported VPN profiles and signed download URLs as private working data.

### Prepare Windows split-DNS settings

The [client configuration fragment](../../samples/customer-poc/vpn-clientconfig.example.xml)
contains the service DNS suffixes for this public-Azure POC; it is **not** a
complete VPN profile and cannot be imported on its own.

1. Make a private local copy of the customer's downloaded full profile.
2. Replace its whole `clientconfig` element (including `i:nil="true"` when
   present) with the fragment. Keep it inside the existing `AzVpnProfile` root,
   using the root's `http://schemas.datacontract.org/2004/07/` XML namespace.
   Do not add a second `clientconfig` or leave the populated element marked nil.
3. Replace `REPLACE_WITH_CUSTOMER_RESOLVER_IP` with **this deployment's**
   `dnsServerAddress.value` from `pointToSiteVpnDeployment` outputs.
   Do not use the gateway public IP, a private endpoint IP, a public DNS server
   or Azure's VNet-only virtual DNS IP `168.63.129.16`.
4. Preserve every other part of the downloaded profile, especially its gateway,
   server validation, authentication, certificates, transport and route settings.
   Import the full edited profile, not the fragment.

`dnsserver` selects the private resolver; `dnssuffix` entries select the DNS
namespaces to send through it. These are domain suffixes, **not an inventory
of individual resource FQDNs**. For example `.azconfig.io` covers the new
App Configuration hostname, `.vault.azure.net` covers the vault's normal
hostname, and `.azurecontainerapps.io` covers the internal Container Apps
domain. The fragment also covers Blob, Search, Cosmos, registry, Foundry/OpenAI
and monitoring endpoints. Add approved private custom-domain suffixes if used;
review the set for corporate DNS policy. Do not force all Internet DNS through
the tunnel or configure default routes as a DNS workaround.

The Bicep template creates the resolver and private zones/links, but does not
edit a downloaded client profile or install Windows DNS policy. With Entra
authentication, Azure VPN Client uses the Windows Name Resolution Policy Table
(NRPT). `ipconfig /all` alone does not establish whether VPN DNS is configured.
This procedure targets Windows; macOS suffix handling differs and requires
separate validation.

## Verify DNS, routing and service access

Use **actual outputs** from this environment, not values from another POC.
Check App Configuration, Key Vault, Search, OpenAI, ACR and internal Container
Apps hostnames. Compare direct-resolver DNS with normal Windows resolution:

```powershell
$hostnameToCheck = '<service-hostname>'
$resolverAddress = '<dnsServerAddress-from-customer-deployment>'

# First prove that the private resolver is reachable and has the private records.
Resolve-DnsName $hostnameToCheck -Server $resolverAddress -Type A -DnsOnly

# Then prove that normal applications will select the VPN DNS policy.
Get-DnsClientNrptPolicy -Effective |
    Select-Object Namespace, NameServers
Resolve-DnsName $hostnameToCheck -Type A -DnsOnly
Test-NetConnection <service-hostname> -Port 443
```

Expect the private DNS chain to resolve to the correct workload private address.
Both lookups must match the intended private endpoint; a direct `-Server`
success alone does not validate normal application DNS.

| Observation | Next check |
| --- | --- |
| Direct resolver returns private IP; normal lookup returns public IP or fails | Missing/stale client `dnsservers`/`dnssuffixes`, missing effective NRPT rules or conflicting corporate policy; reimport/reconnect the correct profile and retest |
| Direct resolver times out | VPN connection, route to the resolver subnet and DNS reachability; suffixes alone cannot fix routing |
| Direct resolver returns public IP or no record | Resolver's VNet, private-zone links/records and correct customer resource hostname |
| Both return private IP but HTTPS fails | Private endpoint/routing, TLS and then the actual caller's data-plane permissions |

Use the normal hostname, not a hardcoded private IP or hosts-file entry. If a
previous public response is cached, clear the local DNS cache after reconnecting
and retest according to the workstation's policy. Do not change global DNS or
manually add machine-wide NRPT rules to hide an incomplete imported profile.
A TCP connection is only a network check: follow it with authenticated HTTPS
operations using the approved customer identity. Do not bypass TLS validation,
use fabricated identity headers or grant broad permissions to mask a 403.

Internal Container Apps ingress also needs a private zone for the environment's
default domain, with a wildcard record to its static ingress address. This is
separate from service Private Link zones. Template-managed DNS creates it;
with policy-managed DNS the DNS owner must provide equivalent records.
DNS-zone links alone do not configure a laptop's resolver or VPN routes.

## Finish connected configuration

**Do this after connecting the VPN and verifying normal private DNS, but before
application deployment.** Resume the service configuration skipped during
initial provisioning; this is not an optional step at the end of deployment.

| Phase | Saved azd settings | Effect |
| --- | --- | --- |
| Before VPN access | `RUN_FROM_JUMPBOX=false`, `AZURE_SKIP_NETWORK_ISOLATION_WARNING=true` | Defer private service configuration while provisioning the foundation |
| After VPN/DNS verification | `RUN_FROM_JUMPBOX=true`, `AZURE_SKIP_NETWORK_ISOLATION_WARNING=false` | Clear the bootstrap deferral and check connectivity before configuring services |

`RUN_FROM_JUMPBOX=true` does **not** create a jumpbox or connect the VPN.
`AZURE_SKIP_NETWORK_ISOLATION_WARNING=false` clears the legacy warning-skip
deferral setting. Neither value bypasses the private-connectivity checks.
Connecting Windows VPN does not update saved azd values automatically. If the
bootstrap values remain, post-provisioning exits as deferred without completing
service configuration.

From the repository root, with the intended customer azd environment selected:

```powershell
azd env set RUN_FROM_JUMPBOX true
if ($LASTEXITCODE -ne 0) { throw 'Cannot clear post-provision deferral.' }
azd env set AZURE_SKIP_NETWORK_ISOLATION_WARNING false
if ($LASTEXITCODE -ne 0) { throw 'Cannot clear legacy warning deferral.' }
pwsh -NoProfile -File .\scripts\postProvision.ps1
```

These are the two values in the customer profile's `connected` group. On Bash
hosts, set the same two azd values, checking each command succeeds, then run
`bash ./scripts/postProvision.sh` instead of the PowerShell hook.
The hook loads the selected environment, verifies private-network prerequisites,
and completes configuration such as App Configuration, Key Vault and the Search
index/knowledge objects. It does not rerun the entire infrastructure deployment.
Fix reported failures; do not interpret a deferred or failed hook as completed
setup.

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
