# WireGuard SPA - Architecture

> **📝 Migration Note**: This architecture has been updated to reflect the migration from Azure Durable Functions to Azure Static Web Apps built-in Functions. See [MIGRATION.md](MIGRATION.md) for details.

## System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                          GitHub Actions                              │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  Azure Static Web Apps Deploy Workflow                       │   │
│  │  • Single deployment for both SPA and API                     │   │
│  │  • Python 3.11 for built-in Functions                        │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ Deploys to
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Azure Static Web App                            │
│                                                                       │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │  Frontend (SPA)                                            │     │
│  │  ┌──────────────────────────────────────────────────────┐  │     │
│  │  │  Zero-build SPA (Alpine.js + Foundation CSS)         │  │     │
│  │  │  • Authentication UI                                 │  │     │
│  │  │  • Job submission and status polling                 │  │     │
│  │  │  • WireGuard config download                         │  │     │
│  │  └──────────────────────────────────────────────────────┘  │     │
│  │                           │                                 │     │
│  │                           │ /.auth/login                    │     │
│  │                           ▼                                 │     │
│  │  ┌──────────────────────────────────────────────────────┐  │     │
│  │  │  Built-in Authentication                             │  │     │
│  │  │  • Google OAuth                                      │  │     │
│  │  │  • Azure AD (Microsoft)                              │  │     │
│  │  │  • Sets X-MS-CLIENT-PRINCIPAL header                 │  │     │
│  │  └──────────────────────────────────────────────────────┘  │     │
│  └────────────────────────────────────────────────────────────┘     │
│                           │                                           │
│                           │ /api/* (from authenticated frontend)      │
│                           ▼                                           │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │  Built-in Functions (Python 3.11)                         │     │
│  │  ┌──────────────────────────────────────────────────────┐  │     │
│  │  │  POST /api/start_job                                 │  │     │
│  │  │  • Validates user against allowlist                  │  │     │
│  │  │  • Creates job with operationId                      │  │     │
│  │  │  • Returns 202 Accepted + Location header            │  │     │
│  │  │  • Starts background processing                      │  │     │
│  │  └──────────────────────────────────────────────────────┘  │     │
│  │  ┌──────────────────────────────────────────────────────┐  │     │
│  │  │  GET /api/job_status?id={operationId}               │  │     │
│  │  │  • Returns job status, progress, result/error        │  │     │
│  │  │  • Client polls this endpoint                        │  │     │
│  │  └──────────────────────────────────────────────────────┘  │     │
│  │  ┌──────────────────────────────────────────────────────┐  │     │
│  │  │  Shared Modules                                      │  │     │
│  │  │  • auth.py: User validation                          │  │     │
│  │  │  • vm_provisioner.py: Direct Azure VM provisioning   │  │     │
│  │  │  • wireguard_docker_setup.sh: On-VM setup script     │  │     │
│  │  └──────────────────────────────────────────────────────┘  │     │
│  └────────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────┘
                           │
                           │ Direct Azure SDK calls
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Azure Resources                                 │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  Compute Management API                                       │   │
│  │  • Create VM (Flatcar Container Linux)                       │   │
│  │  • Get VM status                                             │   │
│  │  • Execute Run Command (WireGuard setup)                     │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                           │                                           │
│                           │ Provisions and configures                 │
│                           ▼                                           │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  Ephemeral VMs with Docker-based WireGuard                   │   │
│  │  • Flatcar Container Linux (Standard_B1ls)                   │   │
│  │  • linuxserver/wireguard Docker container                    │   │
│  │  • Keys generated on-VM (stateless)                          │   │
│  │  • Auto-teardown after 30 minutes                            │   │
│  └──────────────────────────────────────────────────────────────┘   │
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
  │<─────────────────────┼────────────────────────────┤
  │  Auth Token + Cookie │                            │
  │                      │                            │
  ├──────────────────────>│                            │
  │  Redirect back       │                            │
  │                      │                            │
  │<─────────────────────┤                            │
  │  Authenticated       │                            │
  │  X-MS-CLIENT-        │                            │
  │  PRINCIPAL header    │                            │
```

### 2. Job Creation Flow (202 Accepted Pattern)

```
Frontend            start_job Function      Status Store      Upstream API
  │                       │                      │                  │
  ├──────────────────────>│                      │                  │
  │  POST /api/start_job  │                      │                  │
  │  (authenticated)      │                      │                  │
  │                       │                      │                  │
  │                       ├─ Validate User       │                  │
  │                       │  (X-MS-CLIENT-       │                  │
  │                       │   PRINCIPAL header)  │                  │
  │                       │                      │                  │
  │                       ├─ Generate            │                  │
  │                       │  operationId         │                  │
  │                       │                      │                  │
  │                       ├─────────────────────>│                  │
  │                       │  Create job entry    │                  │
  │                       │<─────────────────────┤                  │
  │                       │                      │                  │
  │<──────────────────────┤                      │                  │
  │  202 Accepted         │                      │                  │
  │  {operationId, ...}   │                      │                  │
  │  Location header      │                      │                  │
  │                       │                      │                  │
  │                       ├─ Start background    │                  │
  │                       │  thread              │                  │
  │                       │                      │                  │
  │                       ├─────────────────────────────────────────>│
  │                       │  POST /provision     │                  │
  │                       │<─────────────────────────────────────────┤
  │                       │  {upstream_id}       │                  │
  │                       │                      │                  │
  │                       ├─────────────────────>│                  │
  │                       │  Update: running     │                  │
```

### 3. Status Polling Flow

```
Frontend            job_status Function     Status Store      Background Thread
  │                       │                      │                  │
  ├──────────────────────>│                      │                  │
  │  GET /api/job_status  │                      │                  │
  │  ?id=operationId      │                      │                  │
  │                       │                      │                  │
  │                       ├─────────────────────>│                  │
  │                       │  Get job             │                  │
  │                       │<─────────────────────┤                  │
  │                       │  {status: running,   │                  │
  │                       │   progress: "..."}   │                  │
  │                       │                      │                  │
  │<──────────────────────┤                      │                  │
  │  200 OK               │                      │                  │
  │  {status, progress}   │                      │                  │
  │                       │                      │                  │
  ├─ Wait 5 seconds       │                      │                  │
  │                       │                      │                  │
  │                       │                      │                  ├─ Poll upstream
  │                       │                      │                  │  GET /status/{id}
  │                       │                      │                  │
  │                       │                      │<─────────────────┤
  │                       │                      │  Update progress │
  │                       │                      │                  │
  ├──────────────────────>│                      │                  │
  │  GET /api/job_status  │                      │                  │
  │  ?id=operationId      │                      │                  │
  │                       │                      │                  │
  │                       ├─────────────────────>│                  │
  │                       │<─────────────────────┤                  │
  │                       │  {status: completed, │                  │
  │                       │   result: {...}}     │                  │
  │<──────────────────────┤                      │                  │
  │  200 OK - Completed!  │                      │                  │
  │  {confText, ...}      │                      │                  │
```

### 4. Docker-based WireGuard Setup Flow

```
VM Provisioner         Azure VM            Run Command         Docker Container
  │                      │                      │                      │
  ├─ Create VM           │                      │                      │
  │  (Flatcar Linux)     │                      │                      │
  │                      │                      │                      │
  ├─────────────────────>│                      │                      │
  │  VM Creation         │                      │                      │
  │  started             │                      │                      │
  │                      │                      │                      │
  │                      ├─ VM boots            │                      │
  │                      │  (Flatcar + Docker)  │                      │
  │                      │                      │                      │
  ├─ Poll VM Status      │                      │                      │
  ├─────────────────────>│                      │                      │
  │<─────────────────────┤                      │                      │
  │  Status: Succeeded   │                      │                      │
  │                      │                      │                      │
  ├─ Execute Run Command │                      │                      │
  ├──────────────────────┼─────────────────────>│                      │
  │  wireguard_docker_   │                      │                      │
  │  setup.sh            │                      │                      │
  │                      │                      │                      │
  │                      │                      ├─ Generate keys       │
  │                      │                      │  (wg genkey)         │
  │                      │                      │                      │
  │                      │                      ├─ Create wg0.conf     │
  │                      │                      │                      │
  │                      │                      ├─ Pull image          │
  │                      │                      ├─────────────────────>│
  │                      │                      │  linuxserver/        │
  │                      │                      │  wireguard           │
  │                      │                      │                      │
  │                      │                      ├─ Start container     │
  │                      │                      ├─────────────────────>│
  │                      │                      │                      │
  │                      │                      │                      ├─ WireGuard running
  │                      │                      │                      │  on UDP 51820
  │                      │                      │                      │
  │                      │                      ├─ Output client conf  │
  │                      │                      │  (between markers)   │
  │<─────────────────────┼──────────────────────┤                      │
  │  Run Command output  │                      │                      │
  │  with client .conf   │                      │                      │
  │                      │                      │                      │
  ├─ Extract config      │                      │                      │
  │  from output         │                      │                      │
  │                      │                      │                      │
  ├─ Return to client    │                      │                      │
  │  Status: Succeeded   │                      │                      │
  │  confText: [Interf..]│                      │                      │
```

### 5. Auto-teardown Flow

> **Note**: Auto-teardown after 30 minutes is implemented via VM tags. A separate cleanup process (not implemented in this codebase) can query for VMs with `auto-delete: true` tags older than 30 minutes and delete them.

```
Cleanup Process (External)
  │
  ├─ Query VMs with auto-delete tag
  │
  ├─ Check creation timestamp
  │
  ├─ If > 30 minutes old:
  │  │
  │  ├─ Delete VM
  │  ├─ Delete NIC
  │  ├─ Delete Public IP
  │  ├─ Delete VNet
  │  └─ Delete NSG
  │
  └─ Cleanup complete
```

Potential implementation options:
- Azure Automation runbook (scheduled every 5-10 minutes)
- Azure Logic App with recurrence trigger
- Separate Azure Function with timer trigger
- External cron job using Azure CLI

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
│  4. Upstream Provider Access                            │
│     • API Key authentication (UPSTREAM_API_KEY)         │
│     • Stored in SWA app settings                        │
│     • Not exposed to frontend                           │
│                                                         │
│  5. Secrets Management                                  │
│     • No secrets in code                                │
│     • SWA App Settings for configuration                │
│     • GitHub Secrets for CI/CD token                    │
│     • Upstream credentials via environment variables    │
└─────────────────────────────────────────────────────────┘
```

## Data Flow

### Request-Response Lifecycle

```
1. User Request
   ├─> Frontend validates auth state
   ├─> Sends request to /api/* endpoint
   └─> Includes authentication cookie

2. SWA Runtime
   ├─> Validates authentication cookie
   ├─> Extracts user principal
   ├─> Adds X-MS-CLIENT-PRINCIPAL header
   └─> Routes to built-in Function

3. Built-in Function (start_job or job_status)
   ├─> Receives request with user principal
   ├─> Validates user email against ALLOWED_EMAILS
   ├─> Processes request
   └─> Returns response

4. For start_job:
   ├─> Generates operationId
   ├─> Creates job in status store
   ├─> Returns 202 Accepted immediately
   ├─> Spawns background thread
   └─> Background thread calls upstream provider

5. Background Thread / Upstream Integration
   ├─> Calls upstream POST /provision
   ├─> Polls upstream GET /status/{id}
   ├─> Updates local status store
   └─> Completes when upstream reports done

6. For job_status:
   ├─> Queries local status store
   ├─> Returns current job status
   └─> Client continues polling until completed/failed
```

## Deployment Architecture

### Simplified Deployment Flow

```
GitHub Repo                  Azure
    │                          │
    ├─> Push to main           │
    │   or manual trigger      │
    │                          │
    ├─────────────────────────>│
    │  Azure/static-web-apps-  │
    │  deploy@v1               │
    │                          │
    │                          ├─> Upload SPA files
    │                          │   (index.html, etc.)
    │                          │
    │                          ├─> Build Python Functions
    │                          │   (pip install from
    │                          │    api/requirements.txt)
    │                          │
    │                          ├─> Deploy to SWA
    │                          │   • Frontend at /
    │                          │   • API at /api/*
    │                          │
    │<─────────────────────────┤
    │  Deployment Complete     │
    │  (Single resource)       │
```

### Infrastructure Provisioning

```
Azure CLI or Portal
    │
    ├─> Create Static Web App
    │   az staticwebapp create
    │
    ├─> Configure App Settings
    │   • ALLOWED_EMAILS
    │   • UPSTREAM_BASE_URL
    │   • UPSTREAM_API_KEY
    │   • DRY_RUN
    │
    └─> Configure Authentication
        • Google/Microsoft providers
```

## Scalability & Performance

### Resource Scaling

```
Component              Scaling Strategy              Limits
─────────────────────────────────────────────────────────────
Static Web App         Auto-scaling                  N/A
Frontend               (CDN-backed)                  

SWA Functions          Auto-scaling                  Managed by Azure
                       (serverless)                  (typically 200+ instances)

In-memory Store        Single instance               Limited by instance memory
                       (can upgrade to Redis/        (upgrade for horizontal
                       Table Storage)                scaling)

Upstream Provider      External system               Depends on provider                 
```

### Performance Characteristics

```
Operation              Latency       Notes
──────────────────────────────────────────────────────
Frontend Load          < 2s          CDN-cached
Authentication         < 3s          OAuth redirect
POST /api/start_job    < 500ms       Returns 202 immediately
GET /api/job_status    < 200ms       Queries in-memory store
VM Provisioning        2-5 min       Depends on upstream provider
Background polling     5s interval   Can be configured
```

## Monitoring & Observability

### Monitoring Options

```
SWA Functions Logs            Azure Portal / CLI
    │                              │
    ├─> Function execution logs    │
    │   (stdout/stderr)            │
    │                              │
    ├─> HTTP request logs          │
    │   (status codes, latency)    │
    │                              │
    └─────────────────────────────>│
                                   │
                                   ├─> View in portal
                                   │   (Monitoring blade)
                                   │
                                   └─> Stream logs
                                       (az cli or portal)
```

**Available monitoring:**
- Function execution logs in Azure Portal
- HTTP request/response logs
- Error tracking
- Performance metrics
- Can integrate with Application Insights (optional)

## Cost Optimization

### Resource Costs (Approximate)

```
Resource              Tier              Monthly Cost (est.)
──────────────────────────────────────────────────────────
Static Web App        Free              $0
SWA Functions         First 1M requests $0 (then ~$0.20/M)
Bandwidth             First 100 GB      $0
───────────────────────────────────────────────────────────
Azure baseline                          $0 with free tier
Upstream costs                          Varies by provider
```

**Upstream provider costs** (if using Azure VMs via upstream):
- VM per session: $0.01-0.08/hour depending on size
- Storage: Minimal (~$0.05/month per disk)
- Networking: Minimal
- Data egress: Variable based on VPN usage

### Cost Control Strategies

1. **Free SWA Tier**: Sufficient for most use cases
2. **Serverless Functions**: Pay per request, not per hour
3. **In-memory Store**: No external storage costs (can upgrade later)
4. **DRY_RUN Mode**: Test without provisioning resources
5. **Short Sessions**: Upstream provider manages VM lifetime
6. **Efficient Polling**: Balance freshness vs. API costs

## Future Architecture Enhancements

### Near-term Improvements

1. **Persistent Status Store**: Upgrade from in-memory to Redis or Azure Table Storage for:
   - Job persistence across function restarts
   - Horizontal scaling support
   - Better reliability

2. **Webhook Support**: Allow upstream provider to push status updates instead of polling

3. **Background Worker**: Separate polling logic into dedicated worker process

### Medium-term Enhancements

4. **Multi-region Support**: Deploy SWA in multiple regions for lower latency

5. **Advanced RBAC**: Role-based access control beyond email allowlist

6. **QR Code Generation**: Generate QR codes for mobile WireGuard config

7. **Usage Analytics**: Track and report usage patterns

### Long-term Vision

8. **Multi-provider Support**: Abstract upstream provider interface for:
   - Azure VMs
   - AWS EC2
   - GCP Compute
   - Kubernetes pods

9. **Container Support**: If WireGuard in Azure Container Instances becomes viable

10. **Custom Domains**: Support custom domain mapping in SWA

## Key Design Decisions

### Why SWA Functions instead of Durable Functions?

**Benefits:**
- ✅ Simpler architecture (single resource)
- ✅ Lower cost (no separate Function App or Storage)
- ✅ Easier deployment (single workflow)
- ✅ Better integration (frontend + API in one resource)
- ✅ Standard REST pattern (202 Accepted)

**Trade-offs:**
- ⚠️ No built-in state management (must implement)
- ⚠️ No durable timers (delegate to upstream)
- ⚠️ Polling required (can add webhooks later)
- ⚠️ Shorter timeout limits (can work around with async pattern)

### Why In-memory Status Store?

**Benefits:**
- ✅ Zero external dependencies to start
- ✅ Fast reads/writes
- ✅ Simple implementation
- ✅ Easy to upgrade later

**Limitations:**
- ⚠️ Lost on restart (acceptable for MVP)
- ⚠️ Single instance only (can upgrade to Redis)
- ⚠️ Limited by instance memory

**Upgrade Path:**
- Replace `StatusStore` class with Redis client
- Update `get_status_store()` to return Redis-backed store
- No API changes required

### Why Upstream Provider Pattern?

**Benefits:**
- ✅ Decouples SWA from VM provisioning logic
- ✅ Allows flexibility in backend implementation
- ✅ Easier to test (DRY_RUN mode)
- ✅ Can swap providers without changing API

**Implementation:**
- `api/shared/upstream.py` provides abstraction
- Environment variables configure integration
- TODO comments mark integration points
