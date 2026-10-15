import { apiFetch } from './client.js'

export async function deleteUserData() {
  return apiFetch('/v1/me/data', {
    method: 'DELETE',
  })
}

export async function exportUserData() {
  return apiFetch('/v1/me/export', {
    method: 'POST',
  })
}

export async function deleteUserAccount() {
  return apiFetch('/v1/me/account', {
    method: 'DELETE',
  })
}
