import { useState } from 'react'
import { CheckSquare, HelpCircle, Users, Tag, Target, Clock, ShieldAlert, Award } from 'lucide-react'

export function ExtractionView({ conversation }) {
  const [activeTab, setActiveTab] = useState('topics')

  if (!conversation) return <div className="empty-state">No conversation selected</div>

  const topics = conversation.topics || []
  const actionItems = conversation.action_items || []
  const commitments = conversation.commitments || []
  const decisions = conversation.decisions || []
  const deadlines = conversation.deadlines || []
  const questions = conversation.questions || []
  const people = conversation.people || []
  const organizations = conversation.organizations || []

  const getConfidenceBadge = (score) => {
    if (score === null || score === undefined) return null
    const pct = Math.round(score * 100)
    let colorClass = 'badge-high'
    if (pct < 60) colorClass = 'badge-low'
    else if (pct < 85) colorClass = 'badge-medium'

    return (
      <span className={`confidence-chip ${colorClass}`} title="AI Extraction Confidence">
        <Award className="chip-icon" /> {pct}% Confidence
      </span>
    )
  }

  return (
    <div className="extraction-container">
      {/* Sub tabs for extracted intelligence categories */}
      <div className="extraction-tabs">
        <button
          className={`tab-btn ${activeTab === 'topics' ? 'active' : ''}`}
          onClick={() => setActiveTab('topics')}
        >
          <Tag className="tab-icon" /> Topics ({topics.length})
        </button>
        <button
          className={`tab-btn ${activeTab === 'actions' ? 'active' : ''}`}
          onClick={() => setActiveTab('actions')}
        >
          <CheckSquare className="tab-icon" /> Action Items ({actionItems.length})
        </button>
        <button
          className={`tab-btn ${activeTab === 'commitments' ? 'active' : ''}`}
          onClick={() => setActiveTab('commitments')}
        >
          <Target className="tab-icon" /> Commitments ({commitments.length})
        </button>
        <button
          className={`tab-btn ${activeTab === 'decisions' ? 'active' : ''}`}
          onClick={() => setActiveTab('decisions')}
        >
          <ShieldAlert className="tab-icon" /> Decisions ({decisions.length})
        </button>
        <button
          className={`tab-btn ${activeTab === 'deadlines' ? 'active' : ''}`}
          onClick={() => setActiveTab('deadlines')}
        >
          <Clock className="tab-icon" /> Deadlines ({deadlines.length})
        </button>
        <button
          className={`tab-btn ${activeTab === 'questions' ? 'active' : ''}`}
          onClick={() => setActiveTab('questions')}
        >
          <HelpCircle className="tab-icon" /> Questions ({questions.length})
        </button>
        <button
          className={`tab-btn ${activeTab === 'entities' ? 'active' : ''}`}
          onClick={() => setActiveTab('entities')}
        >
          <Users className="tab-icon" /> People & Orgs ({people.length + organizations.length})
        </button>
      </div>

      {/* Content Panes */}
      <div className="extraction-content">
        {activeTab === 'topics' && (
          <div className="intelligence-grid">
            {topics.length === 0 ? (
              <div className="empty-state">No topics detected</div>
            ) : (
              topics.map((t) => (
                <div key={t.id || t.name} className="intelligence-card">
                  <div className="card-title">
                    <Tag className="card-icon" />
                    <span>{t.name}</span>
                  </div>
                  {t.summary && <p className="card-body">{t.summary}</p>}
                </div>
              ))
            )}
          </div>
        )}

        {activeTab === 'actions' && (
          <div className="intelligence-list">
            {actionItems.length === 0 ? (
              <div className="empty-state">No action items extracted</div>
            ) : (
              actionItems.map((item) => (
                <div key={item.id} className="intelligence-card">
                  <div className="card-header-flex">
                    <span className="item-text">{item.description || item.title}</span>
                    {getConfidenceBadge(item.confidence)}
                  </div>
                  {item.assignee && (
                    <div className="item-meta">
                      <strong>Assignee:</strong> {item.assignee}
                    </div>
                  )}
                  {item.provenance && (
                    <div className="provenance-quote">
                      <em>"{item.provenance}"</em>
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        )}

        {activeTab === 'commitments' && (
          <div className="intelligence-list">
            {commitments.length === 0 ? (
              <div className="empty-state">No commitments extracted</div>
            ) : (
              commitments.map((c) => (
                <div key={c.id} className="intelligence-card">
                  <div className="card-header-flex">
                    <span className="item-text">{c.title || c.commitment_text}</span>
                    {getConfidenceBadge(c.confidence)}
                  </div>
                  <div className="item-meta">
                    <span>Status: <strong>{c.status || 'open'}</strong></span>
                    {c.due_date && <span>Due: {new Date(c.due_date).toLocaleDateString()}</span>}
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {activeTab === 'decisions' && (
          <div className="intelligence-list">
            {decisions.length === 0 ? (
              <div className="empty-state">No decisions recorded</div>
            ) : (
              decisions.map((d) => (
                <div key={d.id} className="intelligence-card">
                  <div className="card-header-flex">
                    <span className="item-text">{d.description || d.text}</span>
                    {getConfidenceBadge(d.confidence)}
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {activeTab === 'deadlines' && (
          <div className="intelligence-list">
            {deadlines.length === 0 ? (
              <div className="empty-state">No deadlines identified</div>
            ) : (
              deadlines.map((dl) => (
                <div key={dl.id} className="intelligence-card">
                  <div className="card-header-flex">
                    <span className="item-text">{dl.description || dl.title}</span>
                    <span className="deadline-date">{dl.due_date}</span>
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {activeTab === 'questions' && (
          <div className="intelligence-list">
            {questions.length === 0 ? (
              <div className="empty-state">No open questions extracted</div>
            ) : (
              questions.map((q) => (
                <div key={q.id} className="intelligence-card">
                  <div className="item-text">
                    <HelpCircle className="card-icon-inline" /> {q.question_text || q.question}
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {activeTab === 'entities' && (
          <div className="entities-dual-grid">
            <div className="entity-column">
              <h4>People Mentioned</h4>
              {people.length === 0 ? (
                <div className="empty-state">No people identified</div>
              ) : (
                people.map((p) => (
                  <div key={p.id} className="entity-chip-card">
                    <strong>{p.name}</strong>
                    {p.title && <span>{p.title}</span>}
                  </div>
                ))
              )}
            </div>

            <div className="entity-column">
              <h4>Organizations</h4>
              {organizations.length === 0 ? (
                <div className="empty-state">No organizations identified</div>
              ) : (
                organizations.map((org) => (
                  <div key={org.id || org.name} className="entity-chip-card">
                    <strong>{org.name}</strong>
                  </div>
                ))
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
