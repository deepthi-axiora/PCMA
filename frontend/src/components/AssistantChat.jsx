import { useState } from 'react'
import { Bot, Send, User, ExternalLink, HelpCircle, ShieldCheck, AlertCircle } from 'lucide-react'
import { askAssistant } from '../api/assistant'

export function AssistantChat({ onSelectConversation }) {
  const [query, setQuery] = useState('')
  const [messages, setMessages] = useState([
    {
      id: 'welcome',
      sender: 'assistant',
      text: 'Hello! I am your Personal Conversation Memory Assistant. Ask me anything about your recorded meetings, action items, or past commitments.',
      source_ids: [],
    },
  ])
  const [loading, setLoading] = useState(false)

  const handleSend = async (e) => {
    e.preventDefault()
    if (!query.trim() || loading) return

    const userMsg = {
      id: `usr_${Date.now()}`,
      sender: 'user',
      text: query.trim(),
    }

    setMessages((prev) => [...prev, userMsg])
    const currentQuery = query.trim()
    setQuery('')
    setLoading(true)

    try {
      const response = await askAssistant(currentQuery)
      const assistantMsg = {
        id: `ast_${Date.now()}`,
        sender: 'assistant',
        text: response.answer || 'No relevant information found.',
        source_ids: response.source_ids || response.sources || [],
        confidence: response.confidence,
      }
      setMessages((prev) => [...prev, assistantMsg])
    } catch (err) {
      console.error('Assistant query error:', err)
      const errorMsg = {
        id: `err_${Date.now()}`,
        sender: 'assistant',
        text: `Sorry, I encountered an error answering your question: ${err.message}`,
        isError: true,
      }
      setMessages((prev) => [...prev, errorMsg])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="assistant-chat-container">
      <div className="chat-header">
        <Bot className="header-bot-icon" />
        <div>
          <h3>Personal Assistant (FR-36)</h3>
          <span className="subtitle">Bounded LLM Memory Answer Generation</span>
        </div>
      </div>

      {/* Messages Thread */}
      <div className="chat-thread">
        {messages.map((msg) => (
          <div key={msg.id} className={`chat-bubble-wrapper bubble-${msg.sender}`}>
            <div className="avatar-cell">
              {msg.sender === 'user' ? <User className="avatar-icon" /> : <Bot className="avatar-icon bot-avatar" />}
            </div>

            <div className={`chat-bubble ${msg.isError ? 'bubble-error' : ''}`}>
              <div className="bubble-text">{msg.text}</div>

              {/* Source Provenance Links */}
              {msg.source_ids && msg.source_ids.length > 0 && (
                <div className="bubble-sources">
                  <span className="sources-label">Source Evidence:</span>
                  <div className="source-links">
                    {msg.source_ids.map((srcId) => (
                      <button
                        key={srcId}
                        className="source-chip"
                        onClick={() => onSelectConversation && onSelectConversation(srcId)}
                      >
                        <ExternalLink className="chip-icon" /> Conversation #{srcId}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="chat-bubble-wrapper bubble-assistant">
            <div className="avatar-cell">
              <Bot className="avatar-icon bot-avatar spin" />
            </div>
            <div className="chat-bubble loading-bubble">
              Analyzing memory bank & generating bounded answer...
            </div>
          </div>
        )}
      </div>

      {/* Input Box */}
      <form onSubmit={handleSend} className="chat-input-bar">
        <input
          type="text"
          className="chat-input"
          placeholder="Ask a question about your conversations..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          disabled={loading}
        />
        <button type="submit" className="btn btn-primary send-btn" disabled={loading || !query.trim()}>
          <Send className="btn-icon" />
        </button>
      </form>
    </div>
  )
}
