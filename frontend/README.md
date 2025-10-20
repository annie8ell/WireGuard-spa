# ⚠️ DEPRECATED / Archived

**Archived: This frontend README describes a previous Vue/Vite implementation. The repository currently uses a zero-build SPA (index.html) with Alpine.js — see [README.md](../README.md) for current instructions.**

---

# WireGuard Frontend (Vue.js SPA) - Historical Reference

Modern, responsive Vue.js Single Page Application for managing WireGuard VPN sessions.

> **Note**: This documentation is kept for historical reference only. The current implementation uses a zero-build SPA in the root `index.html` file.

## Features

- 🔐 **Authentication**: Google and Microsoft sign-in via Azure Static Web Apps
- 🚀 **Session Management**: Start, monitor, and end VPN sessions
- ⏱️ **Real-time Status**: Live session status updates with countdown timer
- 📱 **Responsive Design**: Works on desktop, tablet, and mobile
- 🎨 **Modern UI**: Beautiful gradient design with smooth animations

## Structure

```
frontend/
├── index.html                      # HTML entry point
├── package.json                    # NPM dependencies and scripts
├── vite.config.js                  # Vite build configuration
├── src/
│   ├── main.js                     # Vue app initialization
│   └── App.vue                     # Main Vue component
└── public/
    └── staticwebapp.config.json    # Azure Static Web Apps configuration
```

## Technology Stack

- **Vue.js 3**: Progressive JavaScript framework
- **Vite**: Fast build tool and dev server
- **Azure Static Web Apps**: Hosting with built-in authentication
- **Native CSS**: No additional CSS framework needed

## Local Development

### Prerequisites
- Node.js 16+ and npm

### Setup

1. **Install dependencies**:
   ```bash
   npm install
   ```

2. **Run development server**:
   ```bash
   npm run dev
   ```

3. **Open browser**:
   Navigate to `http://localhost:5173`

### Development Features

- **Hot Module Replacement (HMR)**: Changes reflect instantly
- **Fast Builds**: Vite provides near-instant build times
- **Vue DevTools**: Use browser extension for debugging

## Building for Production

```bash
# Build the app
npm run build

# Preview production build locally
npm run preview
```

The build output will be in the `dist/` directory.

## Components

### App.vue

Main application component with:
- **Authentication State Management**: Detects logged-in user via `/.auth/me` endpoint
- **Session Management**: Start, monitor, and end VPN sessions
- **Status Polling**: Automatically refreshes session status every 5 seconds
- **Responsive Layout**: Mobile-first design

### Key Sections

#### 1. Authentication Section
- Shows login buttons for Google and Microsoft
- Displayed when user is not authenticated
- Redirects to Azure Static Web Apps authentication

#### 2. Session Control Section
- **Start Session**: Configure duration and start new VPN session
- **Active Session**: View session details, status, and remaining time
- **Status Indicators**: Color-coded status badges

#### 3. User Interface
- Clean, modern design with gradient background
- Card-based layout for content
- Smooth transitions and hover effects

## API Integration

The frontend communicates with the Azure Functions backend:

### Endpoints

#### GET `/.auth/me`
- **Purpose**: Get current authenticated user information
- **Response**:
  ```json
  {
    "clientPrincipal": {
      "identityProvider": "google",
      "userId": "...",
      "userDetails": "user@example.com",
      "userRoles": ["authenticated"]
    }
  }
  ```

#### POST `/api/start`
- **Purpose**: Start a new WireGuard session
- **Request**:
  ```json
  {
    "duration": 3600
  }
  ```
- **Response**:
  ```json
  {
    "instanceId": "abc123...",
    "user_email": "user@example.com",
    "duration": 3600
  }
  ```

#### GET `/api/status?instanceId={id}`
- **Purpose**: Get session status
- **Response**:
  ```json
  {
    "instanceId": "abc123...",
    "runtimeStatus": "Running",
    "output": {
      "provision_result": {
        "public_ip": "1.2.3.4"
      }
    }
  }
  ```

## Configuration

### staticwebapp.config.json

Azure Static Web Apps configuration:

```json
{
  "navigationFallback": {
    "rewrite": "/index.html"
  },
  "routes": [
    {
      "route": "/api/*",
      "allowedRoles": ["authenticated"]
    }
  ],
  "responseOverrides": {
    "401": {
      "redirect": "/.auth/login/aad",
      "statusCode": 302
    }
  }
}
```

**Key Settings**:
- **navigationFallback**: SPA routing support
- **routes**: API authentication requirement
- **responseOverrides**: Auto-redirect on unauthorized access

## Styling

The app uses scoped CSS with:
- **CSS Variables**: Easy theme customization
- **Flexbox**: Responsive layouts
- **Gradient Background**: Modern visual appeal
- **Transitions**: Smooth interactions

### Customizing Theme

Edit the gradient in `App.vue`:

```css
body {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}
```

Or customize button colors:

```css
.btn-primary {
  background: #667eea; /* Change to your brand color */
}
```

## Authentication Flow

