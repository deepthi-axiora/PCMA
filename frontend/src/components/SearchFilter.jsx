import { useState, useEffect, useCallback } from 'react'
import { Search, Brain, Calendar, Filter, User, Folder, Tag, Sparkles } from 'lucide-react'
import { searchConversations, getPersonalMemories, getPeople, getProjects, getTopics } from '../api/memorySearch'

export function SearchFilter({ onSelectConversation }) {
  const [activeTab, setActiveTab] = useState('search') // search, memory

  // Filters
  const [query, setQuery] = useState('')
  const [selectedPerson, setSelectedPerson] = useState('')
  const [selectedProject, setSelectedProject] = useState('')
  const [selectedTopic, setSelectedTopic] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')

  // Entity dropdown options
  const [people, setPeople] = useState([])
  const [projects, setProjects] = useState([])
  const [topics, setTopics] = useState([])

  // Results
  const [results, setResults] = useState([])
  const [memories, setMemories] = useState([])
  const [searching, setSearching] = useState(false)
  const [loadingMemories, setLoadingMemories] = useState(false)

  // Load filter options on mount
  useEffect(() => {
    Promise.all([
      getPeople().catch(() => []),
      getProjects().catch(() => []),
      getTopics().catch(() => []),
    ]).then(([pData, projData, tData]) => {
      setPeople(pData)
      setProjects(projData)
      setTopics(tData)
    })
  }, [])

  const executeSearch = useCallback(async () => {
    setSearching(true)
    try {
      const data = await searchConversations({
        query: query.trim() || undefined,
        person_id: selectedPerson || undefined,
        project_id: selectedProject || undefined,
        topic_id: selectedTopic || undefined,
        start_date: startDate || undefined,
        end_date: endDate || undefined,
      })
      setResults(data)
    } catch (err) {
      console.error('Search failed:', err)
    } finally {
      setSearching(false)
    }
  }, [query, selectedPerson, selectedProject, selectedTopic, startDate, endDate])

  const loadMemories = useCallback(async () => {
    setLoadingMemories(true)
    try {
      const data = await getPersonalMemories()
      setMemories(data)
    } catch (err) {
      console.error('Memories load failed:', err)
    } finally {
      setLoadingMemories(false)
    }
  }, [])

  useEffect(() => {
    if (activeTab === 'memory') {
      loadMemories()
    }
  }, [activeTab, loadMemories])

  return (
    <div className="search-memory-container">
      {/* Sub Tabs */}
      <div className="search-subtabs">
        <button
          className={`subtab-btn ${activeTab === 'search' ? 'active' : ''}`}
          onClick={() => setActiveTab('search')}
        >
          <Search className="tab-icon" /> Conversation Search (FR-32)
        </button>
        <button
          className={`subtab-btn ${activeTab === 'memory' ? 'active' : ''}`}
          onClick={() => setActiveTab('memory')}
        >
          <Brain className="tab-icon" /> Personal Memory (FR-33)
        </button>
      </div>

      {activeTab === 'search' && (
        <div className="search-pane">
          {/* Multi-filter Form */}
          <div className="filter-card">
            <div className="search-input-group">
              <Search className="search-icon" />
              <input
                type="text"
                className="search-input"
                placeholder="Search keywords, topics, decisions..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && executeSearch()}
              />
              <button className="btn btn-primary" onClick={executeSearch} disabled={searching}>
                {searching ? 'Searching...' : 'Search'}
              </button>
            </div>

            <div className="filters-row">
              <div className="filter-select-wrapper">
                <User className="select-icon" />
                <select
                  className="select-input"
                  value={selectedPerson}
                  onChange={(e) => setSelectedPerson(e.target.value)}
                >
                  <option value="">All People</option>
                  {people.map((p) => (
                    <option key={p.id} value={p.id}>{p.name}</option>
                  ))}
                </select>
              </div>

              <div className="filter-select-wrapper">
                <Folder className="select-icon" />
                <select
                  className="select-input"
                  value={selectedProject}
                  onChange={(e) => setSelectedProject(e.target.value)}
                >
                  <option value="">All Projects</option>
                  {projects.map((pr) => (
                    <option key={pr.id} value={pr.id}>{pr.name}</option>
                  ))}
                </select>
              </div>

              <div className="filter-select-wrapper">
                <Tag className="select-icon" />
                <select
                  className="select-input"
                  value={selectedTopic}
                  onChange={(e) => setSelectedTopic(e.target.value)}
                >
                  <option value="">All Topics</option>
                  {topics.map((t) => (
                    <option key={t.id} value={t.id}>{t.name}</option>
                  ))}
                </select>
              </div>

              <div className="filter-date-wrapper">
                <Calendar className="select-icon" />
                <input
                  type="date"
                  className="date-input"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  placeholder="From"
                />
                <span>to</span>
                <input
                  type="date"
                  className="date-input"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  placeholder="To"
                />
              </div>
            </div>
          </div>

          {/* Results List */}
          <div className="search-results-list">
            <h4>Search Results ({results.length})</h4>
            {searching ? (
              <div className="loading-spinner-box">Searching conversations...</div>
            ) : results.length === 0 ? (
              <div className="empty-state">No matching conversations found.</div>
            ) : (
              results.map((item) => (
                <div
                  key={item.id}
                  className="search-result-card"
                  onClick={() => onSelectConversation && onSelectConversation(item.id)}
                >
                  <div className="result-title">Conversation #{item.id}</div>
                  <div className="result-meta">
                    <span>Recorded: {new Date(item.created_at || item.occurred_at).toLocaleString()}</span>
                  </div>
                  {item.snippet && <p className="result-snippet">"...{item.snippet}..."</p>}
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {activeTab === 'memory' && (
        <div className="memory-pane">
          <div className="memory-header-banner">
            <Sparkles className="banner-icon" />
            <div>
              <h4>Personal Memory Bank (FR-33)</h4>
              <p>User-scoped cross-conversation memory recalled automatically from your interactions.</p>
            </div>
          </div>

          {loadingMemories ? (
            <div className="loading-spinner-box">Loading personal memory bank...</div>
          ) : memories.length === 0 ? (
            <div className="empty-state">No personal memories created yet.</div>
          ) : (
            <div className="memories-grid">
              {memories.map((mem) => (
                <div key={mem.id} className="memory-card">
                  <div className="memory-content">{mem.content || mem.memory_text}</div>
                  <div className="memory-footer">
                    <span>Source: Conversation #{mem.conversation_id || 'System'}</span>
                    <span>{new Date(mem.created_at).toLocaleDateString()}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
