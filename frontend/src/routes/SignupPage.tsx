import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { signup } from '../api/auth'
import type { ApiError } from '../api/client'
import { useAuth } from '../auth/AuthContext'

export default function SignupPage() {
  const auth = useAuth()
  const navigate = useNavigate()

  const [email, setEmail] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setIsSubmitting(true)
    try {
      const tokens = await signup({
        email: email.trim(),
        username: username.trim(),
        password,
      })
      auth.setTokenPair(tokens)
      await auth.refreshUser()
      navigate('/', { replace: true })
    } catch (err) {
      const apiErr = err as ApiError
      setError(apiErr.detail || 'Signup failed')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div style={{ padding: 24, maxWidth: 420, margin: '0 auto' }}>
      <h1 style={{ marginBottom: 12 }}>Sign up</h1>
      <p style={{ marginBottom: 16, opacity: 0.8 }}>
        Create an account to start tracking reviews.
      </p>

      <form onSubmit={onSubmit} style={{ display: 'grid', gap: 12 }}>
        <label style={{ display: 'grid', gap: 6 }}>
          <span>Email</span>
          <input
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            type="email"
            autoComplete="email"
            required
            style={{ padding: 10 }}
          />
        </label>

        <label style={{ display: 'grid', gap: 6 }}>
          <span>Username</span>
          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
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
            autoComplete="new-password"
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
          {isSubmitting ? 'Creating…' : 'Create account'}
        </button>
      </form>

      <p style={{ marginTop: 16 }}>
        Already have an account? <Link to="/login">Log in</Link>
      </p>
    </div>
  )
}

