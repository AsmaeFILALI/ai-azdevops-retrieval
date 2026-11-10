# ADR-0025: Optional Entra point-to-site VPN and staged private migration

**Status:** Implemented; private infrastructure deployed; VPN client validation pending<br>
**Date:** 2026-10-27<br>
**Owners:** Platform and network maintainers

## Context

An inherited policy disables public Key Vault access. The user approved adding
a point-to-site VPN gateway and enabling network isolation without deleting the
successful POC resources. They confirmed Entra ID/OpenVPN authentication, VNet
`10.77.0.0/21`, VPN clients `172.27.240.0/24`, a parallel private Container Apps
environment, ongoing networking costs, and a connected-host image-build path.
Cosmos remains in Canada Central; the remaining foundation stays in Canada East.

The existing Container Apps environment has no customer VNet and cannot change
network type in place. A VPN tunnel also needs DNS resolution for private
endpoints; linking private DNS zones to a VNet does not make them resolvable
from an arbitrary laptop.

Priorities are preserving data/resources (no deletes in preview), private
service access (private DNS and authenticated access tests), explicit identity
(tenant-bound Entra, no anonymous VPN), backward compatibility (default-off
resources), and recoverability (old app placeholders retained until sign-off).

## Alternatives considered

### Optional gateway with private DNS resolver (selected)

Add a route-based, active-standby, Standard-public-IP VPN gateway using Entra
authentication and OpenVPN. Add a dedicated DNS Private Resolver inbound
endpoint so the VPN client can resolve linked private zones. Deploy only when
explicitly selected with network isolation. Existing public-mode deployments
remain unchanged.

Use the Microsoft-registered Azure VPN Client audience. Local client software,
profile import, sign-in, and user/group admission remain operator responsibilities.
Tenant authentication is not application or document authorization.

### Jumpbox and Bastion only

Offers a connected deployment host but does not give the laptop VPN access.
Valid for administrative use, but does not meet the requested access method.

### Do not change

Preserves all resources but leaves Key Vault configuration blocked. Public-access
policy exclusions are not part of this decision.

## Decision

Implement a default-off VPN module, dedicated `GatewaySubnet` without NSG/UDR,
and delegated DNS resolver subnet. Validate the client pool against the VNet,
and validate explicit networking/authentication inputs before deployment.
Expose gateway ID/public IP, resolver address, and client configuration inputs.
No root certificates, passwords, or client secrets are generated or committed.

For this POC, provision a new VNet-integrated internal Container Apps environment
and uniquely named app placeholders. Preserve the old environment and apps.
Explicit app-name selection must carry through configuration and identity
discovery; ambiguous service tags must not select the old identity.

Keep the existing successful data/model services and attach private endpoints.
Upgrade the existing registry to Premium for its private endpoint. Use a
connected Docker host for builds because dedicated ACR build pools are not
listed in Canada East. Use explicit NAT egress rather than an unconfigured
firewall route. No full-tunnel VPN or public application ingress is selected.

## Consequences

VPN Gateway, public IP, DNS resolver, private endpoints, NAT, Premium ACR and
parallel app capacity incur ongoing charges. Gateway provisioning can take
tens of minutes. Existing public service endpoints become unavailable to
unconnected clients after isolation.

The user must install Azure VPN Client, import the generated profile, configure
the resolver address, and sign in. Deployment may explicitly defer data-plane
configuration until this connectivity is available. Deferred configuration is
not a completed accelerator or working chat application.

## Adoption and recovery

1. Implement and test additive parameters, gating, reserved subnets, DNS and
   explicit app-name selection.
2. Verify quota, allowed regions, policy, no-overlap checks and a non-destructive
   preview against actual resource identities.
3. Provision network/gateway and parallel app foundation with private
   post-provision configuration explicitly deferred.
4. Generate the private client profile, connect and verify private DNS/TLS and
   authenticated Key Vault access before rerunning post-provision.
5. Deploy application images and validate access and document permissions
   separately. Old placeholders are not deleted without explicit approval.

A rollback must not reopen Key Vault or bypass the inherited policy. Preserve
data services and prior app resources; recover private connectivity or restore
the previous validated application configuration. Never claim that flipping the
isolation flag back is a complete or policy-compliant rollback.

## Compliance verification

Compile and lint Bicep, check template size, test disabled/enabled resource
shapes, parameter parity, reserved gateway/DNS subnet rules, client-pool overlap,
and exact new app identity selection. Review no-delete ARM preview. Verify live
resource locations and gateway/private endpoint states. Client tunnel and
end-to-end application tests remain required after the user's interactive sign-in.

## Documentation impact and review trigger

Update the central AI Landing Zones configuration/network/deployment guidance
with parameters, cost, client DNS and the connected-runner gate. Reassess on
VPN authentication/client support changes, address-space changes, policy changes,
or before retiring the old app environment. This ADR authorizes neither policy
exceptions nor destructive cleanup.

## Deployment evidence

The approved migration was provisioned successfully with network isolation
enabled. Independent management-plane reads verified:

- VPN gateway `Succeeded`, VpnGw1AZ, route-based, OpenVPN and Entra-only
  authentication, with the approved tenant and client address pool.
- `GatewaySubnet` has no NSG, route table or delegation; the DNS resolver
  subnet is separately delegated and its inbound endpoint is `Succeeded`.
- All nine private endpoints are `Succeeded` and `Approved`.
- Key Vault, Search, App Configuration, storage, registry, Foundry and the
  selected Cosmos account report public network access `Disabled`.
- The existing registry was upgraded to Premium. The new internal Container
  Apps environment and app placeholders exist; old apps/environment were
  preserved. The new ACA subnet has NAT egress.
- Cosmos remains in Canada Central and the other regional services in Canada
  East. The new orchestrator has its resource-scoped model, Search, registry,
  configuration, secret-reader, storage and Cosmos permissions.

The internal environment also needs its default-domain wildcard DNS record;
the Private Link zone alone does not provide that. A focused, tested
`container-apps-private-dns` module is now wired into the main template, gated
on internal networking and template-managed DNS. Its create-only supplemental
deployment succeeded and links the internal app domain to the same VNet.

Verification includes 180 affected Python tests, 98 deterministic PowerShell
preflight checks, Bicep build/lint, and the existing template-size gate. Root
outputs remain at the ARM limit of 64; gateway/DNS outputs are available from
the nested `pointToSiteVpnDeployment`.

The generated Entra VPN profile was verified and configured with the live
inbound resolver address and the approved VNet split route. Its signed download
URL was not printed or committed. It is stored only in local ignored deployment
state for the operator to import.

Post-provision data-plane configuration was explicitly deferred, as planned.
The user must import the profile into Azure VPN Client and sign in, then verify
private DNS/TLS and authenticated Key Vault access. Only then clear deferral
and rerun post-provision. No application images, ingestion pipeline or documents
were deployed by this migration. No policy exemptions or anonymous application
access were enabled, and no existing resources were deleted.
