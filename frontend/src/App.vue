<template>
  <div class="app">
    <header class="header">
      <h1>🔐 WireGuard VPN Service</h1>
      <p class="subtitle">Secure, Ephemeral VPN Sessions</p>
    </header>

    <main class="main-content">
      <!-- Not authenticated -->
      <div v-if="!user" class="auth-section">
        <div class="card">
          <h2>Welcome!</h2>
          <p>Please sign in to create a WireGuard VPN session</p>
          
          <div class="login-buttons">
            <a href="/.auth/login/google" class="btn btn-google">
              <svg width="18" height="18" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
                <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>
                <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>
                <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/>
                <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/>
              </svg>
              Sign in with Google
            </a>
            
            <a href="/.auth/login/aad" class="btn btn-microsoft">
              <svg width="18" height="18" viewBox="0 0 23 23" xmlns="http://www.w3.org/2000/svg">
                <path fill="#f3f3f3" d="M0 0h23v23H0z"/>
                <path fill="#f35325" d="M1 1h10v10H1z"/>
                <path fill="#81bc06" d="M12 1h10v10H12z"/>
                <path fill="#05a6f0" d="M1 12h10v10H1z"/>
                <path fill="#ffba08" d="M12 12h10v10H12z"/>
              </svg>
              Sign in with Microsoft
            </a>
          </div>
        </div>
      </div>

      <!-- Authenticated -->
      <div v-else class="session-section">
        <div class="card">
          <div class="user-info">
            <h3>Welcome, {{ user.userDetails }}</h3>
            <a href="/.auth/logout" class="btn-logout">Sign out</a>
          </div>

          <div v-if="!session" class="start-session">
            <h2>Start VPN Session</h2>
            <p>Create a temporary WireGuard VPN instance</p>
            
            <div class="form-group">
              <label for="duration">Session Duration (seconds):</label>
              <input 
                id="duration" 
                v-model.number="duration" 
                type="number" 
                min="60" 
                max="86400"
                class="input"
              />
            </div>

            <button @click="startSession" :disabled="loading" class="btn btn-primary">
              {{ loading ? 'Starting...' : 'Start Session' }}
            </button>
          </div>

          <div v-else class="active-session">
            <h2>Active Session</h2>
            
            <div class="session-info">
              <div class="info-row">
                <span class="label">Instance ID:</span>
                <span class="value">{{ session.instanceId }}</span>
              </div>
              <div class="info-row">
                <span class="label">Status:</span>
                <span class="value status" :class="session.status">{{ session.status }}</span>
              </div>
              <div class="info-row" v-if="session.publicIp">
                <span class="label">Public IP:</span>
                <span class="value">{{ session.publicIp }}</span>
              </div>
              <div class="info-row" v-if="session.remainingTime">
                <span class="label">Remaining Time:</span>
                <span class="value">{{ formatTime(session.remainingTime) }}</span>
              </div>
            </div>

            <button @click="refreshStatus" :disabled="loading" class="btn btn-secondary">
              {{ loading ? 'Refreshing...' : 'Refresh Status' }}
            </button>
            
            <button @click="endSession" class="btn btn-danger">
              End Session
            </button>
          </div>

          <div v-if="error" class="error">
            {{ error }}
          </div>
        </div>
      </div>
    </main>

    <footer class="footer">
      <p>WireGuard VPN Service | Powered by Azure</p>
      <p class="allowed-users">Allowed users: awwsawws@gmail.com, awwsawws@hotmail.com</p>
    </footer>
  </div>
</template>

