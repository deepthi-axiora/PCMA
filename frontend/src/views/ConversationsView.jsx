import { useState, useEffect, useCallback } from 'react'
import { MessageSquare, ArrowLeft, FileText, Sparkles, Volume2, Clock } from 'lucide-react'
import { getConversations, getConversationDetail } from '../api/conversations'
import { AudioPlayer } from '../components/AudioPlayer'
import { TranscriptView } from '../components/TranscriptView'
import { ExtractionView } from '../components/ExtractionView'
import { MomEditorModal } from '../components/MomEditorModal'

export function ConversationsView({ selectedId, onSelectConversation }) {
  const [conversations, setConversations] = useState([])
  const [loading, setLoading] = useState(true)
  const [activeConversation, setActiveConversation] = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)

  const [detailSubTab, setDetailSubTab] = useState('transcript') // transcript, extraction
  const [showMomModal, setShowMomModal] = useState(false)

  const loadConversations = useCallback(async () => {
    setLoading(true)
    try {
      const data = await getConversations()
      setConversations(data)
    } catch (err) {
      console.error('Failed to load conversations:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  const loadDetail = useCallback(async (id) => {
    setDetailLoading(true)
    try {
      const detail = await getConversationDetail(id)
      setActiveConversation(detail)
    } catch (err) {
      console.error('Failed to load conversation detail:', err)
    } finally {
      setDetailLoading(false)
    }
  }, [])

  useEffect(() => {
    loadConversations()
  }, [loadConversations])

  useEffect(() => {
    if (selectedId) {
      loadDetail(selectedId)
    } else {
      setActiveConversation(null)
    }
  }, [selectedId, loadDetail])

  // MASTER LIST VIEW
  if (!activeConversation) {
    return (
      <div className="view-pane conversations-view">
        <div className="view-header">
          <h2>Conversations Library</h2>
          <p className="subtitle">All recorded and processed audio meetings</p>
        </div>

        {loading ? (
          <div className="loading-spinner-box">Loading conversations...</div>
        ) : conversations.length === 0 ? (
          <div className="empty-state">No conversations recorded yet. Go to the Record tab to start your first session.</div>
        ) : (
          <div className="conversations-grid">
            {conversations.map((conv) => (
              <div
                key={conv.id}
                className="conversation-card"
                onClick={() => onSelectConversation(conv.id)}
              >
                <div className="conv-card-header">
                  <MessageSquare className="conv-icon" />
                  <span className="conv-title">Conversation #{conv.id}</span>
                </div>
                <div className="conv-meta">
                  <span><Clock className="meta-icon" /> {new Date(conv.created_at || conv.occurred_at).toLocaleString()}</span>
                </div>
                {conv.topics && conv.topics.length > 0 && (
                  <div className="conv-tags">
                    {conv.topics.slice(0, 3).map((t) => (
                      <span key={t.id || t.name} className="tag-pill">{t.name}</span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    )
  }

  // DETAIL VIEW
  return (
    <div className="view-pane conversation-detail-view">
      {/* Back button & Header */}
      <div className="detail-top-bar">
        <button className="btn btn-secondary btn-sm" onClick={() => onSelectConversation(null)}>
          <ArrowLeft className="btn-icon" /> All Conversations
        </button>
        <button className="btn btn-primary btn-sm" onClick={() => setShowMomModal(true)}>
          <FileText className="btn-icon" /> Minutes of Meeting (MOM)
        </button>
      </div>

      <div className="conversation-detail-card">
        <div className="detail-title-group">
          <h2>Conversation #{activeConversation.id}</h2>
          <span className="detail-date">
            Recorded: {new Date(activeConversation.created_at || activeConversation.occurred_at).toLocaleString()}
          </span>
        </div>

        {/* Encrypted Audio Player */}
        <AudioPlayer recordingId={activeConversation.recording_id || activeConversation.id} />

        {/* Detail Tabs */}
        <div className="detail-subtabs">
          <button
            className={`subtab-btn ${detailSubTab === 'transcript' ? 'active' : ''}`}
            onClick={() => setDetailSubTab('transcript')}
          >
            <Volume2 className="tab-icon" /> Transcript & Diarization
          </button>
          <button
            className={`subtab-btn ${detailSubTab === 'extraction' ? 'active' : ''}`}
            onClick={() => setDetailSubTab('extraction')}
          >
            <Sparkles className="tab-icon" /> AI Extracted Insights
          </button>
        </div>

        {detailLoading ? (
          <div className="loading-spinner-box">Loading conversation details...</div>
        ) : (
          <div className="detail-pane-content">
            {detailSubTab === 'transcript' && (
              <TranscriptView recordingId={activeConversation.recording_id || activeConversation.id} />
            )}
            {detailSubTab === 'extraction' && (
              <ExtractionView conversation={activeConversation} />
            )}
          </div>
        )}
      </div>

      {/* MOM Editor Modal */}
      <MomEditorModal
        conversationId={activeConversation.id}
        isOpen={showMomModal}
        onClose={() => setShowMomModal(false)}
      />
    </div>
  )
}
