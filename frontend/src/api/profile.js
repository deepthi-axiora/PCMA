import { apiFetch } from './client.js'

export async function getMe() {
  return apiFetch('/v1/me')
}

export async function getProfile() {
  return apiFetch('/v1/profile')
}

export async function updateProfile(data) {
  return apiFetch('/v1/profile', {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}