<script>
export default {
  name: 'App',
  data() {
    return {
      user: null,
      session: null,
      duration: 3600,
      loading: false,
      error: null
    }
  },
  async mounted() {
    await this.fetchUserInfo()
  },
  methods: {
    async fetchUserInfo() {
      try {
        const response = await fetch('/.auth/me')
        const data = await response.json()
        
        if (data.clientPrincipal) {
          this.user = data.clientPrincipal
        }
      } catch (err) {
        console.error('Error fetching user info:', err)
      }
    },
    
    async startSession() {
      this.loading = true
      this.error = null
      
      try {
        const response = await fetch('/api/start', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            duration: this.duration
          })
        })
        
        if (!response.ok) {
          const errorData = await response.json()
          throw new Error(errorData.error || 'Failed to start session')
        }
        
        const data = await response.json()
        
        this.session = {
          instanceId: data.instanceId,
          status: 'starting',
          startTime: Date.now(),
          duration: this.duration
        }
        
        // Start polling for status
        this.pollStatus()
      } catch (err) {
        this.error = err.message
      } finally {
        this.loading = false
      }
    },
    
    async refreshStatus() {
      if (!this.session) return
      
      this.loading = true
      this.error = null
      
      try {
        const response = await fetch(`/api/status?instanceId=${this.session.instanceId}`)
        
        if (!response.ok) {
          throw new Error('Failed to get status')
        }
        
        const data = await response.json()
        
        this.session.status = data.runtimeStatus?.toLowerCase() || 'unknown'
        
        if (data.output && data.output.provision_result) {
          this.session.publicIp = data.output.provision_result.public_ip
        }
        
        const elapsed = Math.floor((Date.now() - this.session.startTime) / 1000)
        this.session.remainingTime = Math.max(0, this.session.duration - elapsed)
        
      } catch (err) {
        this.error = err.message
      } finally {
        this.loading = false
      }
    },
    
    pollStatus() {
      if (!this.session) return
      
      const intervalId = setInterval(async () => {
        if (!this.session || this.session.status === 'completed') {
          clearInterval(intervalId)
          return
        }
        
        await this.refreshStatus()
      }, 5000)
    },
    
    endSession() {
      this.session = null
      this.error = null
    },
    
    formatTime(seconds) {
      const hours = Math.floor(seconds / 3600)
      const minutes = Math.floor((seconds % 3600) / 60)
      const secs = seconds % 60
      
      if (hours > 0) {
        return `${hours}h ${minutes}m ${secs}s`
      } else if (minutes > 0) {
        return `${minutes}m ${secs}s`
      } else {
        return `${secs}s`
      }
    }
  }
}
</script>

<style scoped>
.app {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.header {
  text-align: center;
  padding: 2rem;
  color: white;
}

.header h1 {
  font-size: 2.5rem;
  margin-bottom: 0.5rem;
}

.subtitle {
  font-size: 1.1rem;
  opacity: 0.9;
}

.main-content {
  flex: 1;
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 2rem;
}

.card {
  background: white;
  border-radius: 12px;
  padding: 2rem;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  max-width: 500px;
  width: 100%;
}

.card h2 {
  margin-bottom: 1rem;
  color: #333;
}

.card p {
  color: #666;
  margin-bottom: 1.5rem;
}

.login-buttons {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  padding: 0.875rem 1.5rem;
  border: none;
  border-radius: 6px;
  font-size: 1rem;
  font-weight: 500;
  cursor: pointer;
  text-decoration: none;
  transition: all 0.2s;
}

.btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.btn-google {
  background: white;
  color: #333;
  border: 1px solid #ddd;
}

.btn-microsoft {
  background: white;
  color: #333;
  border: 1px solid #ddd;
}

.btn-primary {
  background: #667eea;
  color: white;
}

.btn-primary:hover {
  background: #5568d3;
}

.btn-primary:disabled {
  background: #ccc;
  cursor: not-allowed;
  transform: none;
}

.btn-secondary {
  background: #6c757d;
  color: white;
  margin-right: 0.5rem;
}

.btn-danger {
  background: #dc3545;
  color: white;
}

.user-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid #eee;
}

.user-info h3 {
  color: #333;
  font-size: 1.1rem;
}

.btn-logout {
  color: #667eea;
  text-decoration: none;
  font-size: 0.9rem;
}

.btn-logout:hover {
  text-decoration: underline;
}

.form-group {
  margin-bottom: 1.5rem;
}

.form-group label {
  display: block;
  margin-bottom: 0.5rem;
  color: #333;
  font-weight: 500;
}

.input {
  width: 100%;
  padding: 0.75rem;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 1rem;
}

.input:focus {
  outline: none;
  border-color: #667eea;
}

.session-info {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 1.5rem;
  margin-bottom: 1.5rem;
}

.info-row {
  display: flex;
  justify-content: space-between;
  padding: 0.5rem 0;
  border-bottom: 1px solid #e9ecef;
}

.info-row:last-child {
  border-bottom: none;
}

.info-row .label {
  font-weight: 600;
  color: #495057;
}

.info-row .value {
  color: #212529;
}

.status {
  padding: 0.25rem 0.75rem;
  border-radius: 4px;
  font-size: 0.875rem;
  font-weight: 600;
}

.status.starting,
.status.running {
  background: #d4edda;
  color: #155724;
}

.status.pending {
  background: #fff3cd;
  color: #856404;
}

.status.completed {
  background: #d1ecf1;
  color: #0c5460;
}

.error {
  background: #f8d7da;
  color: #721c24;
  padding: 1rem;
  border-radius: 6px;
  margin-top: 1rem;
}

.footer {
  text-align: center;
  padding: 2rem;
  color: white;
  opacity: 0.8;
}

.footer p {
  margin: 0.25rem 0;
}

.allowed-users {
  font-size: 0.875rem;
  opacity: 0.7;
}
</style>
