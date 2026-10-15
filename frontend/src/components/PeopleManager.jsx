import { useState, useEffect, useCallback } from 'react'
import { UserPlus, GitMerge, UserCheck, AlertCircle } from 'lucide-react'
import { getPeople, createPerson, mergePeople } from '../api/memorySearch'

export function PeopleManager() {
  const [people, setPeople] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Create person state
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [organization, setOrganization] = useState('')
  const [title, setTitle] = useState('')
  const [creating, setCreating] = useState(false)

  // Merge state
  const [sourcePersonId, setSourcePersonId] = useState('')
  const [targetPersonId, setTargetPersonId] = useState('')
  const [merging, setMerging] = useState(false)

  const loadPeople = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await getPeople()
      setPeople(data)
    } catch (err) {
      console.error('People fetch error:', err)
      setError(err.message || 'Failed to load people directory')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadPeople()
  }, [loadPeople])

  const handleCreatePerson = async (e) => {
    e.preventDefault()
    if (!name.trim()) return
    setCreating(true)
    try {
      await createPerson({ name: name.trim(), email: email.trim() || undefined, organization: organization.trim() || undefined, title: title.trim() || undefined })
      setName('')
      setEmail('')
      setOrganization('')
      setTitle('')
      await loadPeople()
    } catch (err) {
      alert(`Create person failed: ${err.message}`)
    } finally {
      setCreating(false)
    }
  }

  const handleMergePeople = async (e) => {
    e.preventDefault()
    if (!sourcePersonId || !targetPersonId || sourcePersonId === targetPersonId) return
    if (!window.confirm('Merge source person into target person? This action consolidates speaker references.')) return
    setMerging(true)
    try {
      await mergePeople(parseInt(sourcePersonId, 10), parseInt(targetPersonId, 10))
      setSourcePersonId('')
      setTargetPersonId('')
      await loadPeople()
      alert('People merged successfully!')
    } catch (err) {
      alert(`Merge failed: ${err.message}`)
    } finally {
      setMerging(false)
    }
  }

  return (
    <div className="entity-manager-pane">
      <h3>People Management (FR-29)</h3>

      {error && <div className="error-banner">{error}</div>}

      {/* Create Form */}
      <form onSubmit={handleCreatePerson} className="form-card">
        <h4><UserPlus className="form-icon" /> Add New Person</h4>
        <div className="form-row-grid">
          <input
            type="text"
            required
            className="text-input"
            placeholder="Full Name *"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <input
            type="email"
            className="text-input"
            placeholder="Email Address"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <input
            type="text"
            className="text-input"
            placeholder="Organization"
            value={organization}
            onChange={(e) => setOrganization(e.target.value)}
          />
          <input
            type="text"
            className="text-input"
            placeholder="Title / Role"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
        </div>
        <button type="submit" className="btn btn-primary" disabled={creating}>
          {creating ? 'Saving...' : 'Add Person'}
        </button>
      </form>

      {/* Merge Form */}
      {people.length >= 2 && (
        <form onSubmit={handleMergePeople} className="form-card merge-card">
          <h4><GitMerge className="form-icon" /> Merge Duplicate People</h4>
          <div className="form-row-grid">
            <select
              className="select-input"
              value={sourcePersonId}
              onChange={(e) => setSourcePersonId(e.target.value)}
            >
              <option value="">Select Source Person (to merge from)...</option>
              {people.map((p) => (
                <option key={p.id} value={p.id}>{p.name} ({p.organization || 'No org'})</option>
              ))}
            </select>

            <select
              className="select-input"
              value={targetPersonId}
              onChange={(e) => setTargetPersonId(e.target.value)}
            >
              <option value="">Select Target Person (to keep)...</option>
              {people.map((p) => (
                <option key={p.id} value={p.id}>{p.name} ({p.organization || 'No org'})</option>
              ))}
            </select>
          </div>
          <button type="submit" className="btn btn-secondary" disabled={merging}>
            {merging ? 'Merging...' : 'Merge People'}
          </button>
        </form>
      )}

      {/* People Directory List */}
      <div className="directory-list">
        <h4>People Directory ({people.length})</h4>
        {loading ? (
          <div className="loading-spinner-box">Loading directory...</div>
        ) : people.length === 0 ? (
          <div className="empty-state">No people registered yet.</div>
        ) : (
          <div className="people-grid">
            {people.map((p) => (
              <div key={p.id} className="person-card">
                <div className="person-name"><UserCheck className="person-icon" /> {p.name}</div>
                {p.title && <div className="person-detail">{p.title}</div>}
                {p.organization && <div className="person-detail">{p.organization}</div>}
                {p.email && <div className="person-email">{p.email}</div>}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
