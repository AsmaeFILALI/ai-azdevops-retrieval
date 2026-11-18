targetScope = 'resourceGroup'

@description('Route table name, derived by the root naming contract.')
param name string
@description('Workload region.')
param location string
@description('Deployment tags.')
param tags object
@description('Keep gateway-learned routes (for example the point-to-site client pool) on subnets using this route table. Required when a VPN gateway is deployed so replies can return to VPN clients.')
param allowGatewayRoutePropagation bool = false

resource routeTable 'Microsoft.Network/routeTables@2024-07-01' = {
  name: name
  location: location
  tags: tags
  properties: {
    disableBgpRoutePropagation: !allowGatewayRoutePropagation
  }
}

@description('Actual ARM ID of the route table.')
output resourceId string = routeTable.id
