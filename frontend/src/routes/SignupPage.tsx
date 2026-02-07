import { useMemo, useRef, useState } from 'react'
import type { ChangeEvent, FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { signup } from '../api/auth'
import type { ApiError } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import AuthLayout from '../components/auth/AuthLayout'
import Button from '../components/ui/Button'
import Input from '../components/ui/Input'
import StateMessage from '../components/ui/StateMessage'

interface SignupTouchedState {
  email: boolean
  username: boolean
  password: boolean
  confirmPassword: boolean
}

export default function SignupPage() {
  const auth = useAuth()
  const navigate = useNavigate()

  const emailRef = useRef<HTMLInputElement | null>(null)
  const usernameRef = useRef<HTMLInputElement | null>(null)
  const passwordRef = useRef<HTMLInputElement | null>(null)
  const confirmPasswordRef = useRef<HTMLInputElement | null>(null)

  const [email, setEmail] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submittedOnce, setSubmittedOnce] = useState(false)
  const [touched, setTouched] = useState<SignupTouchedState>({
    email: false,
    username: false,
    password: false,
    confirmPassword: false,
  })

  const normalizedEmail = email.trim()
  const normalizedUsername = username.trim()

  const fieldErrors = useMemo(() => {
    let emailError: string | undefined
    let usernameError: string | undefined
    let passwordError: string | undefined
    let confirmPasswordError: string | undefined

    if (!normalizedEmail) {
      emailError = 'Enter your email address.'
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(normalizedEmail)) {
      emailError = 'Enter a valid email format.'
    }

    if (!normalizedUsername) {
      usernameError = 'Enter a username.'
    }

    if (!password) {
      passwordError = 'Create a password.'
    }

    if (!confirmPassword) {
      confirmPasswordError = 'Re-enter your password.'
    } else if (password !== confirmPassword) {
      confirmPasswordError = 'Passwords do not match.'
    }

    return {
      email: emailError,
      username: usernameError,
      password: passwordError,
      confirmPassword: confirmPasswordError,
    }
  }, [confirmPassword, normalizedEmail, normalizedUsername, password])

  const showEmailError = (submittedOnce || touched.email) && !!fieldErrors.email
  const showUsernameError = (submittedOnce || touched.username) && !!fieldErrors.username
  const showPasswordError = (submittedOnce || touched.password) && !!fieldErrors.password
  const showConfirmPasswordError =
    (submittedOnce || touched.confirmPassword) && !!fieldErrors.confirmPassword

  const onChangeWithErrorReset = (
    setter: (value: string) => void,
  ) => (e: ChangeEvent<HTMLInputElement>) => {
    setter(e.target.value)
    if (error) setError(null)
  }

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    setSubmittedOnce(true)
    setTouched({
      email: true,
      username: true,
      password: true,
      confirmPassword: true,
    })

    if (fieldErrors.email) {
      emailRef.current?.focus()
      return
    }

    if (fieldErrors.username) {
      usernameRef.current?.focus()
      return
    }

    if (fieldErrors.password) {
      passwordRef.current?.focus()
      return
    }

    if (fieldErrors.confirmPassword) {
      confirmPasswordRef.current?.focus()
      return
    }

    setIsSubmitting(true)
    try {
      const tokens = await signup({
        email: normalizedEmail,
        username: normalizedUsername,
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
      <form onSubmit={onSubmit} noValidate className="auth-form">
        <Input
          ref={emailRef}
          label="Email"
          value={email}
          onChange={onChangeWithErrorReset(setEmail)}
          onBlur={() => setTouched((prev) => ({ ...prev, email: true }))}
          type="email"
          autoComplete="email"
          autoFocus
          required
          density="lg"
          disabled={isSubmitting}
          hint="Used for account recovery and important notices."
          error={showEmailError ? fieldErrors.email : undefined}
        />

        <Input
          ref={usernameRef}
          label="Username"
          value={username}
          onChange={onChangeWithErrorReset(setUsername)}
          onBlur={() => setTouched((prev) => ({ ...prev, username: true }))}
          autoComplete="username"
          required
          density="lg"
          disabled={isSubmitting}
          hint="This name appears in your dashboard."
          error={showUsernameError ? fieldErrors.username : undefined}
        />

        <Input
          ref={passwordRef}
          label="Password"
          value={password}
          onChange={onChangeWithErrorReset(setPassword)}
          onBlur={() => setTouched((prev) => ({ ...prev, password: true }))}
          type="password"
          autoComplete="new-password"
          required
          density="lg"
          disabled={isSubmitting}
          hint="Use a unique password for this account."
          error={showPasswordError ? fieldErrors.password : undefined}
        />

        <Input
          ref={confirmPasswordRef}
          label="Confirm password"
          value={confirmPassword}
          onChange={onChangeWithErrorReset(setConfirmPassword)}
          onBlur={() => setTouched((prev) => ({ ...prev, confirmPassword: true }))}
          type="password"
          autoComplete="new-password"
          required
          density="lg"
          disabled={isSubmitting}
          hint="Re-enter to avoid typos."
          error={showConfirmPasswordError ? fieldErrors.confirmPassword : undefined}
        />

        {error ? (
          <StateMessage
            role="alert"
            title="Signup failed"
            tone="danger"
            className="auth-form__error"
          >
            {error}
          </StateMessage>
        ) : null}

        {isSubmitting ? (
          <p className="auth-form__status" role="status" aria-live="polite">
            Creating your account...
          </p>
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

        <p className="auth-form__meta">
          Continue only if the information above is accurate. You can update profile details later.
        </p>
      </form>
    </AuthLayout>
  )
}
