import { useState, useEffect, useCallback } from 'react'
import {
  FileText,
  CheckCircle2,
  Edit,
  History,
  Share2,
  Download,
  Trash2,
  AlertCircle,
  Clock,
  Send,
} from 'lucide-react'
import {
  generateMom,
  getMom,
  updateMom,
  approveMom,
  getMomHistory,
  shareMom,
  getMomShares,
  revokeMomShare,
  exportMom,
} from '../api/moms'

export function MomEditorModal({ conversationId, isOpen, onClose }) {
  const [mom, setMom] = useState(null)
  const [history, setHistory] = useState([])
  const [shares, setShares] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [activeSubTab, setActiveSubTab] = useState('editor') // editor, history, share, export

  // Edit form state
  const [title, setTitle] = useState('')
  const [summary, setSummary] = useState('')
  const [isEditing, setIsEditing] = useState(false)
  const [saving, setSaving] = useState(false)

  // Share form state
  const [recipientEmail, setRecipientEmail] = useState('')
  const [sharing, setSharing] = useState(false)

  // Export format state
  const [exportFormat, setExportFormat] = useState('markdown')

  const loadMomData = useCallback(async () => {
    if (!conversationId) return
    setLoading(true)
    setError(null)
    try {
      let data
      try {
        data = await getMom(conversationId)
      } catch (getErr) {
        // If MOM doesn't exist yet, trigger generation
        if (getErr.status === 404) {
          data = await generateMom(conversationId)
        } else {
          throw getErr
        }
      }

      setMom(data)
      setTitle(data.title || '')
      setSummary(data.summary || '')

      if (data.id) {
        // Load history & shares in parallel
        const [histData, shareData] = await Promise.all([
          getMomHistory(data.id).catch(() => []),
          getMomShares(data.id).catch(() => []),
        ])
        setHistory(histData)
        setShares(shareData)
      }
    } catch (err) {
      console.error('MOM load error:', err)
      setError(err.message || 'Failed to load Minutes of Meeting')
    } finally {
      setLoading(false)
    }
  }, [conversationId])

  useEffect(() => {
    if (isOpen && conversationId) {
      loadMomData()
    }
  }, [isOpen, conversationId, loadMomData])

  const handleSaveDraft = async () => {
    if (!mom) return
    setSaving(true)
    try {
      const updated = await updateMom(mom.id, {
        title,
        summary,
      })
      setMom(updated)
      setIsEditing(false)
      await loadMomData()
    } catch (err) {
      alert(`Save failed: ${err.message}`)
    } finally {
      setSaving(false)
    }
  }

  const handleApprove = async () => {
    if (!mom) return
    if (!window.confirm('Approve this MOM? Once approved, it can be shared and exported.')) return
    setSaving(true)
    try {
      const approved = await approveMom(mom.id)
      setMom(approved)
      await loadMomData()
    } catch (err) {
      alert(`Approval failed: ${err.message}`)
    } finally {
      setSaving(false)
    }
  }

  const handleShare = async (e) => {
    e.preventDefault()
    if (!recipientEmail || !mom) return
    setSharing(true)
    try {
      await shareMom(mom.id, recipientEmail)
      setRecipientEmail('')
      const updatedShares = await getMomShares(mom.id)
      setShares(updatedShares)
      alert('MOM shared successfully!')
    } catch (err) {
      alert(`Share failed: ${err.message}`)
    } finally {
      setSharing(false)
    }
  }

  const handleRevokeShare = async (shareId) => {
    if (!mom || !window.confirm('Revoke access for this recipient?')) return
    try {
      await revokeMomShare(mom.id, shareId)
      const updatedShares = await getMomShares(mom.id)
      setShares(updatedShares)
    } catch (err) {
      alert(`Revoke failed: ${err.message}`)
    }
  }

  const handleExport = async () => {
    if (!mom) return
    try {
      const result = await exportMom(mom.id, exportFormat)
      let blob
      if (result instanceof Blob) {
        blob = result
      } else {
        const textContent = typeof result === 'string' ? result : JSON.stringify(result, null, 2)
        blob = new Blob([textContent], { type: 'text/plain;charset=utf-8' })
      }

      const downloadUrl = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = downloadUrl
      a.download = `MOM_${mom.id}_${exportFormat}.${exportFormat === 'markdown' ? 'md' : exportFormat}`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(downloadUrl)
    } catch (err) {
      alert(`Export failed: ${err.message}`)
    }
  }

  if (!isOpen) return null

  const isApproved = mom?.status === 'approved'

  return (
    <div className="modal-overlay">
      <div className="modal-content mom-modal">
        <div className="modal-header">
          <FileText className="modal-header-icon" />
          <div className="header-text-group">
            <h2>Minutes of Meeting (MOM)</h2>
            {mom && (
              <span className={`status-badge-inline ${isApproved ? 'approved' : 'draft'}`}>
                {isApproved ? 'Approved' : 'Draft'}
              </span>
            )}
          </div>
          <button className="close-btn" onClick={onClose}>
            &times;
          </button>
        </div>

        {/* Modal Navigation Sub-Tabs */}
        <div className="mom-tabs">
          <button
            className={`subtab-btn ${activeSubTab === 'editor' ? 'active' : ''}`}
            onClick={() => setActiveSubTab('editor')}
          >
            <Edit className="tab-icon" /> Document Editor
          </button>
          <button
            className={`subtab-btn ${activeSubTab === 'history' ? 'active' : ''}`}
            onClick={() => setActiveSubTab('history')}
          >
            <History className="tab-icon" /> Audit & Edit History ({history.length})
          </button>
          <button
            className={`subtab-btn ${activeSubTab === 'share' ? 'active' : ''}`}
            onClick={() => setActiveSubTab('share')}
          >
            <Share2 className="tab-icon" /> Sharing ({shares.length})
          </button>
          <button
            className={`subtab-btn ${activeSubTab === 'export' ? 'active' : ''}`}
            onClick={() => setActiveSubTab('export')}
          >
            <Download className="tab-icon" /> Export
          </button>
        </div>

        <div className="modal-body">
          {loading ? (
            <div className="loading-spinner-box">Generating & loading MOM data...</div>
          ) : error ? (
            <div className="error-banner">
              <AlertCircle className="error-icon" />
              <span>{error}</span>
            </div>
          ) : (
            <>
              {/* SUBTAB 1: EDITOR */}
              {activeSubTab === 'editor' && (
                <div className="mom-editor-pane">
                  {!isEditing && !isApproved && (
                    <button className="btn btn-secondary btn-sm edit-trigger" onClick={() => setIsEditing(true)}>
                      <Edit className="btn-icon" /> Edit Draft
                    </button>
                  )}

                  {isEditing ? (
                    <div className="edit-form">
                      <div className="form-group">
                        <label>MOM Title:</label>
                        <input
                          type="text"
                          className="text-input"
                          value={title}
                          onChange={(e) => setTitle(e.target.value)}
                        />
                      </div>
                      <div className="form-group">
                        <label>Executive Summary / Notes:</label>
                        <textarea
                          rows={8}
                          className="textarea-input"
                          value={summary}
                          onChange={(e) => setSummary(e.target.value)}
                        />
                      </div>
                      <div className="form-actions">
                        <button className="btn btn-secondary" onClick={() => setIsEditing(false)}>
                          Cancel
                        </button>
                        <button className="btn btn-primary" onClick={handleSaveDraft} disabled={saving}>
                          {saving ? 'Saving...' : 'Save Changes'}
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="mom-preview-doc">
                      <h3 className="doc-title">{mom?.title}</h3>
                      <div className="doc-meta">
                        <span>Status: <strong>{mom?.status}</strong></span>
                        <span>Created: {new Date(mom?.created_at).toLocaleString()}</span>
                      </div>
                      <div className="doc-section">
                        <h4>Executive Summary</h4>
                        <p>{mom?.summary || 'No summary content.'}</p>
                      </div>

                      {/* Display sections if present */}
                      {mom?.sections && mom.sections.length > 0 && (
                        <div className="doc-sections-list">
                          {mom.sections.map((sec, idx) => (
                            <div key={idx} className="doc-section">
                              <h4>{sec.heading}</h4>
                              <p>{sec.content}</p>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}

              {/* SUBTAB 2: HISTORY */}
              {activeSubTab === 'history' && (
                <div className="mom-history-pane">
                  {history.length === 0 ? (
                    <div className="empty-state">No previous revisions recorded.</div>
                  ) : (
                    history.map((item) => (
                      <div key={item.id} className="history-card">
                        <div className="history-header">
                          <Clock className="history-icon" />
                          <span>Revision #{item.id}</span>
                          <span className="history-date">{new Date(item.created_at || item.edited_at).toLocaleString()}</span>
                        </div>
                        <p className="history-diff"><strong>Summary Diff:</strong> {item.summary}</p>
                      </div>
                    ))
                  )}
                </div>
              )}

              {/* SUBTAB 3: SHARING */}
              {activeSubTab === 'share' && (
                <div className="mom-share-pane">
                  {!isApproved ? (
                    <div className="info-banner">
                      <AlertCircle className="info-icon" />
                      <span>MOM must be <strong>Approved</strong> before sharing with external recipients.</span>
                    </div>
                  ) : (
                    <>
                      <form onSubmit={handleShare} className="share-form">
                        <input
                          type="email"
                          required
                          className="text-input"
                          placeholder="Recipient email address"
                          value={recipientEmail}
                          onChange={(e) => setRecipientEmail(e.target.value)}
                        />
                        <button type="submit" className="btn btn-primary" disabled={sharing}>
                          <Send className="btn-icon" /> {sharing ? 'Sending...' : 'Share MOM'}
                        </button>
                      </form>

                      <div className="shares-list">
                        <h4>Active Share Recipient Links ({shares.length})</h4>
                        {shares.length === 0 ? (
                          <div className="empty-state">No external shares created yet.</div>
                        ) : (
                          shares.map((sh) => (
                            <div key={sh.id} className="share-item-card">
                              <div className="share-info">
                                <strong>{sh.recipient_email}</strong>
                                <span className="share-date">Shared: {new Date(sh.created_at).toLocaleDateString()}</span>
                              </div>
                              <button className="btn btn-danger btn-sm" onClick={() => handleRevokeShare(sh.id)}>
                                <Trash2 className="btn-icon" /> Revoke
                              </button>
                            </div>
                          ))
                        )}
                      </div>
                    </>
                  )}
                </div>
              )}

              {/* SUBTAB 4: EXPORT */}
              {activeSubTab === 'export' && (
                <div className="mom-export-pane">
                  <h4>Select Export Format:</h4>
                  <div className="format-options">
                    {['markdown', 'txt', 'json', 'pdf'].map((fmt) => (
                      <label key={fmt} className={`format-radio ${exportFormat === fmt ? 'selected' : ''}`}>
                        <input
                          type="radio"
                          name="exportFormat"
                          value={fmt}
                          checked={exportFormat === fmt}
                          onChange={() => setExportFormat(fmt)}
                        />
                        <span>{fmt.toUpperCase()} Format</span>
                      </label>
                    ))}
                  </div>

                  <button className="btn btn-primary btn-export" onClick={handleExport}>
                    <Download className="btn-icon" /> Download Export ({exportFormat.toUpperCase()})
                  </button>
                </div>
              )}
            </>
          )}
        </div>

        <div className="modal-footer">
          {mom && !isApproved && (
            <button className="btn btn-success" onClick={handleApprove} disabled={saving}>
              <CheckCircle2 className="btn-icon" /> Approve MOM
            </button>
          )}
          <button className="btn btn-secondary" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  )
}
