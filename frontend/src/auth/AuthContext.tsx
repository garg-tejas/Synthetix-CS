import React, { createContext, useContext, useEffect, useMemo, useState } from 'react'

import { getMe } from '../api/auth'
import { setAuthFailureHandler, tokenManager } from '../api/client'
import type { TokenResponse, UserOut } from '../api/types'

type AuthStatus = 'unknown' | 'authenticated' | 'unauthenticated'

export interface AuthContextValue {
  status: AuthStatus
  user: UserOut | null
  accessToken: string | null
  refreshToken: string | null
  setTokenPair: (tokens: TokenResponse) => void
  clearSession: () => void
  refreshUser: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

const ACCESS_KEY = 'csrag.access_token'
const REFRESH_KEY = 'csrag.refresh_token'

function readStoredToken(key: string): string | null {
  try {
    return sessionStorage.getItem(key)
  } catch {
    return null
  }
}

function writeStoredToken(key: string, value: string | null) {
  try {
    if (value === null) sessionStorage.removeItem(key)
    else sessionStorage.setItem(key, value)
  } catch {
    // ignore
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [accessToken, setAccessToken] = useState<string | null>(() =>
    readStoredToken(ACCESS_KEY)
  )
  const [refreshToken, setRefreshToken] = useState<string | null>(() =>
    readStoredToken(REFRESH_KEY)
  )
  const [user, setUser] = useState<UserOut | null>(null)
  const [status, setStatus] = useState<AuthStatus>('unknown')

  const clearSession = () => {
    setAccessToken(null)
    setRefreshToken(null)
    setUser(null)
    setStatus('unauthenticated')
    tokenManager.clear()
    writeStoredToken(ACCESS_KEY, null)
    writeStoredToken(REFRESH_KEY, null)
  }

  const setTokenPair = (tokens: TokenResponse) => {
    setAccessToken(tokens.access_token)
    setRefreshToken(tokens.refresh_token)
    tokenManager.setTokens(tokens.access_token, tokens.refresh_token)
    writeStoredToken(ACCESS_KEY, tokens.access_token)
    writeStoredToken(REFRESH_KEY, tokens.refresh_token)
  }

  const refreshUser = async () => {
    if (!tokenManager.getAccessToken()) {
      setStatus('unauthenticated')
      setUser(null)
      return
    }
    const me = await getMe()
    setUser(me)
    setStatus('authenticated')
  }

  // On mount: ensure tokenManager has whatever we stored.
  useEffect(() => {
    if (accessToken && refreshToken) {
      tokenManager.setTokens(accessToken, refreshToken)
      setStatus('authenticated')
    } else {
      tokenManager.clear()
      setStatus('unauthenticated')
    }
  }, [accessToken, refreshToken])

  // On auth failure from API client: clear tokens.
  useEffect(() => {
    setAuthFailureHandler(() => {
      clearSession()
    })
  }, [])

  // Best-effort: fetch /me once we have an access token.
  useEffect(() => {
    let cancelled = false
    const run = async () => {
      if (!accessToken) return
      try {
        const me = await getMe()
        if (cancelled) return
        setUser(me)
        setStatus('authenticated')
      } catch {
        if (cancelled) return
        // If /me fails, we’ll treat it as unauthenticated; the API client may refresh later.
        setUser(null)
        setStatus('unauthenticated')
      }
    }
    run()
    return () => {
      cancelled = true
    }
  }, [accessToken])

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      user,
      accessToken,
      refreshToken,
      setTokenPair,
      clearSession,
      refreshUser,
    }),
    [status, user, accessToken, refreshToken]
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return ctx
}