1. **User clicks "Sign in with Google/Microsoft"**
2. **Redirected to Azure SWA authentication** (`/.auth/login/google` or `/.auth/login/aad`)
3. **User authenticates with provider**
4. **Redirected back to app with authentication cookie**
5. **Frontend fetches user info** from `/.auth/me`
6. **Backend validates user** against `ALLOWED_EMAILS` list

## Session Management Flow

1. **User starts session**: POST to `/api/start` with duration
2. **Backend creates orchestration**: Returns instance ID
3. **Frontend polls status**: GET `/api/status?instanceId=...` every 5 seconds
4. **Display updates**: Show status, IP, and remaining time
5. **Session completes**: Orchestration finishes, VM destroyed

## Deployment

### Option 1: Using GitHub Actions

The `Deploy Frontend` or `Provision Infrastructure and Deploy` workflow handles deployment automatically.

### Option 2: Manual Deployment

```bash
# Build the app
npm run build

# Get SWA deployment token
SWA_TOKEN=$(az staticwebapp secrets list \
  --name <swa-name> \
  --resource-group <resource-group> \
  --query 'properties.apiKey' -o tsv)

# Deploy using Azure CLI
az staticwebapp deploy \
  --name <swa-name> \
  --resource-group <resource-group> \
  --app-location frontend \
  --output-location dist \
  --token $SWA_TOKEN
```

### Option 3: Using SWA CLI

```bash
# Install SWA CLI
npm install -g @azure/static-web-apps-cli

# Build
npm run build

# Deploy
swa deploy ./dist --deployment-token $SWA_TOKEN
```

## Testing

### Manual Testing Checklist

- [ ] Login with Google works
- [ ] Login with Microsoft works
- [ ] Unauthorized user sees error
- [ ] Authorized user can start session
- [ ] Session status updates automatically
- [ ] Remaining time counts down
- [ ] Public IP displays when available
- [ ] End session clears state
- [ ] Logout works correctly
- [ ] Mobile responsive layout
- [ ] Error messages display clearly

### Browser Compatibility

Tested on:
- ✅ Chrome 90+
- ✅ Firefox 88+
- ✅ Safari 14+
- ✅ Edge 90+
- ✅ Mobile browsers (iOS Safari, Chrome Mobile)

## Troubleshooting

### Common Issues

#### Authentication not working
- **Check**: Azure SWA authentication providers configured
- **Check**: Redirect URIs match your SWA URL
- **Clear**: Browser cookies and try again

#### API calls fail with 401
- **Check**: User email is in `ALLOWED_EMAILS` (backend config)
- **Check**: `/api/*` routes require authentication in `staticwebapp.config.json`
- **Check**: Backend is deployed and running

#### Build fails
- **Check**: Node.js version (16+)
- **Run**: `npm install` to ensure dependencies are installed
- **Check**: `package.json` for correct script definitions

#### Hot reload not working
- **Check**: Running `npm run dev` (not `npm run build`)
- **Restart**: Dev server
- **Check**: No syntax errors in Vue components

### Debug Mode

Enable Vue DevTools:
1. Install Vue DevTools browser extension
2. Open browser DevTools
3. Click Vue tab to inspect component state

View network requests:
1. Open browser DevTools
2. Go to Network tab
3. Filter by "Fetch/XHR" to see API calls

## Best Practices

1. **Keep components small**: Split into smaller components if App.vue grows
2. **Use composition API**: For more complex state management
3. **Add loading states**: Show spinners during API calls
4. **Handle errors gracefully**: Display user-friendly error messages
5. **Test across browsers**: Ensure compatibility
6. **Optimize images**: Use appropriate formats and sizes
7. **Lazy load components**: For better performance

## Future Enhancements

- [ ] Add WireGuard config download
- [ ] Implement session history
- [ ] Add admin panel for user management
- [ ] Support for multiple simultaneous sessions
- [ ] Add session extend functionality
- [ ] Implement dark/light theme toggle
- [ ] Add more detailed VM metrics
- [ ] Support for custom VM configurations
- [ ] Add QR code for WireGuard config
- [ ] Implement real-time notifications

## Performance

- **Bundle Size**: ~100KB (gzipped)
- **Initial Load**: < 2 seconds on 3G
- **Time to Interactive**: < 3 seconds
- **Lighthouse Score**: 95+ (Performance, Accessibility, Best Practices, SEO)

## Security

- **Authentication**: Required for all API access
- **Authorization**: Backend validates allowed users
- **HTTPS Only**: All traffic encrypted
- **No Secrets**: No API keys or secrets in frontend code
- **CSP Ready**: Compatible with Content Security Policy

## Accessibility

- **Semantic HTML**: Proper element usage
- **ARIA Labels**: Where needed for screen readers
- **Keyboard Navigation**: All interactive elements accessible
- **Color Contrast**: WCAG AA compliant
- **Focus Indicators**: Visible focus states

## Contributing

See [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines on:
- Code style
- Component structure
- Commit messages
- Pull request process

## License

MIT License - See [LICENSE](../LICENSE) for details
