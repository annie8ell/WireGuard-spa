# Azure Deployment Fix - Resource Provider Registration

## Problem
The GitHub Actions workflow for infrastructure provisioning was failing with the following error:

```
ERROR: "status":"Failed","error":{"code":"DeploymentFailed",
"message":"At least one resource deployment operation failed.",
"details":[{"code":"Conflict",
"message":"Failed to register resource provider 'microsoft.operationalinsights'. 
Ensure that microsoft.operationalinsights is registered for this subscription."}]}
```

## Root Cause
The Bicep template (`infra/main.bicep`) creates Azure resources that depend on certain Azure resource providers being registered in the subscription:

1. **Application Insights** (`Microsoft.Insights/components`) - requires:
   - `Microsoft.Insights` resource provider
   - `Microsoft.OperationalInsights` resource provider (for workspace dependencies)

2. **Function Apps and Static Web Apps** - requires:
   - `Microsoft.Web` resource provider

3. **Storage Accounts** - requires:
   - `Microsoft.Storage` resource provider

These resource providers were not automatically registered in the Azure subscription, causing the deployment to fail.

## Solution Implemented

### 1. Added Resource Provider Registration Step
Added a new step in `.github/workflows/infra-provision-and-deploy.yml` that explicitly registers all required Azure resource providers before the Bicep deployment:

```yaml
- name: Register Required Azure Resource Providers
  run: |
    set -euo pipefail
    echo "Registering required Azure resource providers..."
    
    # Register Microsoft.Insights for Application Insights
    echo "Registering Microsoft.Insights..."
    az provider register --namespace Microsoft.Insights --wait
    
    # Register Microsoft.OperationalInsights for Application Insights workspace dependencies
    echo "Registering Microsoft.OperationalInsights..."
    az provider register --namespace Microsoft.OperationalInsights --wait
    
    # Register Microsoft.Web for Function Apps and Static Web Apps
    echo "Registering Microsoft.Web..."
    az provider register --namespace Microsoft.Web --wait
    
    # Register Microsoft.Storage for Storage Accounts
    echo "Registering Microsoft.Storage..."
    az provider register --namespace Microsoft.Storage --wait
    
    echo "All required resource providers registered successfully."
```

**Key points:**
- Uses `--wait` flag to ensure registration completes before proceeding
- Registers all providers needed by the Bicep template
- Positioned after resource group creation but before Bicep deployment
- Idempotent - safe to run multiple times

### 2. Enhanced Error Diagnostics
Enhanced the deployment step to provide detailed error information when deployment fails:

```yaml
# Attempt deployment and capture result
if ! OUTPUT=$(az deployment group create \
  --resource-group "${{ env.RESOURCE_GROUP }}" \
  --template-file infra/main.bicep \
  --parameters projectName=${{ env.PROJECT_NAME }} location=${{ env.LOCATION }} \
  --query 'properties.outputs' -o json 2>&1); then
  
  echo "ERROR: Bicep deployment failed!" >&2
  echo "Error details:" >&2
  echo "$OUTPUT" >&2
  
  echo "" >&2
  echo "Retrieving deployment operation details for diagnostics..." >&2
  
  # Get the most recent deployment name
  DEPLOYMENT_NAME=$(az deployment group list \
    --resource-group "${{ env.RESOURCE_GROUP }}" \
    --query '[0].name' -o tsv 2>/dev/null || echo "main")
  
  echo "Deployment name: $DEPLOYMENT_NAME" >&2
  
  # Show detailed deployment operations
  echo "" >&2
  echo "=== Deployment Operations ===" >&2
  az deployment operation group list \
    --resource-group "${{ env.RESOURCE_GROUP }}" \
    --name "$DEPLOYMENT_NAME" \
    --query '[?properties.provisioningState==`Failed`].[properties.targetResource.resourceType, properties.targetResource.resourceName, properties.statusMessage.error.code, properties.statusMessage.error.message]' \
    -o table 2>&1 || echo "Could not retrieve deployment operations." >&2
  
  exit 1
fi
```

**Benefits:**
- Captures and displays the full error output from Azure CLI
- Retrieves detailed deployment operation information
- Shows which specific resources failed and why
- Makes debugging future deployment issues much easier

## Expected Behavior After Fix

When the workflow runs:

1. ✅ Creates or validates resource group exists
2. ✅ Registers all required Azure resource providers (new step)
3. ✅ Deploys Bicep infrastructure successfully
4. ✅ If deployment fails, provides detailed diagnostic information

## Testing

The changes have been:
- ✅ Syntax validated (YAML is valid)
- ✅ Structure verified (workflow steps are properly ordered)
- ✅ Committed to branch `copilot/fix-deployment-issues`

## Next Steps

1. Merge this PR to the main branch
2. Trigger the "Provision Infrastructure and Deploy" workflow manually
3. Verify that:
   - Resource providers are registered successfully
   - Bicep deployment completes without the previous error
   - All Azure resources are created as expected

## References

- [Azure Resource Provider Registration](https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/resource-providers-and-types)
- [Azure Deployment Operations](https://aka.ms/arm-deployment-operations)
- Failed Workflow Run: https://github.com/annie8ell/WireGuard-spa/actions/runs/18589663604/job/53001592297
