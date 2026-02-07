import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { signup } from '../api/auth'
import type { ApiError } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import AuthLayout from '../components/auth/AuthLayout'
import Button from '../components/ui/Button'
import Input from '../components/ui/Input'
import StateMessage from '../components/ui/StateMessage'

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
    <AuthLayout
      mode="signup"
      title="Create account"
      subtitle="Start tracking spaced-repetition mastery across your core subjects."
      footer={
        <p>
          Already have an account? <Link to="/login">Log in</Link>
        </p>
      }
    >
      <form onSubmit={onSubmit} className="auth-form">
        <Input
          label="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          type="email"
          autoComplete="email"
          required
          density="lg"
        />

        <Input
          label="Username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          autoComplete="username"
          required
          density="lg"
        />

        <Input
          label="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          type="password"
          autoComplete="new-password"
          required
          density="lg"
        />

        {error ? (
          <StateMessage title="Signup failed" tone="danger" className="auth-form__error">
            {error}
          </StateMessage>
        ) : null}

        <Button
          type="submit"
          size="lg"
          fullWidth
          loading={isSubmitting}
          loadingLabel="Creating account..."
        >
          Create account
        </Button>
      </form>
    </AuthLayout>
  )
}
