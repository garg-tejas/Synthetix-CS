import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

import type { ApiError } from '../api/client'
import { answerQuizSession, finishQuizSession, startQuizSession } from '../api/quiz'
import type { QuizCard, QuizSessionAnswerResponse, SessionProgress } from '../api/types'
import PageHeader from '../components/layout/PageHeader'
import FeedbackPanel from '../components/review/FeedbackPanel'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import Card from '../components/ui/Card'
import ProgressBar from '../components/ui/ProgressBar'
import StateMessage from '../components/ui/StateMessage'
import Textarea from '../components/ui/Textarea'
import './review.css'

export default function ReviewPage() {
  const navigate = useNavigate()
  const location = useLocation()

  const [sessionId, setSessionId] = useState<string | null>(null)
  const [currentCard, setCurrentCard] = useState<QuizCard | null>(null)
  const [progress, setProgress] = useState<SessionProgress | null>(null)
  const [displayedIndex, setDisplayedIndex] = useState(0)

  const [userAnswer, setUserAnswer] = useState('')
  const [attemptStartedAt, setAttemptStartedAt] = useState<number | null>(null)

  const [result, setResult] = useState<QuizSessionAnswerResponse | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const sessionIdRef = useRef<string | null>(null)
  const sessionClosedRef = useRef(false)

  useEffect(() => {
    sessionIdRef.current = sessionId
  }, [sessionId])

  const finishAndNavigateBack = useCallback(() => {
    const activeSessionId = sessionIdRef.current
    if (!activeSessionId || sessionClosedRef.current) {
      navigate('/dashboard')
      return
    }
    sessionClosedRef.current = true
    void finishQuizSession(activeSessionId)
      .catch(() => undefined)
      .finally(() => {
        sessionIdRef.current = null
        setSessionId(null)
        navigate('/dashboard')
      })
  }, [navigate])

  useEffect(() => {
    let cancelled = false
    const run = async () => {
      setIsLoading(true)
      setError(null)
      setResult(null)
      setUserAnswer('')
      try {
        const state = location.state as
          | { topics?: string[] | null; subject?: string | null }
          | null
        const topics = state?.topics && state.topics.length ? state.topics : undefined
        const subject = state?.subject || undefined
        const data = await startQuizSession({ limit: 10, topics, subject })
        if (cancelled) return
        sessionClosedRef.current = false
        setSessionId(data.session_id)
        setProgress(data.progress)
        setDisplayedIndex(0)
        if (data.current_card) {
          setCurrentCard(data.current_card)
          setAttemptStartedAt(performance.now())
        } else {
          setCurrentCard(null)
          setAttemptStartedAt(null)
        }
      } catch (err) {
        if (cancelled) return
        const apiErr = err as ApiError
        setError(apiErr.detail || 'Failed to start review session')
      } finally {
        if (!cancelled) setIsLoading(false)
      }
    }
    void run()
    return () => {
      cancelled = true
    }
  }, [location.state])

  useEffect(() => {
    return () => {
      const activeSessionId = sessionIdRef.current
      if (!activeSessionId || sessionClosedRef.current) return
      sessionClosedRef.current = true
      void finishQuizSession(activeSessionId).catch(() => undefined)
    }
  }, [])

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!currentCard || !sessionId) return
    const trimmedAnswer = userAnswer.trim()
    if (!trimmedAnswer) {
      setError('Please enter an answer before submitting')
      return
    }
    setIsSubmitting(true)
    setError(null)
    try {
      const started = attemptStartedAt ?? performance.now()
      const responseTimeMs = Math.round(performance.now() - started)
      const res = await answerQuizSession(sessionId, {
        card_id: currentCard.card_id,
        user_answer: trimmedAnswer,
        response_time_ms: responseTimeMs,
      })
      setResult(res)
      setProgress(res.progress)
    } catch (err) {
      const apiErr = err as ApiError
      setError(apiErr.detail || 'Failed to submit answer')
    } finally {
      setIsSubmitting(false)
    }
  }

  const goToNextCard = () => {
    if (!result?.next_card) {
      setCurrentCard(null)
      return
    }
    setCurrentCard(result.next_card)
    setDisplayedIndex((previous) => previous + 1)
    setUserAnswer('')
    setResult(null)
    setAttemptStartedAt(performance.now())
  }

  const noCards = !isLoading && !error && !currentCard && !result

  const progressPercent = useMemo(() => {
    if (!progress || progress.total === 0) return 0
    if (progress.completed && !currentCard) return 100
    const stepsIntoRun = currentCard ? displayedIndex + 1 : displayedIndex
    return Math.round((stepsIntoRun / progress.total) * 100)
  }, [currentCard, displayedIndex, progress])

  const queueRemaining = useMemo(() => {
    if (!currentCard || !progress) return 0
    return Math.max(progress.total - displayedIndex - 1, 0)
  }, [currentCard, displayedIndex, progress])

  const hasMoreAfterCurrent = useMemo(() => Boolean(result?.next_card), [result])
  const totalCards = progress?.total ?? 0

  return (
    <div className="review layout-stack layout-stack--lg">
      <PageHeader
        eyebrow="Session"
        title="Review workspace"
        subtitle={
          currentCard
            ? `Card ${displayedIndex + 1} of ${totalCards}`
            : 'No active card'
        }
        backHref="/dashboard"
        backLabel="Back to dashboard"
      />

      <section className="review-progress">
        <Card
          className="review-progress__card"
          kicker="Session progress"
          title={
            currentCard ? `${progressPercent}% through this run` : 'Ready for the next run'
          }
          subtitle={
            currentCard
              ? `${queueRemaining} cards remaining after this step`
              : 'Select new scope from dashboard when ready.'
          }
          actions={
            currentCard ? (
              <Badge tone={result ? 'success' : 'info'}>
                {result ? 'Answered' : 'In progress'}
              </Badge>
            ) : (
              <Badge tone="neutral">Idle</Badge>
            )
          }
        >
          <ProgressBar
            value={progressPercent}
            className="review-progress__bar"
            ariaLabel="Session progress"
          />
        </Card>
      </section>

      {isLoading ? (
        <StateMessage title="Loading review cards" tone="info">
          Preparing your next question set.
        </StateMessage>
      ) : null}

      {error ? (
        <StateMessage title="Review session error" tone="danger">
          {error}
        </StateMessage>
      ) : null}

      {noCards ? (
        <Card className="review-empty" tone="inset" padding="lg">
          <StateMessage title="No cards due right now" tone="success">
            Nice work. You can return to the dashboard and start a new session later.
          </StateMessage>
          <div className="review-empty__actions">
            <Button type="button" onClick={finishAndNavigateBack}>
              Back to dashboard
            </Button>
          </div>
        </Card>
      ) : null}

      {!isLoading && !error && currentCard ? (
        <section className="review-workspace">
          <Card
            className="review-question"
            tone="default"
            padding="lg"
            kicker={`Topic: ${currentCard.topic}`}
            title="Question"
          >
            <p className="review-question__text">{currentCard.question}</p>
            <p className="review-question__hint">
              Explain your answer clearly. Use precise terms where possible.
            </p>
          </Card>

          <Card
            className="review-compose"
            tone="inset"
            padding="lg"
            kicker="Answer composer"
            title="Your response"
            subtitle={
              result
                ? 'Answer submitted. Review feedback and choose the next step below.'
                : 'Draft your response before submitting.'
            }
          >
            <form onSubmit={onSubmit} className="review-compose__form">
              <Textarea
                label="Your answer"
                value={userAnswer}
                onChange={(e) => setUserAnswer(e.target.value)}
                rows={9}
                required
                disabled={!!result}
              />

              <div className="review-compose__actions">
                <Button
                  type="submit"
                  disabled={isSubmitting || !!result || !sessionId}
                  loading={isSubmitting}
                  loadingLabel="Submitting..."
                >
                  Submit answer
                </Button>
              </div>

              {result ? (
                <p className="review-compose__submitted-note">
                  Submission locked. Use the feedback panel to continue.
                </p>
              ) : null}
            </form>
          </Card>
        </section>
      ) : null}

      {result ? (
        <FeedbackPanel
          result={result}
          hasMoreAfterCurrent={hasMoreAfterCurrent}
          onNextCard={goToNextCard}
          onFinishSession={finishAndNavigateBack}
          onBackToDashboard={finishAndNavigateBack}
        />
      ) : null}
    </div>
  )
}
