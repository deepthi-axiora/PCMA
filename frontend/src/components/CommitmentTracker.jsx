import { useState, useEffect, useCallback } from 'react'
import { CheckSquare, Bell, Clock, Plus, Trash2, CheckCircle2, AlertTriangle, Calendar } from 'lucide-react'
import {
  getCommitments,
  updateCommitmentStatus,
  getReminders,
  createReminder,
  deleteReminder,
} from '../api/commitmentsReminders'

export function CommitmentTracker() {
  const [activeSubTab, setActiveSubTab] = useState('commitments') // commitments, reminders

  // Commitments state
  const [commitments, setCommitments] = useState([])
  const [statusFilter, setStatusFilter] = useState('open') // open, fulfilled, cancelled, all
  const [loadingCommitments, setLoadingCommitments] = useState(true)

  // Reminders state
  const [reminders, setReminders] = useState([])
  const [loadingReminders, setLoadingReminders] = useState(true)
  const [showCreateReminder, setShowCreateReminder] = useState(false)

  // New reminder form
  const [remTitle, setRemTitle] = useState('')
  const [remDateTime, setRemDateTime] = useState('')
  const [remPriority, setRemPriority] = useState('normal')
  const [creatingRem, setCreatingRem] = useState(false)

  const loadCommitments = useCallback(async () => {
    setLoadingCommitments(true)
    try {
      const data = await getCommitments()
      setCommitments(data)
    } catch (err) {
      console.error('Commitments load failed:', err)
    } finally {
      setLoadingCommitments(false)
    }
  }, [])

  const loadReminders = useCallback(async () => {
    setLoadingReminders(true)
    try {
      const data = await getReminders()
      setReminders(data)
    } catch (err) {
      console.error('Reminders load failed:', err)
    } finally {
      setLoadingReminders(false)
    }
  }, [])

  useEffect(() => {
    loadCommitments()
    loadReminders()
  }, [loadCommitments, loadReminders])

  // Native notification permission request for FR-35
  useEffect(() => {
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission().catch(() => {})
    }
  }, [])

  const handleStatusChange = async (commitmentId, newStatus) => {
    try {
      await updateCommitmentStatus(commitmentId, newStatus)
      await loadCommitments()
    } catch (err) {
      alert(`Update status failed: ${err.message}`)
    }
  }

  const handleCreateReminder = async (e) => {
    e.preventDefault()
    if (!remTitle.trim() || !remDateTime) return
    setCreatingRem(true)
    try {
      await createReminder({
        title: remTitle.trim(),
        remind_at: new Date(remDateTime).toISOString(),
        priority: remPriority,
      })
      setRemTitle('')
      setRemDateTime('')
      setShowCreateReminder(false)
      await loadReminders()

      if ('Notification' in window && Notification.permission === 'granted') {
        new Notification('Reminder Scheduled', { body: remTitle })
      }
    } catch (err) {
      alert(`Create reminder failed: ${err.message}`)
    } finally {
      setCreatingRem(false)
    }
  }

  const handleDeleteReminder = async (reminderId) => {
    if (!window.confirm('Delete this reminder?')) return
    try {
      await deleteReminder(reminderId)
      await loadReminders()
    } catch (err) {
      alert(`Delete failed: ${err.message}`)
    }
  }

  const filteredCommitments = commitments.filter((c) => {
    if (statusFilter === 'all') return true
    return c.status === statusFilter
  })

  return (
    <div className="commitments-container">
      {/* Sub Tabs */}
      <div className="commitments-subtabs">
        <button
          className={`subtab-btn ${activeSubTab === 'commitments' ? 'active' : ''}`}
          onClick={() => setActiveSubTab('commitments')}
        >
          <CheckSquare className="tab-icon" /> Commitment Tracking (FR-34) ({commitments.length})
        </button>
        <button
          className={`subtab-btn ${activeSubTab === 'reminders' ? 'active' : ''}`}
          onClick={() => setActiveSubTab('reminders')}
        >
          <Bell className="tab-icon" /> Reminders (FR-35) ({reminders.length})
        </button>
      </div>

      {/* COMMITMENTS TAB */}
      {activeSubTab === 'commitments' && (
        <div className="commitments-pane">
          {/* Status Filter Chips */}
          <div className="status-filter-bar">
            {['open', 'fulfilled', 'cancelled', 'all'].map((st) => (
              <button
                key={st}
                className={`filter-chip ${statusFilter === st ? 'active' : ''}`}
                onClick={() => setStatusFilter(st)}
              >
                {st.toUpperCase()}
              </button>
            ))}
          </div>

          <div className="commitments-list">
            {loadingCommitments ? (
              <div className="loading-spinner-box">Loading commitments...</div>
            ) : filteredCommitments.length === 0 ? (
              <div className="empty-state">No commitments found for status '{statusFilter}'.</div>
            ) : (
              filteredCommitments.map((c) => (
                <div key={c.id} className="commitment-card">
                  <div className="commitment-header">
                    <span className="commitment-title">{c.title || c.commitment_text}</span>
                    <span className={`status-pill pill-${c.status}`}>{c.status}</span>
                  </div>

                  {c.due_date && (
                    <div className="commitment-due">
                      <Clock className="due-icon" /> Due: {new Date(c.due_date).toLocaleDateString()}
                    </div>
                  )}

                  {/* Quick Action Buttons */}
                  <div className="commitment-actions">
                    {c.status !== 'fulfilled' && (
                      <button
                        className="btn btn-secondary btn-sm"
                        onClick={() => handleStatusChange(c.id, 'fulfilled')}
                      >
                        <CheckCircle2 className="btn-icon" /> Mark Fulfilled
                      </button>
                    )}
                    {c.status !== 'cancelled' && (
                      <button
                        className="btn btn-secondary btn-sm"
                        onClick={() => handleStatusChange(c.id, 'cancelled')}
                      >
                        Cancel
                      </button>
                    )}
                    {c.status !== 'open' && (
                      <button
                        className="btn btn-secondary btn-sm"
                        onClick={() => handleStatusChange(c.id, 'open')}
                      >
                        Reopen
                      </button>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* REMINDERS TAB */}
      {activeSubTab === 'reminders' && (
        <div className="reminders-pane">
          <div className="reminders-header-bar">
            <h4>Scheduled Reminders</h4>
            <button className="btn btn-primary btn-sm" onClick={() => setShowCreateReminder(!showCreateReminder)}>
              <Plus className="btn-icon" /> {showCreateReminder ? 'Close Form' : 'New Reminder'}
            </button>
          </div>

          {/* New Reminder Form */}
          {showCreateReminder && (
            <form onSubmit={handleCreateReminder} className="form-card">
              <h4>Set Up Reminder</h4>
              <div className="form-row-grid">
                <input
                  type="text"
                  required
                  className="text-input"
                  placeholder="Reminder Title *"
                  value={remTitle}
                  onChange={(e) => setRemTitle(e.target.value)}
                />
                <input
                  type="datetime-local"
                  required
                  className="date-input"
                  value={remDateTime}
                  onChange={(e) => setRemDateTime(e.target.value)}
                />
                <select
                  className="select-input"
                  value={remPriority}
                  onChange={(e) => setRemPriority(e.target.value)}
                >
                  <option value="low">Low Priority</option>
                  <option value="normal">Normal Priority</option>
                  <option value="high">High Priority</option>
                </select>
              </div>
              <button type="submit" className="btn btn-primary" disabled={creatingRem}>
                {creatingRem ? 'Scheduling...' : 'Schedule Reminder'}
              </button>
            </form>
          )}

          <div className="reminders-list">
            {loadingReminders ? (
              <div className="loading-spinner-box">Loading reminders...</div>
            ) : reminders.length === 0 ? (
              <div className="empty-state">No reminders scheduled yet.</div>
            ) : (
              reminders.map((rem) => (
                <div key={rem.id} className="reminder-card">
                  <div className="reminder-info">
                    <span className="reminder-title">{rem.title}</span>
                    <span className="reminder-time">
                      <Calendar className="rem-icon" /> {new Date(rem.remind_at).toLocaleString()}
                    </span>
                  </div>
                  <div className="reminder-right">
                    <span className={`priority-badge priority-${rem.priority}`}>{rem.priority}</span>
                    <button className="btn btn-danger btn-sm" onClick={() => handleDeleteReminder(rem.id)}>
                      <Trash2 className="btn-icon" />
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  )
}
