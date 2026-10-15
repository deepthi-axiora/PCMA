import { apiFetch } from './client.js'

export async function generateMom(conversationId) {
  return apiFetch(`/v1/conversations/${conversationId}/mom/generate`, {
    method: 'POST',
  })
}

export async function getMom(conversationId) {
  return apiFetch(`/v1/conversations/${conversationId}/mom`)
}

export async function updateMom(momId, data) {
  return apiFetch(`/v1/moms/${momId}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

export async function approveMom(momId) {
  return apiFetch(`/v1/moms/${momId}/approve`, {
    method: 'POST',
  })
}

export async function getMomHistory(momId) {
  return apiFetch(`/v1/moms/${momId}/history`)
}

export async function shareMom(momId, recipientEmail) {
  return apiFetch(`/v1/moms/${momId}/share`, {
    method: 'POST',
    body: JSON.stringify({ recipient_email: recipientEmail }),
  })
}

export async function getMomShares(momId) {
  return apiFetch(`/v1/moms/${momId}/shares`)
}

export async function revokeMomShare(momId, shareId) {
  return apiFetch(`/v1/moms/${momId}/shares/${shareId}`, {
    method: 'DELETE',
  })
}

export async function exportMom(momId, format = 'markdown') {
  return apiFetch(`/v1/moms/${momId}/export?format=${format}`)
}
