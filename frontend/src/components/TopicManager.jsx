import { useState, useEffect, useCallback } from 'react'
import { Tag, GitMerge } from 'lucide-react'
import { getTopics, mergeTopics } from '../api/memorySearch'

export function TopicManager() {
  const [topics, setTopics] = useState([])
  const [loading, setLoading] = useState(true)

  const [sourceTopicId, setSourceTopicId] = useState('')
  const [targetTopicId, setTargetTopicId] = useState('')
  const [merging, setMerging] = useState(false)

  const loadTopics = useCallback(async () => {
    setLoading(true)
    try {
      const data = await getTopics()
      setTopics(data)
    } catch (err) {
      console.error('Topics fetch failed:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadTopics()
  }, [loadTopics])

  const handleMerge = async (e) => {
    e.preventDefault()
    if (!sourceTopicId || !targetTopicId || sourceTopicId === targetTopicId) return
    if (!window.confirm('Merge source topic into target topic?')) return
    setMerging(true)
    try {
      await mergeTopics(parseInt(sourceTopicId, 10), parseInt(targetTopicId, 10))
      setSourceTopicId('')
      setTargetTopicId('')
      await loadTopics()
      alert('Topics merged successfully!')
    } catch (err) {
      alert(`Merge failed: ${err.message}`)
    } finally {
      setMerging(false)
    }
  }

  return (
    <div className="entity-manager-pane">
      <h3>Topic Management (FR-31)</h3>

      {topics.length >= 2 && (
        <form onSubmit={handleMerge} className="form-card merge-card">
          <h4><GitMerge className="form-icon" /> Merge Duplicate Topics</h4>
          <div className="form-row-grid">
            <select
              className="select-input"
              value={sourceTopicId}
              onChange={(e) => setSourceTopicId(e.target.value)}
            >
              <option value="">Select Source Topic (to merge from)...</option>
              {topics.map((t) => (
                <option key={t.id} value={t.id}>{t.name}</option>
              ))}
            </select>

            <select
              className="select-input"
              value={targetTopicId}
              onChange={(e) => setTargetTopicId(e.target.value)}
            >
              <option value="">Select Target Topic (to keep)...</option>
              {topics.map((t) => (
                <option key={t.id} value={t.id}>{t.name}</option>
              ))}
            </select>
          </div>
          <button type="submit" className="btn btn-secondary" disabled={merging}>
            {merging ? 'Merging...' : 'Merge Topics'}
          </button>
        </form>
      )}

      <div className="directory-list">
        <h4>All Extracted Topics ({topics.length})</h4>
        {loading ? (
          <div className="loading-spinner-box">Loading topics...</div>
        ) : topics.length === 0 ? (
          <div className="empty-state">No topics detected in recorded conversations.</div>
        ) : (
          <div className="topics-chips-grid">
            {topics.map((t) => (
              <div key={t.id} className="topic-chip-box">
                <Tag className="chip-icon" />
                <span>{t.name}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
