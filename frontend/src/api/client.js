const API_BASE_URL =
  (typeof import.meta !== 'undefined' && import.meta.env?.VITE_API_BASE_URL) ||
  (typeof process !== 'undefined' && process.env?.VITE_API_BASE_URL) ||
  'http://127.0.0.1:8000'

let getAuthToken = null

export function setAuthTokenGetter(getter) {
  getAuthToken = getter
}

export async function apiFetch(endpoint, options = {}) {
  const url = `${API_BASE_URL}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`
  
  const headers = new Headers(options.headers || {})
  
  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }

  if (getAuthToken) {
    try {
      const token = await getAuthToken()
      if (token) {
        headers.set('Authorization', `Bearer ${token}`)
      }
    } catch (err) {
      console.warn('Could not get auth token for request:', err)
    }
  }

  const response = await fetch(url, {
    ...options,
    headers,
  })

  if (response.status === 204) {
    return null
  }

  let data
  const contentType = response.headers.get('content-type')
  if (contentType && contentType.includes('application/json')) {
    data = await response.json()
  } else if (contentType && (contentType.includes('text/') || contentType.includes('application/octet-stream') || contentType.includes('application/pdf'))) {
    data = await response.blob()
  } else {
    data = await response.text()
  }

  if (!response.ok) {
    let message = 'An API error occurred'
    let code = 'API_ERROR'

    if (data && typeof data === 'object') {
      if (data.detail) {
        if (typeof data.detail === 'object') {
          message = data.detail.message || JSON.stringify(data.detail)
          code = data.detail.code || code
        } else {
          message = data.detail
        }
      } else if (data.message) {
        message = data.message
        code = data.code || code
      }
    }

    const error = new Error(message)
    error.status = response.status
    error.code = code
    error.data = data
    throw error
  }

  return data
}

export { API_BASE_URL }
