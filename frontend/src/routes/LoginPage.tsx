import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'

import { login } from '../api/auth'
import type { ApiError } from '../api/client'
import { useAuth } from '../auth/AuthContext'

export default function LoginPage() {
  const auth = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const [emailOrUsername, setEmailOrUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const from = (location.state as any)?.from?.pathname || '/'

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setIsSubmitting(true)
    try {
      const tokens = await login({
        email_or_username: emailOrUsername.trim(),
        password,
      })
      auth.setTokenPair(tokens)
      await auth.refreshUser()
      navigate(from, { replace: true })
    } catch (err) {
      const apiErr = err as ApiError
      setError(apiErr.detail || 'Login failed')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div style={{ padding: 24, maxWidth: 420, margin: '0 auto' }}>
      <h1 style={{ marginBottom: 12 }}>Log in</h1>
      <p style={{ marginBottom: 16, opacity: 0.8 }}>
        Use your email or username.
      </p>

      <form onSubmit={onSubmit} style={{ display: 'grid', gap: 12 }}>
        <label style={{ display: 'grid', gap: 6 }}>
          <span>Email or username</span>
          <input
            value={emailOrUsername}
            onChange={(e) => setEmailOrUsername(e.target.value)}
            autoComplete="username"
            required
            style={{ padding: 10 }}
          />
        </label>

        <label style={{ display: 'grid', gap: 6 }}>
          <span>Password</span>
          <input
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            type="password"
            autoComplete="current-password"
            required
            style={{ padding: 10 }}
          />
        </label>

        {error && (
          <div style={{ color: '#b00020', fontSize: 14 }}>{error}</div>
        )}

        <button
          type="submit"
          disabled={isSubmitting}
          style={{ padding: 10, cursor: 'pointer' }}
        >
          {isSubmitting ? 'Logging in…' : 'Log in'}
        </button>
      </form>

      <p style={{ marginTop: 16 }}>
        No account? <Link to="/signup">Sign up</Link>
      </p>
    </div>
  )
}

