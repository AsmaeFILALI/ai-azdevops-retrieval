targetScope = 'subscription'

import * as const from './constants/constants.bicep'

@description('Workload environment name used for stable default resource names.')
@minLength(1)
@maxLength(48)
param environmentName string

@description('Region for the ingestion control-state account and private endpoint.')
param location string

@description('Existing workload private endpoint subnet ARM ID in the same region.')
param privateEndpointSubnetResourceId string

@description('Existing privatelink.blob private DNS zone ARM ID linked to the workload VNet.')
param blobPrivateDnsZoneResourceId string

@description('Explicit ingestion worker or POC development principal object ID.')
@minLength(36)
@maxLength(36)
param writerPrincipalId string

@description('Principal type for the container-scoped writer assignment.')
@allowed(['ServicePrincipal', 'User', 'Group'])
param writerPrincipalType string = 'ServicePrincipal'

@description('Optional dedicated ingestion resource-group name; empty uses the workload name.')
param ingestionResourceGroupName string = ''

@description('Optional globally unique storage account name; empty derives a stable lowercase name.')
@maxLength(24)
param storageAccountName string = ''

@description('Private Blob container used only for publisher state, intents, and checkpoints.')
param containerName string = 'ingestion-state'

@description('Recovery window for Blob and container soft deletion; no automatic state expiration is configured.')
@minValue(1)
@maxValue(365)
param softDeleteRetentionDays int = 14

@description('Nonsecret resource tags.')
param tags object = {}

resource ingestionGroup 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: empty(ingestionResourceGroupName) ? 'rg-${environmentName}-ingestion' : ingestionResourceGroupName
  location: location
  tags: tags
}

module stateStore './modules/storage/ingestion-control-state.bicep' = {
  scope: ingestionGroup
  name: 'ingestionControlState'
  params: {
    name: empty(storageAccountName) ? '${const.abbrs.storage.storageAccount}ing${uniqueString(subscription().id, environmentName, location)}' : storageAccountName
    location: location
    containerName: containerName
    privateEndpointSubnetResourceId: privateEndpointSubnetResourceId
    blobPrivateDnsZoneResourceId: blobPrivateDnsZoneResourceId
    writerPrincipalId: writerPrincipalId
    writerPrincipalType: writerPrincipalType
    softDeleteRetentionDays: softDeleteRetentionDays
    tags: tags
  }
}

@description('Nonsecret ingestion-worker state-store bindings. No Markdown source or Search indexer is created.')
output ingestionState object = {
  resourceGroupName: ingestionGroup.name
  storageAccountName: stateStore.outputs.accountName
  storageAccountResourceId: stateStore.outputs.accountResourceId
  blobEndpoint: stateStore.outputs.blobEndpoint
  containerName: containerName
  containerResourceId: stateStore.outputs.containerResourceId
  privateEndpointResourceId: stateStore.outputs.privateEndpointResourceId
  writerPrincipalId: writerPrincipalId
  writerPrincipalType: writerPrincipalType
  writerRoleAssignmentResourceId: stateStore.outputs.writerRoleAssignmentResourceId
}
