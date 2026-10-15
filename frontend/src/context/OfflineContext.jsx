import { createContext, useContext, useEffect, useState, useCallback } from 'react'
import { syncOfflineOperations, getSyncStatus } from '../api/sync'

const OfflineContext = createContext(null)

const LOCAL_STORAGE_KEY = 'pcma_offline_queue'

export function OfflineProvider({ children }) {
  const [isOnline, setIsOnline] = useState(navigator.onLine)
  const [pendingQueue, setPendingQueue] = useState([])
  const [isSyncing, setIsSyncing] = useState(false)
  const [lastSyncResult, setLastSyncResult] = useState(null)
  const [backendSyncStatus, setBackendSyncStatus] = useState(null)

  // Load saved queue from localStorage
  useEffect(() => {
    try {
      const saved = localStorage.getItem(LOCAL_STORAGE_KEY)
      if (saved) {
        setPendingQueue(JSON.parse(saved))
      }
    } catch (e) {
      console.warn('Failed to parse offline queue:', e)
    }
  }, [])

  // Listen to network status
  useEffect(() => {
    const handleOnline = () => setIsOnline(true)
    const handleOffline = () => setIsOnline(false)

    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)

    return () => {
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
    }
  }, [])

  // Save queue changes to localStorage
  const saveQueue = (queue) => {
    setPendingQueue(queue)
    try {
      localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(queue))
    } catch (e) {
      console.warn('Failed to save offline queue:', e)
    }
  }

  const enqueueOperation = (opType, payload) => {
    const newOp = {
      id: `op_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`,
      type: opType,
      payload,
      created_at: new Date().toISOString(),
    }
    const updated = [...pendingQueue, newOp]
    saveQueue(updated)
    return newOp
  }

  const triggerSync = useCallback(async () => {
    if (!isOnline || isSyncing) return null

    setIsSyncing(true)
    try {
      const syncId = `sync_${Date.now()}`
      const result = await syncOfflineOperations(syncId, pendingQueue)
      setLastSyncResult(result)
      saveQueue([]) // clear queue on successful sync

      try {
        const status = await getSyncStatus()
        setBackendSyncStatus(status)
      } catch (stErr) {
        console.warn('Sync status update error:', stErr)
      }

      return result
    } catch (err) {
      console.error('Offline sync failed:', err)
      throw err
    } finally {
      setIsSyncing(false)
    }
  }, [isOnline, isSyncing, pendingQueue])

  // Auto-sync when coming back online if queue has items
  useEffect(() => {
    if (isOnline && pendingQueue.length > 0 && !isSyncing) {
      triggerSync().catch((e) => console.warn('Auto-sync failed:', e))
    }
  }, [isOnline, pendingQueue.length, isSyncing, triggerSync])

  const value = {
    isOnline,
    pendingQueue,
    isSyncing,
    lastSyncResult,
    backendSyncStatus,
    enqueueOperation,
    triggerSync,
    clearQueue: () => saveQueue([]),
  }

  return <OfflineContext.Provider value={value}>{children}</OfflineContext.Provider>
}

export function useOffline() {
  const context = useContext(OfflineContext)
  if (!context) {
    throw new Error('useOffline must be used within an OfflineProvider')
  }
  return context
}
