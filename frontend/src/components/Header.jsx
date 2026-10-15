import { useAuth } from '../context/AuthContext'
import { useOffline } from '../context/OfflineContext'
import { Mic, RefreshCw, Wifi, WifiOff, LogOut, User } from 'lucide-react'

export function Header() {
  const { user, profile, logout, devMode } = useAuth()
  const { isOnline, pendingQueue, isSyncing, triggerSync } = useOffline()

  return (
    <header className="app-header">
      <div className="header-brand">
        <div className="brand-logo">
          <Mic className="logo-icon" />
        </div>
        <div className="brand-title">
          <h1>PCMA</h1>
          <span className="brand-subtitle">Conversation Memory</span>
        </div>
      </div>

      <div className="header-actions">
        {/* Connection status badge */}
        <div className={`status-badge ${isOnline ? 'online' : 'offline'}`}>
          {isOnline ? <Wifi className="badge-icon" /> : <WifiOff className="badge-icon" />}
          <span className="badge-text">{isOnline ? 'Connected' : 'Offline'}</span>
        </div>

        {/* Sync queue indicator */}
        {pendingQueue.length > 0 && (
          <button 
            className="sync-button" 
            onClick={() => triggerSync()}
            disabled={!isOnline || isSyncing}
            title={`${pendingQueue.length} offline operation(s) pending sync`}
          >
            <RefreshCw className={`sync-icon ${isSyncing ? 'spin' : ''}`} />
            <span className="sync-count">{pendingQueue.length}</span>
          </button>
        )}

        {/* Profile & Logout */}
        <div className="user-profile-menu">
          <div className="avatar-chip" title={user?.email || 'User'}>
            <User className="avatar-icon" />
            <span className="avatar-name">{profile?.jurisdiction || (devMode ? 'Dev User' : 'User')}</span>
          </div>

          <button className="logout-button" onClick={logout} title="Log Out">
            <LogOut className="logout-icon" />
          </button>
        </div>
      </div>
    </header>
  )
}
