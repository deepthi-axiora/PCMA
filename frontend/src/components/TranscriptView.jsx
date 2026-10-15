import { useState, useEffect, useCallback } from 'react'
import { UserCheck, Tag, RefreshCw, AlertCircle, Edit3 } from 'lucide-react'
import { getTranscript, relabelSpeaker } from '../api/transcriptions'
import { getPeople } from '../api/memorySearch'

export function TranscriptView({ recordingId }) {
  const [transcript, setTranscript] = useState(null)
  const [people, setPeople] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [editingSpeaker, setEditingSpeaker] = useState(null) // speaker object being edited
  const [newLabel, setNewLabel] = useState('')
  const [selectedPersonId, setSelectedPersonId] = useState('')
  const [savingSpeaker, setSavingSpeaker] = useState(false)

  const loadData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [tData, pData] = await Promise.all([
        getTranscript(recordingId),
        getPeople().catch(() => []),
      ])
      setTranscript(tData)
      setPeople(pData)
    } catch (err) {
      console.error('Transcript fetch failed:', err)
      setError(err.message || 'Transcript is not available yet')
    } finally {
      setLoading(false)
    }
  }, [recordingId])

  useEffect(() => {
    if (recordingId) {
      loadData()
    }
  }, [recordingId, loadData])

  const handleOpenRelabel = (speaker) => {
    setEditingSpeaker(speaker)
    setNewLabel(speaker.label || '')
    setSelectedPersonId(speaker.person_id || '')
  }

  const handleSaveSpeaker = async () => {
    if (!editingSpeaker) return
    setSavingSpeaker(true)
    try {
      await relabelSpeaker(recordingId, editingSpeaker.id, {
        label: newLabel.trim() || null,
        person_id: selectedPersonId ? parseInt(selectedPersonId, 10) : null,
      })
      setEditingSpeaker(null)
      await loadData() // Refresh transcript with updated speaker names
    } catch (err) {
      alert(`Speaker relabel failed: ${err.message}`)
    } finally {
      setSavingSpeaker(false)
    }
  }

  const formatTimestamp = (ms) => {
    if (ms === null || ms === undefined) return '00:00'
    const totalSecs = Math.floor(ms / 1000)
    const mins = Math.floor(totalSecs / 60)
    const secs = totalSecs % 60
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
  }

  if (loading) {
    return <div className="loading-spinner-box">Loading transcript & diarization...</div>
  }

  if (error) {
    return (
      <div className="transcript-error-box">
        <AlertCircle className="error-icon" />
        <div className="error-content">
          <span>{error}</span>
          <button className="btn btn-secondary btn-sm" onClick={loadData}>
            <RefreshCw className="btn-icon" /> Refresh Transcript
          </button>
        </div>
      </div>
    )
  }

  const segments = transcript?.segments || []
  const speakers = transcript?.speakers || []

  return (
    <div className="transcript-container">
      <div className="transcript-header">
        <h3>Transcript & Speaker Identification</h3>
        {transcript?.language && (
          <span className="language-badge">Detected Language: {transcript.language.toUpperCase()}</span>
        )}
      </div>

      {/* Speaker Relabel Summary Bar */}
      {speakers.length > 0 && (
        <div className="speakers-bar">
          <span className="speakers-label">Speakers ({speakers.length}):</span>
          <div className="speaker-chips">
            {speakers.map((spk) => (
              <button
                key={spk.id}
                className="speaker-chip"
                onClick={() => handleOpenRelabel(spk)}
                title="Click to rename or assign person"
              >
                <Tag className="chip-icon" />
                <span className="chip-name">{spk.label || spk.name || `Speaker ${spk.speaker_tag}`}</span>
                {spk.person_id && <UserCheck className="verified-icon" />}
                <Edit3 className="edit-icon" />
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Transcript Segments List */}
      <div className="segments-list">
        {segments.length === 0 ? (
          <div className="empty-state">No transcript segments found.</div>
        ) : (
          segments.map((seg) => {
            const speakerObj = speakers.find((s) => s.id === seg.speaker_id || s.speaker_tag === seg.speaker_tag)
            const speakerName = speakerObj?.label || speakerObj?.name || seg.speaker_label || 'Speaker'

            return (
              <div key={seg.id || seg.start_ms} className="segment-card">
                <div className="segment-meta">
                  <span className="segment-speaker" onClick={() => speakerObj && handleOpenRelabel(speakerObj)}>
                    {speakerName}
                  </span>
                  <span className="segment-time">
                    {formatTimestamp(seg.start_ms)} - {formatTimestamp(seg.end_ms)}
                  </span>
                </div>
                <div className="segment-text">{seg.text}</div>
              </div>
            )
          })
        )}
      </div>

      {/* Speaker Relabel Dialog Modal */}
      {editingSpeaker && (
        <div className="modal-overlay">
          <div className="modal-content">
            <div className="modal-header">
              <h3>Relabel Speaker</h3>
            </div>
            <div className="modal-body">
              <div className="form-group">
                <label>Speaker Name / Custom Label:</label>
                <input
                  type="text"
                  className="text-input"
                  value={newLabel}
                  onChange={(e) => setNewLabel(e.target.value)}
                  placeholder="e.g. John Doe, Interviewer"
                />
              </div>

              <div className="form-group">
                <label>Link to Person Entity (FR-29):</label>
                <select
                  className="select-input"
                  value={selectedPersonId}
                  onChange={(e) => setSelectedPersonId(e.target.value)}
                >
                  <option value="">-- No linked person --</option>
                  {people.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name} {p.organization ? `(${p.organization})` : ''}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div className="modal-footer">
              <button
                className="btn btn-secondary"
                onClick={() => setEditingSpeaker(null)}
                disabled={savingSpeaker}
              >
                Cancel
              </button>
              <button
                className="btn btn-primary"
                onClick={handleSaveSpeaker}
                disabled={savingSpeaker}
              >
                {savingSpeaker ? 'Saving...' : 'Save Label'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
