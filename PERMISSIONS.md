# Azure Service Principal Permissions

## Required Permissions

The Azure service principal used in the GitHub Actions workflow requires specific permissions to deploy the WireGuard SPA infrastructure.

### Minimum Required Roles

The service principal needs **both** of the following roles at the Resource Group level:

1. **Contributor** - To create and manage Azure resources
2. **User Access Administrator** - To create role assignments for managed identities

**OR**

1. **Owner** - Provides both resource management and role assignment capabilities

### Why These Permissions Are Needed

The Bicep infrastructure template (`infra/main.bicep`) creates:
- Azure Function App with a system-assigned managed identity
- Role assignments that grant the Function App identity permissions to:
  - **Virtual Machine Contributor** - To create and manage VMs for WireGuard
  - **Network Contributor** - To create and manage virtual networks

Creating role assignments requires `Microsoft.Authorization/roleAssignments/write` permission, which is only available with the **User Access Administrator** or **Owner** role.

## Setting Up Permissions

### Option 1: Grant User Access Administrator (Recommended)

This provides the minimum permissions needed:

```bash
# Get your service principal's application ID
SP_APP_ID="<your-service-principal-app-id>"

# Get your resource group name
RESOURCE_GROUP="wireguard-spa-rg"

# Grant Contributor role (if not already assigned)
az role assignment create \
  --assignee $SP_APP_ID \
  --role "Contributor" \
  --resource-group $RESOURCE_GROUP

# Grant User Access Administrator role
az role assignment create \
  --assignee $SP_APP_ID \
  --role "User Access Administrator" \
  --resource-group $RESOURCE_GROUP
```

### Option 2: Grant Owner Role

This provides full access to the resource group:

```bash
# Get your service principal's application ID
SP_APP_ID="<your-service-principal-app-id>"

# Get your resource group name
RESOURCE_GROUP="wireguard-spa-rg"

# Grant Owner role
az role assignment create \
  --assignee $SP_APP_ID \
  --role "Owner" \
  --resource-group $RESOURCE_GROUP
```

### Finding Your Service Principal Application ID

Your service principal's application ID can be found in the `AZURE_CREDENTIALS` secret in your GitHub repository. The secret is a JSON object that looks like:

```json
{
  "clientId": "<application-id>",
  "clientSecret": "<secret>",
  "subscriptionId": "<subscription-id>",
  "tenantId": "<tenant-id>"
}
```

The `clientId` field is your service principal's application ID.

## Verifying Permissions

The workflow includes a "Check Azure Service Principal Permissions" step that:
- Lists current role assignments
- Tests deployment permissions using `az deployment group what-if`
- Provides detailed error messages if permissions are insufficient

## Troubleshooting

### Error: "does not have permission to perform action 'Microsoft.Authorization/roleAssignments/write'"

This error means the service principal lacks the ability to create role assignments. Follow the steps in "Setting Up Permissions" above.

### Error: "Authorization failed for template resource of type 'Microsoft.Authorization/roleAssignments'"

This is the same as the above error, indicating missing role assignment permissions.

## Security Best Practices

1. **Scope Permissions**: Assign roles at the Resource Group level, not at the Subscription level, to follow the principle of least privilege
2. **Review Regularly**: Periodically review and audit role assignments
3. **Rotate Credentials**: Regularly rotate service principal credentials
4. **Use Managed Identities**: The infrastructure uses managed identities for the Function App to avoid storing credentials
