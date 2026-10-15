import { apiFetch } from './client.js'

export async function getConversations() {
  return apiFetch('/v1/conversations')
}

export async function getConversationDetail(conversationId) {
  return apiFetch(`/v1/conversations/${conversationId}`)
}

export async function updateConversationTopics(conversationId, topicIds) {
  return apiFetch(`/v1/conversations/${conversationId}/topics`, {
    method: 'PATCH',
    body: JSON.stringify({ topic_ids: topicIds }),
  })
}

export async function processExtraction(conversationId) {
  return apiFetch(`/v1/conversations/${conversationId}/process-extraction`, {
    method: 'POST',
  })
}
