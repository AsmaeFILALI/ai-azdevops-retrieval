targetScope = 'resourceGroup'

import * as const from '../../constants/constants.bicep'

@description('Globally unique lowercase storage account name.')
@minLength(3)
@maxLength(24)
param name string

@description('Account/private endpoint region; must match the existing endpoint subnet.')
param location string

@description('Private control-state container name.')
param containerName string

@description('Existing private endpoint subnet ARM ID; referenced without modifying the VNet.')
param privateEndpointSubnetResourceId string

@description('Existing Blob private DNS zone ARM ID; no duplicate zone or VNet link is created.')
param blobPrivateDnsZoneResourceId string

@description('Explicit state writer object ID; not an application identity inferred by discovery.')
param writerPrincipalId string

@description('Writer principal type.')
@allowed(['ServicePrincipal', 'User', 'Group'])
param writerPrincipalType string

@description('Blob and container soft-delete recovery window in days.')
@minValue(1)
@maxValue(365)
param softDeleteRetentionDays int = 14

@description('Nonsecret resource tags.')
param tags object = {}

module account 'br/public:avm/res/storage/storage-account:0.26.2' = {
  name: 'ingestionStateAccount'
  params: {
    name: name
    location: location
    tags: tags
    enableTelemetry: false
    kind: 'StorageV2'
    skuName: 'Standard_LRS'
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    allowCrossTenantReplication: false
    defaultToOAuthAuthentication: true
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    publicNetworkAccess: 'Disabled'
    enableHierarchicalNamespace: false
    requireInfrastructureEncryption: true
    networkAcls: {
      defaultAction: 'Deny'
      bypass: 'None'
      ipRules: []
      virtualNetworkRules: []
    }
    blobServices: {
      isVersioningEnabled: true
      deleteRetentionPolicyEnabled: true
      deleteRetentionPolicyDays: softDeleteRetentionDays
      containerDeleteRetentionPolicyEnabled: true
      containerDeleteRetentionPolicyDays: softDeleteRetentionDays
      containers: [
        {
          name: containerName
          publicAccess: 'None'
        }
      ]
    }
  }
}

var containerResourceId = '${account.outputs.resourceId}/blobServices/default/containers/${containerName}'
var writerRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', const.roles.StorageBlobDataContributor.guid)

module writerRole '../security/resource-role-assignment.bicep' = {
  name: 'ingestionStateWriter'
  params: {
    name: name
    roleAssignments: [
      {
        resourceId: containerResourceId
        principalId: writerPrincipalId
        principalType: writerPrincipalType
        roleDefinitionId: writerRoleDefinitionId
      }
    ]
  }
}

module endpoint '../networking/private-endpoint.bicep' = {
  name: 'ingestionStatePrivateEndpoint'
  params: {
    name: '${const.abbrs.networking.privateEndpoint}${name}'
    location: location
    resourceGroupName: resourceGroup().name
    tags: tags
    subnetResourceId: privateEndpointSubnetResourceId
    privateLinkServiceConnections: [
      {
        name: 'ingestion-state-blob'
        properties: {
          privateLinkServiceId: account.outputs.resourceId
          groupIds: ['blob']
        }
      }
    ]
    privateDnsZoneGroup: {
      name: 'default'
      privateDnsZoneGroupConfigs: [
        {
          name: 'blob'
          privateDnsZoneResourceId: blobPrivateDnsZoneResourceId
        }
      ]
    }
  }
}

@description('State storage account name.')
output accountName string = account.outputs.name
@description('State account ARM ID.')
output accountResourceId string = account.outputs.resourceId
@description('Entra-authenticated Blob endpoint; no key or SAS.')
output blobEndpoint string = account.outputs.primaryBlobEndpoint
@description('Exact container scope for state writer grants.')
output containerResourceId string = containerResourceId
@description('Private Blob endpoint ARM ID.')
output privateEndpointResourceId string = endpoint.outputs.resourceId
@description('Container-scoped writer role-assignment ARM ID.')
output writerRoleAssignmentResourceId string = extensionResourceId(containerResourceId, 'Microsoft.Authorization/roleAssignments', guid(writerPrincipalId, writerRoleDefinitionId, containerResourceId))
