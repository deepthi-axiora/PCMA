import { apiFetch } from './client.js'

export async function getPeople() {
  return apiFetch('/v1/people')
}

export async function createPerson(data) {
  return apiFetch('/v1/people', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function mergePeople(sourcePersonId, targetPersonId) {
  return apiFetch('/v1/people/merge', {
    method: 'POST',
    body: JSON.stringify({
      source_person_id: sourcePersonId,
      target_person_id: targetPersonId,
    }),
  })
}

export async function getProjects() {
  return apiFetch('/v1/projects')
}

export async function createProject(data) {
  return apiFetch('/v1/projects', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function getTopics() {
  return apiFetch('/v1/topics')
}

export async function mergeTopics(sourceTopicId, targetTopicId) {
  return apiFetch('/v1/topics/merge', {
    method: 'POST',
    body: JSON.stringify({
      source_topic_id: sourceTopicId,
      target_topic_id: targetTopicId,
    }),
  })
}

export async function searchConversations(params = {}) {
  const queryParts = []
  if (params.query) queryParts.push(`query=${encodeURIComponent(params.query)}`)
  if (params.person_id) queryParts.push(`person_id=${params.person_id}`)
  if (params.project_id) queryParts.push(`project_id=${params.project_id}`)
  if (params.topic_id) queryParts.push(`topic_id=${params.topic_id}`)
  if (params.start_date) queryParts.push(`start_date=${encodeURIComponent(params.start_date)}`)
  if (params.end_date) queryParts.push(`end_date=${encodeURIComponent(params.end_date)}`)

  const queryString = queryParts.length > 0 ? `?${queryParts.join('&')}` : ''
  return apiFetch(`/v1/search${queryString}`)
}

export async function getPersonalMemories() {
  return apiFetch('/v1/memory')
}
