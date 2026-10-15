import { useState, useEffect } from 'react'
import { Settings, Shield, RefreshCw, Download, Trash2, UserX, CheckCircle, AlertTriangle } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { useOffline } from '../context/OfflineContext'
import { updateProfile } from '../api/profile'
import { exportUserData, deleteUserData, deleteUserAccount } from '../api/dataControl'
import { ConfirmDialog } from '../components/ConfirmDialog'

const JURISDICTIONS = [
  { id: 'US-CA', name: 'California, USA (All-Party Consent)' },
  { id: 'US-NY', name: 'New York, USA (One-Party Consent)' },
  { id: 'EU-GDPR', name: 'European Union (GDPR Compliant)' },
  { id: 'UK', name: 'United Kingdom (UK-GDPR)' },
  { id: 'IN', name: 'India (DPDP Act 2023)' },
  { id: 'GENERIC-ALL', name: 'All-Party Consent (Default Global)' },
]

export function SettingsView() {
  const { profile, refreshProfile, logout } = useAuth()
  const { isOnline, pendingQueue, isSyncing, triggerSync, backendSyncStatus } = useOffline()

  const [jurisdiction, setJurisdiction] = useState(profile?.jurisdiction || 'US-CA')
  const [savingJurisdiction, setSavingJurisdiction] = useState(false)
  const [successMsg, setSuccessMsg] = useState(null)

  // Confirm Dialog modal state
  const [confirmState, setConfirmState] = useState({
    isOpen: false,
    type: null, // export, wipe, account
    title: '',
    message: '',
    isDanger: false,
  })
  const [isProcessingAction, setIsProcessingAction] = useState(false)

  useEffect(() => {
    if (profile?.jurisdiction) {
      setJurisdiction(profile.jurisdiction)
    }
  }, [profile])

  const handleUpdateJurisdiction = async (e) => {
    e.preventDefault()
    setSavingJurisdiction(true)
    setSuccessMsg(null)
    try {
      await updateProfile({ jurisdiction })
      await refreshProfile()
      setSuccessMsg('Jurisdiction configuration updated successfully.')
    } catch (err) {
      alert(`Update failed: ${err.message}`)
    } finally {
      setSavingJurisdiction(false)
    }
  }

  const promptExport = () => {
    setConfirmState({
      isOpen: true,
      type: 'export',
      title: 'Export All Personal Data (FR-43)',
      message: 'Download a complete encrypted ZIP/JSON package of all your recorded conversations, transcripts, MOMs, and memories.',
      isDanger: false,
    })
  }

  const promptDataWipe = () => {
    setConfirmState({
      isOpen: true,
      type: 'wipe',
      title: 'Wipe All Recorded Data (FR-42)',
      message: 'Warning: This will permanently delete all your audio files, transcripts, conversation memories, commitments, and MOM documents from local and encrypted remote storage.',
      isDanger: true,
    })
  }

  const promptAccountDelete = () => {
    setConfirmState({
      isOpen: true,
      type: 'account',
      title: 'Delete User Account (FR-44)',
      message: 'Warning: This will permanently delete your account profile, scrub personal identifiable information from audit logs, and log you out immediately.',
      isDanger: true,
    })
  }

  const handleExecuteConfirmedAction = async () => {
    setIsProcessingAction(true)
    try {
      if (confirmState.type === 'export') {
        const result = await exportUserData()
        let blob
        if (result instanceof Blob) {
          blob = result
        } else {
          blob = new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' })
        }
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `PCMA_Data_Export_${Date.now()}.json`
        document.body.appendChild(a)
        a.click()
        document.body.removeChild(a)
        URL.revokeObjectURL(url)
        alert('Data export downloaded successfully!')
      } else if (confirmState.type === 'wipe') {
        await deleteUserData()
        alert('All recorded user data has been wiped.')
        window.location.reload()
      } else if (confirmState.type === 'account') {
        await deleteUserAccount()
        alert('Account deleted successfully.')
        logout()
      }
    } catch (err) {
      alert(`Operation failed: ${err.message}`)
    } finally {
      setIsProcessingAction(false)
      setConfirmState({ isOpen: false, type: null, title: '', message: '', isDanger: false })
    }
  }

  return (
    <div className="view-pane settings-view">
      <div className="view-header">
        <h2>Settings & Data Privacy</h2>
        <p className="subtitle">Configure legal compliance, synchronization, data export, and account lifecycle</p>
      </div>

      {/* JURISDICTION CONFIGURATION (FR-03) */}
      <div className="settings-card">
        <h3><Shield className="card-title-icon" /> Compliance & Jurisdiction Setup (FR-03)</h3>
        <form onSubmit={handleUpdateJurisdiction} className="settings-form">
          <div className="form-group">
            <label>Current Legal Jurisdiction:</label>
            <select
              className="select-input"
              value={jurisdiction}
              onChange={(e) => setJurisdiction(e.target.value)}
            >
              {JURISDICTIONS.map((j) => (
                <option key={j.id} value={j.id}>{j.name}</option>
              ))}
            </select>
          </div>
          <button type="submit" className="btn btn-primary" disabled={savingJurisdiction}>
            {savingJurisdiction ? 'Saving...' : 'Update Jurisdiction'}
          </button>
        </form>
        {successMsg && (
          <div className="success-banner">
            <CheckCircle className="banner-icon" /> {successMsg}
          </div>
        )}
      </div>

      {/* SYNCHRONIZATION HARDENING (FR-40, FR-41) */}
      <div className="settings-card">
        <h3><RefreshCw className="card-title-icon" /> Offline Mode & Synchronization (FR-40, FR-41)</h3>
        <div className="sync-status-grid">
          <div className="status-item">
            <span>Network State:</span>
            <strong className={isOnline ? 'text-success' : 'text-danger'}>
              {isOnline ? 'Online' : 'Offline'}
            </strong>
          </div>
          <div className="status-item">
            <span>Pending Offline Operations:</span>
            <strong>{pendingQueue.length} items</strong>
          </div>
        </div>

        <button
          className="btn btn-secondary"
          onClick={() => triggerSync()}
          disabled={!isOnline || isSyncing || pendingQueue.length === 0}
        >
          <RefreshCw className={`btn-icon ${isSyncing ? 'spin' : ''}`} />
          {isSyncing ? 'Synchronizing...' : 'Trigger Immediate Sync'}
        </button>
      </div>

      {/* PRIVACY & DATA CONTROL (FR-42, FR-43, FR-44) */}
      <div className="settings-card privacy-card">
        <h3><Trash2 className="card-title-icon" /> Privacy & Data Control</h3>
        <p className="card-desc">Manage data sovereignty, download encrypted backup packages, or execute account purge.</p>

        <div className="action-buttons-grid">
          <button className="btn btn-secondary" onClick={promptExport}>
            <Download className="btn-icon" /> Export Personal Data (FR-43)
          </button>

          <button className="btn btn-danger" onClick={promptDataWipe}>
            <Trash2 className="btn-icon" /> Wipe Audio & Conversation Data (FR-42)
          </button>

          <button className="btn btn-danger" onClick={promptAccountDelete}>
            <UserX className="btn-icon" /> Delete Account & Scrub PII (FR-44)
          </button>
        </div>
      </div>

      <ConfirmDialog
        isOpen={confirmState.isOpen}
        title={confirmState.title}
        message={confirmState.message}
        isDanger={confirmState.isDanger}
        confirmLabel={confirmState.type === 'export' ? 'Download Export' : 'Proceed'}
        onConfirm={handleExecuteConfirmedAction}
        onCancel={() => setConfirmState({ isOpen: false, type: null, title: '', message: '', isDanger: false })}
        isLoading={isProcessingAction}
      />
    </div>
  )
}
