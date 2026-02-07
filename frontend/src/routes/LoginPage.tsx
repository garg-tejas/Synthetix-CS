import { useMemo, useRef, useState } from 'react'
import type { ChangeEvent, FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'

import { login } from '../api/auth'
import type { ApiError } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import AuthLayout from '../components/auth/AuthLayout'
import Button from '../components/ui/Button'
import Input from '../components/ui/Input'
import StateMessage from '../components/ui/StateMessage'

interface LoginTouchedState {
  emailOrUsername: boolean
  password: boolean
}

export default function LoginPage() {
  const auth = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const identityRef = useRef<HTMLInputElement | null>(null)
  const passwordRef = useRef<HTMLInputElement | null>(null)

  const [emailOrUsername, setEmailOrUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submittedOnce, setSubmittedOnce] = useState(false)
  const [touched, setTouched] = useState<LoginTouchedState>({
    emailOrUsername: false,
    password: false,
  })

  const from = (location.state as { from?: { pathname?: string } } | null)?.from?.pathname || '/'
  const normalizedIdentity = emailOrUsername.trim()

  const fieldErrors = useMemo(() => {
    let identityError: string | undefined
    let passwordError: string | undefined

    if (!normalizedIdentity) {
      identityError = 'Enter your email or username.'
    } else if (/\s/.test(normalizedIdentity)) {
      identityError = 'Remove spaces from email or username.'
    }

    if (!password) {
      passwordError = 'Enter your password.'
    }

    return {
      emailOrUsername: identityError,
      password: passwordError,
    }
  }, [normalizedIdentity, password])

  const showIdentityError = (submittedOnce || touched.emailOrUsername) && !!fieldErrors.emailOrUsername
  const showPasswordError = (submittedOnce || touched.password) && !!fieldErrors.password

  const onIdentityChange = (e: ChangeEvent<HTMLInputElement>) => {
    setEmailOrUsername(e.target.value)
    if (error) setError(null)
  }

  const onPasswordChange = (e: ChangeEvent<HTMLInputElement>) => {
    setPassword(e.target.value)
    if (error) setError(null)
  }

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    setSubmittedOnce(true)
    setTouched({ emailOrUsername: true, password: true })

    if (fieldErrors.emailOrUsername) {
      identityRef.current?.focus()
      return
    }

    if (fieldErrors.password) {
      passwordRef.current?.focus()
      return
    }

    setIsSubmitting(true)
    try {
      const tokens = await login({
        email_or_username: normalizedIdentity,
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
      <form onSubmit={onSubmit} noValidate className="auth-form">
        <Input
          ref={identityRef}
          label="Email or username"
          value={emailOrUsername}
          onChange={onIdentityChange}
          onBlur={() => setTouched((prev) => ({ ...prev, emailOrUsername: true }))}
          autoComplete="username"
          autoFocus
          required
          density="lg"
          disabled={isSubmitting}
          hint="Use the same identifier you registered with."
          error={showIdentityError ? fieldErrors.emailOrUsername : undefined}
        />

        <Input
          ref={passwordRef}
          label="Password"
          value={password}
          onChange={onPasswordChange}
          onBlur={() => setTouched((prev) => ({ ...prev, password: true }))}
          type="password"
          autoComplete="current-password"
          required
          density="lg"
          disabled={isSubmitting}
          hint="Passwords are case sensitive."
          error={showPasswordError ? fieldErrors.password : undefined}
        />

        {error ? (
          <StateMessage
            role="alert"
            title="Login failed"
            tone="danger"
            className="auth-form__error"
          >
            {error}
          </StateMessage>
        ) : null}

        {isSubmitting ? (
          <p className="auth-form__status" role="status" aria-live="polite">
            Verifying credentials...
          </p>
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

        <p className="auth-form__meta">
          Tip: if login fails repeatedly, verify Caps Lock and spacing.
        </p>
      </form>
    </AuthLayout>
  )
}
