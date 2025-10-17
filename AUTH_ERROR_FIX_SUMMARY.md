# Authentication Error Fix - Summary

## Problem Identified

The GitHub Actions workflow was failing with an authorization error:
```
Authorization failed for template resource of type 'Microsoft.Authorization/roleAssignments'. 
The client does not have permission to perform action 'Microsoft.Authorization/roleAssignments/write'
```

## Root Cause

The Bicep infrastructure template (`infra/main.bicep`) creates role assignments to grant the Function App's managed identity the following permissions:
- **Virtual Machine Contributor** - To create and manage VMs for WireGuard
- **Network Contributor** - To create and manage virtual networks

Creating role assignments requires `Microsoft.Authorization/roleAssignments/write` permission, which is only available with:
- **Owner** role, OR
- **User Access Administrator** role (in addition to Contributor)

The service principal configured in `AZURE_CREDENTIALS` only had the **Contributor** role, which cannot create role assignments.

## Solution Implemented

### 1. Added Permission Check Step to Workflow
- New step: "Check Azure Service Principal Permissions"
- Runs **before** the Bicep deployment
- Uses `az deployment group what-if` to test permissions without actually deploying
- Detects authorization errors early and provides clear guidance

### 2. Enhanced Deployment Error Handling
- Modified the "Deploy Bicep Infrastructure" step
- Captures deployment errors and checks for authorization issues
- Provides specific commands to fix the permission problem
- References the new PERMISSIONS.md documentation

### 3. Created Comprehensive Documentation
- **PERMISSIONS.md** - Detailed guide on:
  - Required permissions and why they're needed
  - Step-by-step setup instructions
  - Troubleshooting common errors
  - Security best practices
  
### 4. Updated Existing Documentation
- **README.md** - Added permission requirements to Quick Start
- **SETUP.md** - Updated service principal creation with correct roles

## How to Fix the Current Error

To resolve the authorization error, the service principal needs the **User Access Administrator** role:

```bash
# Get the service principal's application ID from AZURE_CREDENTIALS secret
# The clientId field in the JSON is the application ID

SP_APP_ID="<your-service-principal-app-id>"
RESOURCE_GROUP="wireguard-spa-rg"
SUBSCRIPTION_ID="<your-subscription-id>"

# Grant User Access Administrator role
az role assignment create \
  --assignee "$SP_APP_ID" \
  --role "User Access Administrator" \
  --scope "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP"
```

Alternatively, grant the **Owner** role for full access:

```bash
az role assignment create \
  --assignee "$SP_APP_ID" \
  --role "Owner" \
  --scope "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP"
```

## Testing

The changes have been validated:
- ✅ YAML syntax is valid
- ✅ Permission check logic correctly detects authorization errors
- ✅ Deployment error handling provides clear guidance
- ✅ Documentation is comprehensive and actionable

## Next Steps

1. **Apply the fix**: Grant the service principal the required permissions using the commands above
2. **Re-run the workflow**: The deployment should succeed once permissions are granted
3. **Verify**: Check that the Function App managed identity has the correct role assignments

## Files Changed

- `.github/workflows/infra-provision-and-deploy.yml` - Added permission checks and error handling
- `PERMISSIONS.md` - New comprehensive permissions documentation
- `README.md` - Updated with permission requirements
- `SETUP.md` - Updated service principal setup instructions
