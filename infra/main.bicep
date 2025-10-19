@description('Location for all resources. Defaults to resource group location.')
param location string = resourceGroup().location

@description('Project name used as prefix for resource names')
param projectName string

@description('SKU for Static Web App')
@allowed([
  'Free'
  'Standard'
])
param swaSku string = 'Free'

@description('Function App runtime version')
param functionRuntimeVersion int = 4

@description('Comma-separated list of allowed email addresses')
param allowedEmails string = 'awwsawws@gmail.com,awwsawws@hotmail.com'

@description('Enable dry run mode (no actual VM creation)')
param dryRun string = 'false'

@description('Optional: Custom VM Image Resource ID for pre-baked WireGuard images. If provided, VMs will use this custom image instead of a marketplace image with cloud-init. Format: /subscriptions/{subscriptionId}/resourceGroups/{resourceGroupName}/providers/Microsoft.Compute/images/{imageName} or /subscriptions/{subscriptionId}/resourceGroups/{resourceGroupName}/providers/Microsoft.Compute/galleries/{galleryName}/images/{imageName}/versions/{versionNumber}')
param customVmImageId string = ''

// Generate unique names
var uniqueSuffix = uniqueString(resourceGroup().id)
var storageAccountName = '${projectName}${uniqueSuffix}'
var appInsightsName = '${projectName}-appinsights'
var functionAppName = '${projectName}-func'
var staticWebAppName = '${projectName}-swa'
var hostingPlanName = '${projectName}-plan'

// Storage Account for Function App
resource storageAccount 'Microsoft.Storage/storageAccounts@2021-09-01' = {
  name: storageAccountName
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    supportsHttpsTrafficOnly: true
    minimumTlsVersion: 'TLS1_2'
  }
}

// Application Insights
resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    Request_Source: 'rest'
  }
}

// Consumption Plan for Function App
resource hostingPlan 'Microsoft.Web/serverfarms@2021-03-01' = {
  name: hostingPlanName
  location: location
  sku: {
    name: 'Y1'
    tier: 'Dynamic'
  }
  properties: {
    reserved: true // Linux
  }
}

// Function App with system-assigned managed identity
resource functionApp 'Microsoft.Web/sites@2021-03-01' = {
  name: functionAppName
  location: location
  kind: 'functionapp,linux'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: hostingPlan.id
    siteConfig: {
      linuxFxVersion: 'Python|3.9'
      appSettings: [
        {
          name: 'AzureWebJobsStorage'
          value: 'DefaultEndpointsProtocol=https;AccountName=${storageAccount.name};EndpointSuffix=${environment().suffixes.storage};AccountKey=${storageAccount.listKeys().keys[0].value}'
        }
        {
          name: 'WEBSITE_CONTENTAZUREFILECONNECTIONSTRING'
          value: 'DefaultEndpointsProtocol=https;AccountName=${storageAccount.name};EndpointSuffix=${environment().suffixes.storage};AccountKey=${storageAccount.listKeys().keys[0].value}'
        }
        {
          name: 'WEBSITE_CONTENTSHARE'
          value: toLower(functionAppName)
        }
        {
          name: 'FUNCTIONS_EXTENSION_VERSION'
          value: '~${functionRuntimeVersion}'
        }
        {
          name: 'FUNCTIONS_WORKER_RUNTIME'
          value: 'python'
        }
        {
          name: 'APPINSIGHTS_INSTRUMENTATIONKEY'
          value: appInsights.properties.InstrumentationKey
        }
        {
          name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
          value: appInsights.properties.ConnectionString
        }
        {
          name: 'ALLOWED_EMAILS'
          value: allowedEmails
        }
        {
          name: 'DRY_RUN'
          value: dryRun
        }
        {
          name: 'BACKEND_MODE'
          value: 'vm'
        }
        {
          name: 'AZURE_SUBSCRIPTION_ID'
          value: subscription().subscriptionId
        }
        {
          name: 'AZURE_RESOURCE_GROUP'
          value: resourceGroup().name
        }
      ]
    }
    httpsOnly: true
  }
}

// Static Web App
resource staticWebApp 'Microsoft.Web/staticSites@2021-03-01' = {
  name: staticWebAppName
  location: location
  sku: {
    name: swaSku
    tier: swaSku
  }
  properties: {}
}

// Role assignment: Virtual Machine Contributor for Function App identity
resource vmContributorRole 'Microsoft.Authorization/roleAssignments@2020-04-01-preview' = {
  name: guid(resourceGroup().id, functionApp.id, 'VirtualMachineContributor')
  scope: resourceGroup()
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '9980e02c-c2be-4d73-94e8-173b1dc7cf3c') // Virtual Machine Contributor
    principalId: functionApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// Role assignment: Network Contributor for Function App identity
resource networkContributorRole 'Microsoft.Authorization/roleAssignments@2020-04-01-preview' = {
  name: guid(resourceGroup().id, functionApp.id, 'NetworkContributor')
  scope: resourceGroup()
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4d97b98b-1d4f-4787-a291-c67834d212e7') // Network Contributor
    principalId: functionApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// Outputs
output functionAppName string = functionApp.name
output functionAppHostName string = functionApp.properties.defaultHostName
output staticWebAppName string = staticWebApp.name
output staticWebAppResourceId string = staticWebApp.id
output staticWebAppDefaultHostName string = staticWebApp.properties.defaultHostname
output customVmImageConfigured bool = !empty(customVmImageId)
output customVmImageId string = customVmImageId
