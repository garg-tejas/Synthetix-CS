/**
 * API client with Bearer token authentication and automatic refresh on 401.
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export interface ApiError {
  detail: string
  status_code?: number
}

/**
 * Token storage interface - can be swapped for sessionStorage or other storage.
 */
class TokenStorage {
  private accessToken: string | null = null
  private refreshToken: string | null = null

  setTokens(accessToken: string, refreshToken: string) {
    this.accessToken = accessToken
    this.refreshToken = refreshToken
  }

  getAccessToken(): string | null {
    return this.accessToken
  }

  getRefreshToken(): string | null {
    return this.refreshToken
  }

  clear() {
    this.accessToken = null
    this.refreshToken = null
  }
}

const tokenStorage = new TokenStorage()

/**
 * Callback to trigger redirect to login when auth fails.
 */
let onAuthFailure: (() => void) | null = null

export function setAuthFailureHandler(handler: () => void) {
  onAuthFailure = handler
}

/**
 * Attempts to refresh the access token using the refresh token.
 * Returns the new access token on success, null on failure.
 */
async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = tokenStorage.getRefreshToken()
  if (!refreshToken) {
    return null
  }

  try {
    const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ refresh_token: refreshToken }),
    })

    if (!response.ok) {
      return null
    }

    const data = await response.json()
    if (data.access_token && data.refresh_token) {
      tokenStorage.setTokens(data.access_token, data.refresh_token)
      return data.access_token
    }

    return null
  } catch {
    return null
  }
}

/**
 * Makes an authenticated API request with automatic token refresh on 401.
 */
export async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const accessToken = tokenStorage.getAccessToken()

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  }

  if (accessToken) {
    headers['Authorization'] = `Bearer ${accessToken}`
  }

  let response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers,
  })

  // If 401 and we have a refresh token, try to refresh and retry once
  if (response.status === 401 && tokenStorage.getRefreshToken()) {
    const newAccessToken = await refreshAccessToken()
    if (newAccessToken) {
      // Retry the original request with the new token
      const retryHeaders: Record<string, string> = {
        'Content-Type': 'application/json',
        ...(options.headers as Record<string, string>),
        'Authorization': `Bearer ${newAccessToken}`,
      }
      response = await fetch(`${API_BASE_URL}${endpoint}`, {
        ...options,
        headers: retryHeaders,
      })
    } else {
      // Refresh failed, clear tokens and trigger auth failure handler
      tokenStorage.clear()
      if (onAuthFailure) {
        onAuthFailure()
      }
      throw new Error('Authentication failed')
    }
  }

  if (!response.ok) {
    let errorDetail: string
    try {
      const errorData = await response.json()
      errorDetail = errorData.detail || `HTTP ${response.status}`
    } catch {
      errorDetail = `HTTP ${response.status}: ${response.statusText}`
    }
    const error: ApiError = {
      detail: errorDetail,
      status_code: response.status,
    }
    throw error
  }

  // Handle empty responses
  const contentType = response.headers.get('content-type')
  if (contentType && contentType.includes('application/json')) {
    return response.json()
  }

  return {} as T
}

/**
 * Exports for token management (used by auth context).
 */
export const tokenManager = {
  setTokens: (accessToken: string, refreshToken: string) => {
    tokenStorage.setTokens(accessToken, refreshToken)
  },
  getAccessToken: () => tokenStorage.getAccessToken(),
  getRefreshToken: () => tokenStorage.getRefreshToken(),
  clear: () => tokenStorage.clear(),
}
