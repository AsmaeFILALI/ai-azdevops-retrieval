targetScope = 'resourceGroup'

@description('Internal Container Apps environment default domain.')
param domain string

@description('Internal environment static ingress IPv4 address.')
param staticIp string

@description('VNet from which clients resolve the internal app domain.')
param virtualNetworkResourceId string

@description('Resource tags.')
param tags object = {}

resource zone 'Microsoft.Network/privateDnsZones@2024-06-01' = {
  name: domain
  location: 'global'
  tags: tags
}

resource link 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = {
  parent: zone
  name: 'internal-container-apps'
  location: 'global'
  properties: {
    registrationEnabled: false
    virtualNetwork: { id: virtualNetworkResourceId }
  }
}

resource wildcard 'Microsoft.Network/privateDnsZones/A@2024-06-01' = {
  parent: zone
  name: '*'
  properties: {
    ttl: 60
    aRecords: [{ ipv4Address: staticIp }]
  }
}
