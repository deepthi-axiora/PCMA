import { useState } from 'react'
import { Users, Folder, Tag } from 'lucide-react'
import { PeopleManager } from '../components/PeopleManager'
import { ProjectManager } from '../components/ProjectManager'
import { TopicManager } from '../components/TopicManager'

export function EntitiesView() {
  const [subTab, setSubTab] = useState('people') // people, projects, topics

  return (
    <div className="view-pane entities-view">
      <div className="view-header">
        <h2>Entity Management Hub</h2>
        <p className="subtitle">Manage people directory, speaker mappings, projects, and conversation topics</p>
      </div>

      <div className="entities-subtabs">
        <button
          className={`subtab-btn ${subTab === 'people' ? 'active' : ''}`}
          onClick={() => setSubTab('people')}
        >
          <Users className="tab-icon" /> People Directory (FR-29)
        </button>
        <button
          className={`subtab-btn ${subTab === 'projects' ? 'active' : ''}`}
          onClick={() => setSubTab('projects')}
        >
          <Folder className="tab-icon" /> Projects (FR-30)
        </button>
        <button
          className={`subtab-btn ${subTab === 'topics' ? 'active' : ''}`}
          onClick={() => setSubTab('topics')}
        >
          <Tag className="tab-icon" /> Topics (FR-31)
        </button>
      </div>

      <div className="entities-pane-content">
        {subTab === 'people' && <PeopleManager />}
        {subTab === 'projects' && <ProjectManager />}
        {subTab === 'topics' && <TopicManager />}
      </div>
    </div>
  )
}
