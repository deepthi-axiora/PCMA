import { useState } from 'react'
import { AuthProvider, useAuth } from './context/AuthContext'
import { OfflineProvider } from './context/OfflineContext'
import { Header } from './components/Header'
import { BottomNav } from './components/BottomNav'

// View Panes
import { RecordView } from './views/RecordView'
import { ConversationsView } from './views/ConversationsView'
import { MomView } from './views/MomView'
import { EntitiesView } from './views/EntitiesView'
import { SettingsView } from './views/SettingsView'

// Component Panes
import { SearchFilter } from './components/SearchFilter'
import { CommitmentTracker } from './components/CommitmentTracker'
import { AssistantChat } from './components/AssistantChat'

function MainAppShell() {
  const { isAuthenticated, isLoading, login, authError } = useAuth()
  const [activeTab, setActiveTab] = useState('record')
  const [selectedConversationId, setSelectedConversationId] = useState(null)

  const handleSelectConversation = (id) => {
    setSelectedConversationId(id)
    setActiveTab('conversations')
  }

  if (isLoading) {
    return (
      <div className="app-container" style={{ justifyContent: 'center', alignItems: 'center' }}>
        <div className="loading-spinner-box">Initializing PCMA Mobile Application...</div>
      </div>
    )
  }

  if (!isAuthenticated) {
    return (
      <div className="app-container" style={{ justifyContent: 'center', alignItems: 'center', padding: '24px' }}>
        <div className="login-card" style={{ textStyle: 'center', width: '100%', textAlign: 'center' }}>
          <div className="brand-logo" style={{ margin: '0 auto 16px', width: '56px', height: '56px' }}>
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2">
              <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z"></path>
              <path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
              <line x1="12" y1="19" x2="12" y2="22"></line>
            </svg>
          </div>
          <h2>Personal Conversation Memory Assistant</h2>
          <p className="subtitle" style={{ margin: '8px 0 24px', color: '#94a3b8' }}>
            Secure voice memory, automated MOM, and intelligent retrieval
          </p>

          {authError && <div className="error-banner" style={{ marginBottom: '16px' }}>{authError}</div>}

          <button className="btn btn-primary" style={{ width: '100%', padding: '14px' }} onClick={login}>
            Log In / Authenticate Session
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="app-container">
      <Header />

      <main className="main-content">
        {activeTab === 'record' && <RecordView onOpenConversation={handleSelectConversation} />}
        {activeTab === 'conversations' && (
          <ConversationsView
            selectedId={selectedConversationId}
            onSelectConversation={setSelectedConversationId}
          />
        )}
        {activeTab === 'mom' && <MomView />}
        {activeTab === 'search' && <SearchFilter onSelectConversation={handleSelectConversation} />}
        {activeTab === 'entities' && <EntitiesView />}
        {activeTab === 'commitments' && <CommitmentTracker />}
        {activeTab === 'assistant' && <AssistantChat onSelectConversation={handleSelectConversation} />}
        {activeTab === 'settings' && <SettingsView />}
      </main>

      <BottomNav activeTab={activeTab} onTabChange={setActiveTab} />
    </div>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <OfflineProvider>
        <MainAppShell />
      </OfflineProvider>
    </AuthProvider>
  )
}