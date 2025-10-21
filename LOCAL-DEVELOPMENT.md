# Local Development

## Quick Start

From a vanilla Codespace:

```bash
# Install SWA CLI
npm install -g @azure/static-web-apps-cli

# Enable dry run mode for testing without Azure costs
echo '{"IsEncrypted": false, "Values": {"AzureWebJobsStorage": "", "FUNCTIONS_WORKER_RUNTIME": "python", "AzureWebJobsFeatureFlags": "EnableWorkerIndexing", "DRY_RUN": "true"}}' > api/local.settings.json

# Start development server
swa start ./frontend/public/ --api-location ./api/ --api-port 7072
```

## Dry Run Mode

Dry run mode simulates VPN provisioning without creating real Azure resources:

- **No Azure costs** - test the complete user experience for free
- **Realistic timing** - simulates actual provisioning delays (Creating → Running → Completed)
- **Sample config** - returns working WireGuard configuration for testing
- **No auth required** - bypasses authentication for local development

Configure in `api/local.settings.json`:
```json
{
  "IsEncrypted": false,
  "Values": {
    "DRY_RUN": "true"
  }
}
```

## Access

- **Frontend**: http://localhost:4280
- **API**: http://localhost:7072

## Development Notes

- **Hot reload**: Python and HTML/JS changes reload automatically
- **Port conflicts**: Use `--api-port 7072` to avoid "Port 7071 unavailable" errors

## Testing API

```bash
# Start VPN provisioning
curl -X POST http://localhost:4280/api/start_job -H "Content-Type: application/json" -d '{}'

# Check status (use operationId from above)
curl http://localhost:4280/api/job_status?id={operationId}
```

## Troubleshooting

- **Port conflicts**: `pkill -f "swa\|func"` then restart
- **API not responding**: Check if SWA server is running with `ps aux | grep swa`
- **Authentication errors**: Ensure `DRY_RUN=true` in `local.settings.json`