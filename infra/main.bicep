// ============================================================================
// MIGRATION NOTE: This Bicep template has been updated for SWA Functions migration
// ============================================================================
// The Function App, Storage Account, and related resources are now DISABLED
// as the application has migrated to Azure Static Web Apps with built-in Functions.
//
// Rationale:
// - Azure Static Web Apps (SWA) now provides built-in Python Functions
// - No separate Function App or Storage Account needed
// - Simpler deployment and lower cost
// - Single resource instead of multiple resources
//
// IMPORTANT: VM Provisioning Requirements
// - SWA Functions do NOT support Managed Identity
// - You must create a Service Principal with VM Contributor role
// - Store credentials in SWA Application Settings:
//   * AZURE_CLIENT_ID (Service Principal app ID)
//   * AZURE_CLIENT_SECRET (Service Principal password)
//   * AZURE_TENANT_ID (Azure AD tenant ID)
//   * AZURE_SUBSCRIPTION_ID
//   * AZURE_RESOURCE_GROUP
//
// To create the Service Principal:
//   az ad sp create-for-rbac \
//     --name wireguard-spa-vm-provisioner \
//     --role "Virtual Machine Contributor" \
//     --scopes /subscriptions/<SUBSCRIPTION_ID>/resourceGroups/<RG_NAME>
//
// To remove old resources from an existing deployment:
// 1. Delete the Function App, Storage Account, and Hosting Plan via Azure Portal or CLI
// 2. Deploy this updated template (resources below are commented out)
//
// If you need to revert to the old architecture:
// 1. Uncomment the resources below
// 2. Redeploy the template
// 3. Use the old backend/ directory and workflows from git history
// ============================================================================

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

// Generate unique names
var staticWebAppName = '${projectName}-swa'

// ============================================================================
// DISABLED: Function App and related resources
// ============================================================================
// The following resources are commented out as part of the migration to
// Azure Static Web Apps with built-in Functions:
//
// - Storage Account (was: storageAccount)
// - Application Insights (was: appInsights)
// - Hosting Plan (was: hostingPlan)
// - Function App (was: functionApp)
// - VM Contributor Role Assignment (was: vmContributorRole for Function App MI)
// - Network Contributor Role Assignment (was: networkContributorRole for Function App MI)
//
// These are no longer needed because:
// - SWA built-in Functions don't require a separate Function App
// - No Azure Storage needed for state management (using in-memory store)
// - VM permissions now granted to a Service Principal (configured separately)
// ============================================================================

/*
// Commented out - no longer needed with SWA built-in Functions
var uniqueSuffix = uniqueString(resourceGroup().id)
var storageAccountName = '${projectName}${uniqueSuffix}'
var appInsightsName = '${projectName}-appinsights'
var functionAppName = '${projectName}-func'
var hostingPlanName = '${projectName}-plan'

resource storageAccount 'Microsoft.Storage/storageAccounts@2021-09-01' = { ... }
resource appInsights 'Microsoft.Insights/components@2020-02-02' = { ... }
resource hostingPlan 'Microsoft.Web/serverfarms@2021-03-01' = { ... }
resource functionApp 'Microsoft.Web/sites@2021-03-01' = { ... }
resource vmContributorRole 'Microsoft.Authorization/roleAssignments@2020-04-01-preview' = { ... }
resource networkContributorRole 'Microsoft.Authorization/roleAssignments@2020-04-01-preview' = { ... }
*/

// ============================================================================
// ACTIVE: Static Web App (with built-in Functions)
// ============================================================================

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

// ============================================================================
// Outputs
// ============================================================================

output staticWebAppName string = staticWebApp.name
output staticWebAppResourceId string = staticWebApp.id
output staticWebAppDefaultHostName string = staticWebApp.properties.defaultHostname

// ============================================================================
// Post-Deployment Configuration Required
// ============================================================================
// After deploying this template, you must:
//
// 1. Create a Service Principal for VM provisioning:
//    az ad sp create-for-rbac \
//      --name wireguard-spa-vm-provisioner \
//      --role "Virtual Machine Contributor" \
//      --scopes /subscriptions/<SUBSCRIPTION_ID>/resourceGroups/<RG_NAME>
//
// 2. Configure SWA Application Settings with the Service Principal credentials
//
// 3. Set up SWA authentication (Google, Microsoft, etc.)
//
// 4. Deploy the application code via GitHub Actions
// ============================================================================
