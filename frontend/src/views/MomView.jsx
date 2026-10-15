import { useState, useEffect, useCallback } from 'react'
import { FileText, Edit, Plus } from 'lucide-react'
import { getConversations } from '../api/conversations'
import { MomEditorModal } from '../components/MomEditorModal'

export function MomView() {
  const [conversations, setConversations] = useState([])
  const [loading, setLoading] = useState(true)
  const [activeConversationId, setActiveConversationId] = useState(null)

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const data = await getConversations()
      setConversations(data)
    } catch (err) {
      console.error('Failed to load conversations for MOM:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData()
  }, [loadData])

  return (
    <div className="view-pane mom-view">
      <div className="view-header">
        <h2>Minutes of Meeting (MOM) Center</h2>
        <p className="subtitle">Generate, edit, approve, share, and export official meeting minutes</p>
      </div>

      {loading ? (
        <div className="loading-spinner-box">Loading meeting records...</div>
      ) : conversations.length === 0 ? (
        <div className="empty-state">No conversations recorded yet. Record a meeting first to generate MOM.</div>
      ) : (
        <div className="conversations-grid">
          {conversations.map((conv) => (
            <div key={conv.id} className="conversation-card mom-card">
              <div className="conv-card-header">
                <FileText className="conv-icon" />
                <span className="conv-title">MOM for Conversation #{conv.id}</span>
              </div>
              <div className="conv-meta">
                <span>Recorded: {new Date(conv.created_at || conv.occurred_at).toLocaleDateString()}</span>
              </div>
              <button className="btn btn-primary btn-sm" onClick={() => setActiveConversationId(conv.id)}>
                <Edit className="btn-icon" /> Manage / Edit MOM
              </button>
            </div>
          ))}
        </div>
      )}

      {activeConversationId && (
        <MomEditorModal
          conversationId={activeConversationId}
          isOpen={Boolean(activeConversationId)}
          onClose={() => setActiveConversationId(null)}
        />
      )}
    </div>
  )
}
