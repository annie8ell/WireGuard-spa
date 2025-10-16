# WireGuard Backend (Azure Functions)

Python-based Azure Functions backend using Durable Functions for orchestrating WireGuard VM lifecycle.

## Structure

```
backend/
├── host.json                      # Azure Functions host configuration
├── requirements.txt               # Python dependencies
├── local.settings.json.template   # Template for local development settings
├── shared/                        # Shared utilities
│   ├── config.py                  # Configuration management
│   ├── auth.py                    # Authentication helpers
│   └── vm_manager.py              # Azure VM management
├── StartSession/                  # HTTP trigger to start VPN session
├── GetStatus/                     # HTTP trigger to get session status
├── WireGuardOrchestrator/         # Durable orchestrator function
├── ProvisionVM/                   # Activity function to create VM
└── DestroyVM/                     # Activity function to destroy VM
```

## Functions

### HTTP Triggers

#### StartSession
- **Route**: `/api/start`
- **Method**: POST
- **Auth**: Requires authenticated user from Static Web App
- **Purpose**: Initiates a new WireGuard session orchestration
- **Request Body**:
  ```json
  {
    "duration": 3600  // Session duration in seconds
  }
  ```
- **Response**:
  ```json
  {
    "instanceId": "abc123...",
    "user_email": "user@example.com",
    "duration": 3600,
    "statusQueryGetUri": "..."
  }
  ```

#### GetStatus
- **Route**: `/api/status`
- **Method**: GET, POST
- **Auth**: Requires authenticated user
- **Purpose**: Gets the status of a running orchestration
- **Query Parameters**: `instanceId` - The orchestration instance ID
- **Response**:
  ```json
  {
    "instanceId": "abc123...",
    "runtimeStatus": "Running",
    "input": {...},
    "output": {...},
    "createdTime": "2025-01-01T00:00:00Z",
    "lastUpdatedTime": "2025-01-01T00:05:00Z"
  }
  ```

### Durable Functions

#### WireGuardOrchestrator
- **Type**: Orchestrator
- **Purpose**: Coordinates VM lifecycle (create → wait → destroy)
- **Flow**:
  1. Calls `ProvisionVM` activity
  2. Waits for specified duration
  3. Calls `DestroyVM` activity

#### ProvisionVM
- **Type**: Activity
- **Purpose**: Creates an Azure VM for WireGuard
- **Input**:
  ```json
  {
    "vm_name": "wireguard-abc123",
    "user_email": "user@example.com"
  }
  ```
- **Output**:
  ```json
  {
    "status": "success",
    "vm_name": "wireguard-abc123",
    "public_ip": "1.2.3.4",
    "user_email": "user@example.com"
  }
  ```

#### DestroyVM
- **Type**: Activity
- **Purpose**: Destroys the VM and associated resources
- **Input**:
  ```json
  {
    "vm_name": "wireguard-abc123"
  }
  ```
- **Output**:
  ```json
  {
    "status": "success",
    "vm_name": "wireguard-abc123"
  }
  ```

## Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `ALLOWED_EMAILS` | Comma-separated list of authorized email addresses | `awwsawws@gmail.com,awwsawws@hotmail.com` | Yes |
| `DRY_RUN` | Enable dry-run mode (no actual VMs created) | `false` | No |
| `BACKEND_MODE` | Backend mode: `vm` or `aci` | `vm` | No |
| `AZURE_SUBSCRIPTION_ID` | Azure subscription ID | - | Yes (for VM mode) |
| `AZURE_RESOURCE_GROUP` | Azure resource group name | - | Yes (for VM mode) |
| `FUNCTIONS_WORKER_RUNTIME` | Functions runtime | `python` | Yes |
| `AzureWebJobsStorage` | Storage connection string | - | Yes |

### local.settings.json

Copy the template and fill in your values:

```bash
cp local.settings.json.template local.settings.json
```

Example `local.settings.json`:
```json
{
  "IsEncrypted": false,
  "Values": {
    "AzureWebJobsStorage": "UseDevelopmentStorage=true",
    "FUNCTIONS_WORKER_RUNTIME": "python",
    "ALLOWED_EMAILS": "your-email@example.com",
    "DRY_RUN": "true",
    "BACKEND_MODE": "vm",
    "AZURE_SUBSCRIPTION_ID": "your-subscription-id",
    "AZURE_RESOURCE_GROUP": "your-resource-group"
  }
}
```

