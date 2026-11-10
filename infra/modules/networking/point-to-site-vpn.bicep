targetScope = 'resourceGroup'

@description('VPN gateway name.')
param name string

@description('Location of the gateway and VNet.')
param location string

@description('GatewaySubnet resource ID. No NSG, delegation, or route table may be attached.')
param gatewaySubnetResourceId string

@description('VNet resource ID for the DNS resolver.')
param virtualNetworkResourceId string

@description('Dedicated subnet delegated to Microsoft.Network/dnsResolvers.')
param dnsResolverSubnetResourceId string

@description('Private inbound DNS address, allocated from the resolver subnet.')
param dnsResolverAddress string

@description('Point-to-site IPv4 client CIDR, separate from the VNet and connected networks.')
param clientAddressPool string

@description('Entra directory GUID allowed to authenticate VPN clients.')
param tenantId string

@description('Azure VPN Client audience. Override only with an approved registered VPN application.')
param audience string

@description('Route-based gateway SKU.')
@allowed(['VpnGw1AZ', 'VpnGw2AZ'])
param sku string = 'VpnGw1AZ'

@description('Resource tags.')
param tags object = {}

resource publicIp 'Microsoft.Network/publicIPAddresses@2024-05-01' = {
  name: '${name}-pip'
  location: location
  tags: tags
  sku: { name: 'Standard' }
  properties: {
    publicIPAllocationMethod: 'Static'
    publicIPAddressVersion: 'IPv4'
  }
}

resource gateway 'Microsoft.Network/virtualNetworkGateways@2024-05-01' = {
  name: name
  location: location
  tags: tags
  properties: {
    gatewayType: 'Vpn'
    vpnType: 'RouteBased'
    activeActive: false
    enableBgp: false
    sku: { name: sku, tier: sku }
    ipConfigurations: [
      {
        name: 'gateway-ip'
        properties: {
          privateIPAllocationMethod: 'Dynamic'
          subnet: { id: gatewaySubnetResourceId }
          publicIPAddress: { id: publicIp.id }
        }
      }
    ]
    vpnClientConfiguration: {
      vpnClientAddressPool: { addressPrefixes: [clientAddressPool] }
      vpnClientProtocols: ['OpenVPN']
      vpnAuthenticationTypes: ['AAD']
      aadTenant: 'https://login.microsoftonline.com/${tenantId}/'
      aadIssuer: 'https://sts.windows.net/${tenantId}/'
      aadAudience: audience
    }
  }
}

resource resolver 'Microsoft.Network/dnsResolvers@2022-07-01' = {
  name: '${name}-dns'
  location: location
  tags: tags
  properties: {
    virtualNetwork: { id: virtualNetworkResourceId }
  }
}

resource inbound 'Microsoft.Network/dnsResolvers/inboundEndpoints@2022-07-01' = {
  parent: resolver
  name: 'vpn-inbound'
  location: location
  tags: tags
  properties: {
    ipConfigurations: [
      {
        privateIpAllocationMethod: 'Static'
        privateIpAddress: dnsResolverAddress
        subnet: { id: dnsResolverSubnetResourceId }
      }
    ]
  }
}

@description('VPN gateway ARM resource ID.')
output resourceId string = gateway.id
@description('Gateway public IPv4 address.')
output publicIpAddress string = publicIp.properties.ipAddress
@description('DNS server address to configure in the Azure VPN Client profile.')
output dnsServerAddress string = inbound.properties.ipConfigurations[0].privateIpAddress
@description('Gateway name used to generate the Azure VPN Client profile.')
output gatewayName string = gateway.name
