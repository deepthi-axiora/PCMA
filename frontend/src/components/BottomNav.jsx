import { Mic, MessageSquare, FileText, Search, Users, CheckSquare, Bot, Settings } from 'lucide-react'

export function BottomNav({ activeTab, onTabChange }) {
  const navItems = [
    { id: 'record', label: 'Record', icon: Mic },
    { id: 'conversations', label: 'Conversations', icon: MessageSquare },
    { id: 'mom', label: 'MOM', icon: FileText },
    { id: 'search', label: 'Search', icon: Search },
    { id: 'entities', label: 'Entities', icon: Users },
    { id: 'commitments', label: 'Tasks', icon: CheckSquare },
    { id: 'assistant', label: 'Assistant', icon: Bot },
    { id: 'settings', label: 'Settings', icon: Settings },
  ]

  return (
    <nav className="bottom-nav">
      {navItems.map((item) => {
        const Icon = item.icon
        const isActive = activeTab === item.id
        return (
          <button
            key={item.id}
            className={`nav-tab ${isActive ? 'active' : ''}`}
            onClick={() => onTabChange(item.id)}
          >
            <Icon className="nav-icon" />
            <span className="nav-label">{item.label}</span>
          </button>
        )
      })}
    </nav>
  )
}
