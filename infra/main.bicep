// ============================================================================
// WireGuard On-Demand VPN Infrastructure
// ============================================================================
// This template deploys:
// - Azure Static Web App (with built-in Python Functions)
//   - Hosts the QR code page for WireGuard configuration
//   - Provides API endpoints for VM provisioning
//
// VM Provisioning (done via API):
// - VMs are created on-demand via the SWA Functions API
// - Auto-shutdown is configured for 30 minutes after creation
// - Uses Ubuntu 22.04 LTS with WireGuard
//
// Required GitHub Secrets:
// - AZURE_CLIENT_ID: Service Principal application ID
// - AZURE_SECRET: Service Principal password
// - AZURE_TENANT_ID: Azure AD tenant ID
// - AZURE_SUBSCRIPTION_ID: Azure subscription ID
//
// Access Control:
// - Restricted to awwsawws@gmail.com via SWA role-based auth
// ============================================================================

@description('Location for all resources. Defaults to West Europe for optimal performance.')
param location string = 'westeurope'

@description('Project name used as prefix for resource names')
param projectName string = 'wireguard-vpn'

@description('SKU for Static Web App')
@allowed([
  'Free'
  'Standard'
])
param swaSku string = 'Free'

// Generate unique names
var staticWebAppName = '${projectName}-swa'

// ============================================================================
// Static Web App (with built-in Functions)
// ============================================================================

resource staticWebApp 'Microsoft.Web/staticSites@2022-09-01' = {
  name: staticWebAppName
  location: location
  sku: {
    name: swaSku
    tier: swaSku
  }
  properties: {
    stagingEnvironmentPolicy: 'Enabled'
    allowConfigFileUpdates: true
    buildProperties: {
      skipGithubActionWorkflowGeneration: true
    }
  }
  tags: {
    purpose: 'wireguard-vpn'
    'auto-cleanup': 'true'
  }
}

// ============================================================================
// Outputs
// ============================================================================

output staticWebAppName string = staticWebApp.name
output staticWebAppResourceId string = staticWebApp.id
output staticWebAppDefaultHostName string = staticWebApp.properties.defaultHostname

// ============================================================================
// Post-Deployment Notes
// ============================================================================
// After deploying this template:
//
// 1. Configure SWA Application Settings (done via workflow):
//    - AZURE_SUBSCRIPTION_ID
//    - AZURE_RESOURCE_GROUP  
//    - AZURE_CLIENT_ID
//    - AZURE_CLIENT_SECRET
//    - AZURE_TENANT_ID
//    - DRY_RUN (true/false)
//    - ALLOWED_EMAIL (awwsawws@gmail.com)
//
// 2. Configure Authentication in Azure Portal:
//    - Enable Google authentication
//    - Go to Role Management → Invite awwsawws@gmail.com to 'invited' role
//
// 3. VM Auto-Shutdown:
//    - VMs created via API will have 30-minute auto-shutdown configured
//    - This is handled by the vm_provisioner.py code
// ============================================================================
