# Quick Fix Guide - Authorization Error

## 🔴 Problem
The workflow is failing with:
```
Authorization failed for template resource of type 'Microsoft.Authorization/roleAssignments'.
The client does not have permission to perform action 'Microsoft.Authorization/roleAssignments/write'
```

## 🎯 Solution
The service principal needs **User Access Administrator** role in addition to Contributor.

## 🚀 Quick Fix (5 minutes)

### Step 1: Get your service principal's Application ID

1. Go to your GitHub repository → Settings → Secrets and variables → Actions
2. View the `AZURE_CREDENTIALS` secret (you can't see it, so you may need to recreate it)
3. The secret looks like this:
   ```json
   {
     "clientId": "abc123...",  ← This is your Application ID
     "clientSecret": "...",
     "subscriptionId": "...",
     "tenantId": "..."
   }
   ```

### Step 2: Grant the required role

Replace the placeholders and run this command in Azure Cloud Shell or Azure CLI:

```bash
# Replace these values
SP_APP_ID="<your-clientId-from-step-1>"
RESOURCE_GROUP="wireguard-spa-rg"

# Grant User Access Administrator role
az role assignment create \
  --assignee "$SP_APP_ID" \
  --role "User Access Administrator" \
  --resource-group "$RESOURCE_GROUP"
```

### Step 3: Re-run the workflow

1. Go to Actions → Provision Infrastructure and Deploy
2. Click "Re-run all jobs"
3. The workflow should now succeed! ✅

## 📚 For More Details

- See [PERMISSIONS.md](PERMISSIONS.md) for comprehensive documentation
- See [AUTH_ERROR_FIX_SUMMARY.md](AUTH_ERROR_FIX_SUMMARY.md) for technical details

## ❓ Alternative: Use Owner Role

If you prefer to grant full access (not recommended for production):

```bash
az role assignment create \
  --assignee "$SP_APP_ID" \
  --role "Owner" \
  --resource-group "$RESOURCE_GROUP"
```

## 🔍 What Changed?

The workflow now includes:
- **Permission check step** - Detects auth issues before deployment
- **Better error messages** - Clear guidance when permissions are missing
- **What-if analysis** - Tests deployment without making changes

These additions help diagnose permission issues early and provide actionable fixes.
