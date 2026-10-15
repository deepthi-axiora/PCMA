import { apiFetch } from './client.js'

export async function syncOfflineOperations(clientSyncId, operations) {
  return apiFetch('/v1/sync', {
    method: 'POST',
    body: JSON.stringify({
      client_sync_id: clientSyncId,
      operations: operations || [],
    }),
  })
}

export async function getSyncStatus() {
  return apiFetch('/v1/sync/status')
}
