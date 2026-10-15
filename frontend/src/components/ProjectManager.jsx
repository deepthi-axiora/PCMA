import { useState, useEffect, useCallback } from 'react'
import { FolderPlus, Folder } from 'lucide-react'
import { getProjects, createProject } from '../api/memorySearch'

export function ProjectManager() {
  const [projects, setProjects] = useState([])
  const [loading, setLoading] = useState(true)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [saving, setSaving] = useState(false)

  const loadProjects = useCallback(async () => {
    setLoading(true)
    try {
      const data = await getProjects()
      setProjects(data)
    } catch (err) {
      console.error('Projects load failed:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadProjects()
  }, [loadProjects])

  const handleCreate = async (e) => {
    e.preventDefault()
    if (!name.trim()) return
    setSaving(true)
    try {
      await createProject({ name: name.trim(), description: description.trim() || undefined })
      setName('')
      setDescription('')
      await loadProjects()
    } catch (err) {
      alert(`Create project failed: ${err.message}`)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="entity-manager-pane">
      <h3>Project Management (FR-30)</h3>

      <form onSubmit={handleCreate} className="form-card">
        <h4><FolderPlus className="form-icon" /> Create Project</h4>
        <div className="form-row-grid">
          <input
            type="text"
            required
            className="text-input"
            placeholder="Project Name *"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <input
            type="text"
            className="text-input"
            placeholder="Description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </div>
        <button type="submit" className="btn btn-primary" disabled={saving}>
          {saving ? 'Saving...' : 'Create Project'}
        </button>
      </form>

      <div className="directory-list">
        <h4>Projects List ({projects.length})</h4>
        {loading ? (
          <div className="loading-spinner-box">Loading projects...</div>
        ) : projects.length === 0 ? (
          <div className="empty-state">No projects created yet.</div>
        ) : (
          <div className="projects-grid">
            {projects.map((proj) => (
              <div key={proj.id} className="project-card">
                <div className="project-name"><Folder className="project-icon" /> {proj.name}</div>
                {proj.description && <p className="project-desc">{proj.description}</p>}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