## Local Development

### Prerequisites
- Python 3.9
- Azure Functions Core Tools v4
- Azure CLI (for authentication)

### Setup

1. **Create virtual environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure settings**:
   ```bash
   cp local.settings.json.template local.settings.json
   # Edit local.settings.json with your values
   ```

4. **Login to Azure** (for VM management):
   ```bash
   az login
   ```

5. **Run Functions locally**:
   ```bash
   func start
   ```

The Functions will be available at:
- Start Session: `http://localhost:7071/api/start`
- Get Status: `http://localhost:7071/api/status?instanceId=...`

### Testing Authentication

Since authentication is handled by Static Web Apps, you can test locally by:

1. **Disable auth checks temporarily**: Comment out auth validation in code
2. **Use a tool like Postman**: Add mock auth headers
3. **Deploy to Azure**: Test with real SWA authentication

For local testing, you can modify the auth check to allow any request:

```python
# In shared/auth.py - for LOCAL TESTING ONLY
def validate_user(req):
    # TEMPORARY: Allow all requests for local testing
    return True, "test@example.com", None
```

**Remember to revert this before deploying!**

## Deployment

### Option 1: Using GitHub Actions

Push to `main` branch or trigger the `Deploy Backend` workflow manually.

### Option 2: Using Azure Functions Core Tools

```bash
# Login to Azure
az login

# Publish to Function App
func azure functionapp publish <function-app-name>
```

### Option 3: Using Azure CLI

```bash
# Create deployment package
cd backend
zip -r ../backend.zip .

# Deploy
az functionapp deployment source config-zip \
  --resource-group <resource-group> \
  --name <function-app-name> \
  --src ../backend.zip
```

## Monitoring

### View Logs

```bash
# Stream logs
func azure functionapp logstream <function-app-name>

# Or use Azure CLI
az webapp log tail \
  --resource-group <resource-group> \
  --name <function-app-name>
```

### Application Insights

View detailed telemetry in Azure Portal:
1. Go to your Function App
2. Click **Application Insights**
3. View logs, traces, and performance metrics

## Troubleshooting

### Common Issues

#### Import errors
- Ensure virtual environment is activated
- Install all requirements: `pip install -r requirements.txt`

#### Storage connection errors
- For local development, use Azure Storage Emulator or update connection string
- Check `AzureWebJobsStorage` in `local.settings.json`

#### VM provisioning fails
- Verify Azure credentials are set up (`az login`)
- Check subscription ID and resource group are correct
- Verify managed identity has required RBAC roles (in Azure deployment)
- Try dry-run mode first: `DRY_RUN=true`

#### Orchestration not starting
- Check Durable Functions extension is loaded
- Verify `host.json` has correct extension bundle
- Check Application Insights for detailed errors

### Debug Mode

Enable detailed logging:

```json
// In local.settings.json
{
  "Values": {
    ...
    "logging__logLevel__default": "Debug"
  }
}
```

## Best Practices

1. **Always use dry-run mode first** when testing VM provisioning
2. **Keep secrets out of code** - use environment variables
3. **Test locally** before deploying to Azure
4. **Monitor costs** - ensure VMs are destroyed after sessions
5. **Use managed identities** - avoid storing credentials
6. **Set appropriate timeouts** - balance user experience vs. costs

## Security

- **Authentication**: All HTTP endpoints require authenticated user
- **Authorization**: Email must be in `ALLOWED_EMAILS` list
- **Managed Identity**: Function App uses system-assigned identity for Azure operations
- **RBAC**: Least-privilege roles assigned at resource group scope
- **Secrets**: Never commit `local.settings.json` to source control

## Performance Considerations

- **Consumption Plan**: Cold starts may occur; consider Premium plan for production
- **VM Size**: B1s is cost-effective; upgrade if more resources needed
- **Session Duration**: Balance between user convenience and cost
- **Orchestration Overhead**: Minimal overhead for Durable Functions

## Future Enhancements

- [ ] Add WireGuard configuration generation
- [ ] Implement config distribution to users
- [ ] Add ACI support (if TUN requirement resolved)
- [ ] Add session extension capability
- [ ] Implement cleanup of orphaned resources
- [ ] Add metrics and alerts
- [ ] Support custom VM sizes
- [ ] Add region selection
