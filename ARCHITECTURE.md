# WireGuard SPA - Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                          GitHub Actions                              │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  Provision Infrastructure and Deploy Workflow                 │   │
│  │  • Creates Azure Resources (Bicep)                            │   │
│  │  • Deploys Backend (Functions)                                │   │
│  │  • Deploys Frontend (SWA)                                     │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ Deploys to
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          Azure Cloud                                 │
│                                                                       │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │  Azure Static Web App (Frontend)                           │     │
│  │  ┌──────────────────────────────────────────────────────┐  │     │
│  │  │  Vue.js SPA                                          │  │     │
│  │  │  • Authentication (Google, Microsoft)                │  │     │
│  │  │  • Session Management UI                             │  │     │
│  │  │  • Status Monitoring                                 │  │     │
│  │  └──────────────────────────────────────────────────────┘  │     │
│  │                           │                                 │     │
│  │                           │ /.auth/login                    │     │
│  │                           ▼                                 │     │
│  │  ┌──────────────────────────────────────────────────────┐  │     │
│  │  │  Built-in Authentication                             │  │     │
│  │  │  • Google OAuth                                      │  │     │
│  │  │  • Azure AD (Microsoft)                              │  │     │
│  │  └──────────────────────────────────────────────────────┘  │     │
│  └────────────────────────────────────────────────────────────┘     │
│                           │                                           │
│                           │ /api/* (authenticated)                    │
│                           ▼                                           │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │  Azure Functions (Backend)                                 │     │
│  │  ┌──────────────────────────────────────────────────────┐  │     │
│  │  │  HTTP Triggers                                       │  │     │
│  │  │  • StartSession: POST /api/start                     │  │     │
│  │  │  • GetStatus: GET /api/status                        │  │     │
│  │  └──────────────────────────────────────────────────────┘  │     │
│  │                           │                                 │     │
│  │                           │ Validates user                  │     │
│  │                           ▼                                 │     │
│  │  ┌──────────────────────────────────────────────────────┐  │     │
│  │  │  Durable Functions Orchestrator                      │  │     │
│  │  │  • WireGuardOrchestrator                             │  │     │
│  │  │    ├─> ProvisionVM (Activity)                        │  │     │
│  │  │    ├─> Wait (Timer)                                  │  │     │
│  │  │    └─> DestroyVM (Activity)                          │  │     │
│  │  └──────────────────────────────────────────────────────┘  │     │
│  │                           │                                 │     │
│  │                           │ Uses Managed Identity           │     │
│  │                           ▼                                 │     │
│  │  ┌──────────────────────────────────────────────────────┐  │     │
│  │  │  System-assigned Managed Identity                    │  │     │
│  │  │  • VM Contributor Role                               │  │     │
│  │  │  • Network Contributor Role                          │  │     │
│  │  └──────────────────────────────────────────────────────┘  │     │
│  └────────────────────────────────────────────────────────────┘     │
│                           │                                           │
│                           │ Creates/Destroys                          │
│                           ▼                                           │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │  Ephemeral Azure VMs (WireGuard Instances)                 │     │
│  │  • Ubuntu 18.04 LTS                                        │     │
│  │  • B1s (Standard)                                          │     │
│  │  • WireGuard Configured                                    │     │
│  │  • Auto-destroyed after session timeout                    │     │
│  └────────────────────────────────────────────────────────────┘     │
│                                                                       │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │  Supporting Resources                                      │     │
│  │  • Application Insights (Monitoring)                       │     │
│  │  • Storage Account (Functions Runtime)                     │     │
│  │  • Virtual Networks (VMs)                                  │     │
│  │  • Public IPs (VMs)                                        │     │
│  │  • Network Interfaces (VMs)                                │     │
│  └────────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────┘
```

## Component Interaction Flow

### 1. User Authentication Flow

```
User                    SWA                     Auth Provider
  │                      │                            │
  ├──────────────────────>│                            │
  │  Click "Sign in"     │                            │
  │                      │                            │
  │                      ├───────────────────────────>│
  │                      │  Redirect to Provider      │
  │                      │                            │
  │<─────────────────────┤                            │
  │  Redirect to Auth    │                            │
  │                      │                            │
  ├──────────────────────┼───────────────────────────>│
  │                      │  Authenticate              │
  │                      │                            │
  │<─────────────────────┼────────────────────────────┤
  │  Auth Token          │                            │
  │                      │                            │
  ├──────────────────────>│                            │
  │  Redirect back       │                            │
  │                      │                            │
  │<─────────────────────┤                            │
  │  Authenticated       │                            │
  │  Cookie Set          │                            │
```

### 2. Session Creation Flow

```
Frontend                Backend                  Azure API
  │                       │                          │
  ├──────────────────────>│                          │
  │  POST /api/start      │                          │
  │  {duration: 3600}     │                          │
  │                       │                          │
  │                       ├─ Validate User           │
  │                       │  (check ALLOWED_EMAILS)  │
  │                       │                          │
  │                       ├─ Start Orchestration    │
  │                       │  (Durable Functions)     │
  │                       │                          │
  │                       ├─────────────────────────>│
  │                       │  Create VM               │
  │                       │  • VNet                  │
  │                       │  • Public IP             │
  │                       │  • NIC                   │
  │                       │  • VM Instance           │
  │                       │                          │
  │                       │<─────────────────────────┤
  │                       │  VM Created              │
  │                       │  {public_ip: "1.2.3.4"} │
  │                       │                          │
  │<──────────────────────┤                          │
  │  {instanceId: "..."}  │                          │
  │                       │                          │
  │                       ├─ Schedule Timer          │
  │                       │  (duration seconds)      │
```

### 3. Status Monitoring Flow

```
Frontend                Backend                  Orchestration
  │                       │                          │
  ├──────────────────────>│                          │
  │  GET /api/status      │                          │
  │  ?instanceId=...      │                          │
  │                       │                          │
  │                       ├─ Validate User           │
  │                       │                          │
  │                       ├─────────────────────────>│
  │                       │  Query Status            │
  │                       │                          │
  │                       │<─────────────────────────┤
  │                       │  {status: "Running",     │
  │                       │   output: {...}}         │
  │                       │                          │
  │<──────────────────────┤                          │
  │  Status Response      │                          │
  │                       │                          │
  ├─ Wait 5 seconds       │                          │
  │                       │                          │
  ├──────────────────────>│                          │
  │  GET /api/status      │                          │
  │  (repeat)             │                          │
```

### 4. Session Cleanup Flow

```
Orchestrator            Backend                  Azure API
  │                       │                          │
  ├─ Timer Expires        │                          │
  │                       │                          │
  ├──────────────────────>│                          │
  │  Call DestroyVM       │                          │
  │  Activity             │                          │
  │                       │                          │
  │                       ├─────────────────────────>│
  │                       │  Delete VM               │
  │                       │                          │
  │                       ├─────────────────────────>│
  │                       │  Delete NIC              │
  │                       │                          │
  │                       ├─────────────────────────>│
  │                       │  Delete Public IP        │
  │                       │                          │
  │                       ├─────────────────────────>│
  │                       │  Delete VNet             │
  │                       │                          │
  │                       │<─────────────────────────┤
  │                       │  Resources Deleted       │
  │                       │                          │
  │<──────────────────────┤                          │
  │  Cleanup Complete     │                          │
```

## Security Architecture

### Authentication & Authorization

```
┌─────────────────────────────────────────────────────────┐
│  Security Layers                                        │
│                                                         │
│  1. Network Layer                                       │
│     • HTTPS Only                                        │
│     • TLS 1.2+                                          │
│                                                         │
│  2. Authentication Layer                                │
│     • Azure Static Web Apps Built-in Auth               │
│     • OAuth 2.0 (Google, Microsoft)                     │
│     • Session Cookies (HttpOnly, Secure)                │
│                                                         │
│  3. Authorization Layer                                 │
│     • Email-based Whitelist (ALLOWED_EMAILS)            │
│     • Validated on every API request                    │
│     • No role-based access (future enhancement)         │
│                                                         │
│  4. Azure Resource Access                               │
│     • System-assigned Managed Identity                  │
│     • Least-privilege RBAC:                             │
│       - VM Contributor (Resource Group scope)           │
│       - Network Contributor (Resource Group scope)      │
│     • No credential storage required                    │
│                                                         │
│  5. Secrets Management                                  │
│     • No secrets in code                                │
│     • App Settings for configuration                    │
│     • GitHub Secrets for CI/CD                          │
│     • Managed Identity for Azure access                 │
└─────────────────────────────────────────────────────────┘
```

## Data Flow

### Request-Response Lifecycle

```
1. User Request
   ├─> Frontend validates auth state
   ├─> Sends request to /api/* endpoint
   └─> Includes authentication cookie

2. API Gateway (Static Web App)
   ├─> Validates authentication cookie
   ├─> Extracts user principal
   ├─> Adds x-ms-client-principal header
   └─> Routes to Function App

3. Function App
   ├─> Receives request with user principal
   ├─> Validates user email against ALLOWED_EMAILS
   ├─> Processes request (start/status)
   └─> Returns response

4. Durable Functions (for start)
   ├─> Creates orchestration instance
   ├─> Calls ProvisionVM activity
   ├─> Waits for duration
   ├─> Calls DestroyVM activity
   └─> Completes orchestration

5. Azure Resource Management (Managed Identity)
   ├─> Uses Function App managed identity
   ├─> Creates/Deletes VM resources
   ├─> Validates RBAC permissions
   └─> Returns operation results
```

## Deployment Architecture

### Infrastructure as Code Flow

```
GitHub Repo                  Azure                      Resources
    │                          │                            │
    ├─> Trigger Workflow       │                            │
    │   (Push to main or       │                            │
    │    manual dispatch)      │                            │
    │                          │                            │
    ├─────────────────────────>│                            │
    │  Azure Login             │                            │
    │  (Service Principal)     │                            │
    │                          │                            │
    ├─────────────────────────>│                            │
    │  Deploy Bicep Template   │                            │
    │                          │                            │
    │                          ├───────────────────────────>│
    │                          │  Create/Update:            │
    │                          │  • Storage Account         │
    │                          │  • App Insights            │
    │                          │  • Function App            │
    │                          │  • Static Web App          │
    │                          │  • RBAC Assignments        │
    │                          │                            │
    │                          │<───────────────────────────┤
    │                          │  Deployment Complete       │
    │<─────────────────────────┤  (Outputs)                 │
    │  Extract Outputs         │                            │
    │                          │                            │
    ├─────────────────────────>│                            │
    │  Deploy Functions        │                            │
    │  (Package backend/)      │                            │
    │                          │                            │
    ├─────────────────────────>│                            │
    │  Deploy SWA              │                            │
    │  (Build frontend/)       │                            │
```

## Scalability & Performance

### Resource Scaling

```
Component              Scaling Strategy              Limits
─────────────────────────────────────────────────────────────
Static Web App         Auto-scaling                  N/A
                       (CDN-backed)                  

Function App           Consumption Plan              200 instances
                       (Dynamic)                     (default)
                       
Durable Functions      Per-orchestration             Thousands of
                       scaling                       concurrent

VMs                    One per session               Subscription
                       (short-lived)                 quota limits

Storage                Auto-scaling                  Account limits
                       (Queue/Table)                 
```

### Performance Characteristics

```
Operation              Latency       Notes
──────────────────────────────────────────────────────
Frontend Load          < 2s          CDN-cached
Authentication         < 3s          OAuth redirect
Start Session          < 5s          Orchestration start
VM Provisioning        2-5 min       Azure VM creation
Status Check           < 500ms       Queue query
VM Destruction         1-3 min       Resource cleanup
```

## Monitoring & Observability

### Telemetry Flow

```
Application           Application Insights         Monitoring
    │                          │                        │
    ├─> Traces                 │                        │
    │   (Function logs)         │                        │
    │                          │                        │
    ├─> Metrics                │                        │
    │   (Performance)           │                        │
    │                          │                        │
    ├─> Dependencies           │                        │
    │   (Azure API calls)       │                        │
    │                          │                        │
    └─────────────────────────>│                        │
                               │                        │
                               ├─> Aggregation          │
                               │   (Time-series)        │
                               │                        │
                               ├─> Alerting             │
                               │   (Thresholds)         │
                               │                        │
                               └───────────────────────>│
                                                    Dashboard
```

## Cost Optimization

### Resource Costs (Approximate)

```
Resource              Tier              Monthly Cost (est.)
──────────────────────────────────────────────────────────
Static Web App        Free              $0
Function App          Consumption       $5-20 (usage-based)
Storage Account       Standard LRS      $1-5
Application Insights  Basic             $2-10
VM (per session)      B1s               $0.01-0.02/hour
VNet/IP/NIC          Standard          Minimal (<$5)
───────────────────────────────────────────────────────────
Total (baseline)                        $8-40/month
+ VM usage                              Varies by sessions
```

### Cost Control Strategies

1. **Ephemeral VMs**: Destroyed after session timeout
2. **Consumption Plan**: Pay only for Function execution
3. **Free SWA Tier**: No cost for hosting
4. **B1s VMs**: Smallest instance for cost efficiency
5. **Short Sessions**: Limit max duration to control VM costs
6. **Dry Run Mode**: Test without creating actual resources

## Future Architecture Enhancements

1. **Multi-region deployment** for lower latency
2. **VM pool** for faster provisioning
3. **Custom domain** support
4. **Advanced RBAC** with role-based access
5. **Key Vault integration** for secrets management
6. **Premium Functions** for lower cold-start latency
7. **VPN Gateway** as alternative to VMs
8. **Container support** if WireGuard in ACI becomes viable
9. **Terraform option** alongside Bicep
10. **ARM template export** for other deployment tools
