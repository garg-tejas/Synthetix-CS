import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'

import { login } from '../api/auth'
import type { ApiError } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import AuthLayout from '../components/auth/AuthLayout'
import Button from '../components/ui/Button'
import Input from '../components/ui/Input'
import StateMessage from '../components/ui/StateMessage'

export default function LoginPage() {
  const auth = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const [emailOrUsername, setEmailOrUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const from = (location.state as { from?: { pathname?: string } } | null)?.from?.pathname || '/'

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
    <AuthLayout
      mode="login"
      title="Log in"
      subtitle="Continue your daily review rhythm with your existing account."
      footer={
        <p>
          No account yet? <Link to="/signup">Create one now</Link>
        </p>
      }
    >
      <form onSubmit={onSubmit} className="auth-form">
        <Input
          label="Email or username"
          value={emailOrUsername}
          onChange={(e) => setEmailOrUsername(e.target.value)}
          autoComplete="username"
          required
          density="lg"
        />

        <Input
          label="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          type="password"
          autoComplete="current-password"
          required
          density="lg"
        />

        {error ? (
          <StateMessage title="Login failed" tone="danger" className="auth-form__error">
            {error}
          </StateMessage>
        ) : null}

        <Button
          type="submit"
          size="lg"
          fullWidth
          loading={isSubmitting}
          loadingLabel="Logging in..."
        >
          Log in
        </Button>
      </form>
    </AuthLayout>
  )
}
