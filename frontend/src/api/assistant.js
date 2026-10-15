import { apiFetch } from './client.js'

export async function askAssistant(query) {
  return apiFetch('/v1/query', {
    method: 'POST',
    body: JSON.stringify({ query }),
  })
}
