import { useState, useEffect, useCallback } from 'react'
import { RecordingControls } from '../components/RecordingControls'
import { ConsentModal } from '../components/ConsentModal'
import { useAuth } from '../context/AuthContext'
import { getRecordings } from '../api/recordings'
import { Mic, Clock, FileText } from 'lucide-react'

export function RecordView({ onOpenConversation }) {
  const { profile } = useAuth()
  const [showConsentModal, setShowConsentModal] = useState(!profile?.jurisdiction)
  const [recentRecordings, setRecentRecordings] = useState([])
  const [loading, setLoading] = useState(true)

  const loadRecordings = useCallback(async () => {
    setLoading(true)
    try {
      const data = await getRecordings()
      setRecentRecordings(data.slice(0, 5))
    } catch (err) {
      console.error('Failed to load recent recordings:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadRecordings()
  }, [loadRecordings])

  return (
    <div className="view-pane record-view">
      <div className="view-header">
        <h2>Audio Capture & Recorder</h2>
        <p className="subtitle">Record live conversations with background processing and speaker diarization</p>
      </div>

      <RecordingControls
        onRecordingFinished={(recordingId) => {
          loadRecordings()
          if (onOpenConversation) onOpenConversation(recordingId)
        }}
        onSelectConsent={() => setShowConsentModal(true)}
      />

      {/* Recent Recordings Cards */}
      <div className="recent-recordings-section">
        <h3>Recent Recordings</h3>
        {loading ? (
          <div className="loading-spinner-box">Loading recordings...</div>
        ) : recentRecordings.length === 0 ? (
          <div className="empty-state">No audio recordings captured yet. Tap above to start recording.</div>
        ) : (
          <div className="recordings-list">
            {recentRecordings.map((rec) => (
              <div
                key={rec.id}
                className="recording-list-item"
                onClick={() => onOpenConversation && onOpenConversation(rec.id)}
              >
                <div className="rec-info">
                  <span className="rec-title">Recording #{rec.id}</span>
                  <span className="rec-time">
                    <Clock className="rec-icon" /> {new Date(rec.created_at).toLocaleString()}
                  </span>
                </div>
                <div className="rec-right">
                  <span className={`state-badge state-${rec.state || rec.status}`}>{rec.state || rec.status}</span>
                  <button className="btn btn-secondary btn-sm">
                    <FileText className="btn-icon" /> View
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <ConsentModal
        isOpen={showConsentModal}
        onClose={() => setShowConsentModal(false)}
        onConsentConfirmed={() => loadRecordings()}
      />
    </div>
  )
}
