targetScope = 'resourceGroup'

@description('Object ID of the principal to grant AcrPull on the registry')
param principalObjectId string

@description('Name of the existing Azure Container Registry')
param registryName string

@description('Optional override for the role assignment GUID. Leave empty to deterministically derive it from principalObjectId+registry+role.')
param roleAssignmentName string = ''

resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: registryName
}

// AcrPull is the role App Service grants to its managed identity to pull images
// from ACR. Container-based App Service Deployment Center configures this assignment
// when "Use managed identity" is selected.
var acrPullRoleId = '7f951dda-4ed3-4680-a7ca-43fe172d538d'
var derivedName = guid(registry.id, principalObjectId, acrPullRoleId)
var assignmentName = empty(roleAssignmentName) ? derivedName : roleAssignmentName

resource roleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: registry
  name: assignmentName
  properties: {
    principalId: principalObjectId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPullRoleId)
  }
}

output roleAssignmentName string = roleAssignment.name
