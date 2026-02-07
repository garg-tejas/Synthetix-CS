import { useEffect, useMemo, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

import type { ApiError } from '../api/client'
import { getNextCards, submitAnswer } from '../api/quiz'
import type { QuizAnswerResponse, QuizCard } from '../api/types'
import PageHeader from '../components/layout/PageHeader'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import Card from '../components/ui/Card'
import StateMessage from '../components/ui/StateMessage'
import Textarea from '../components/ui/Textarea'
import './review.css'

interface CurrentCardState {
  card: QuizCard
  index: number
  total: number
}

export default function ReviewPage() {
  const navigate = useNavigate()
  const location = useLocation()

  const [cards, setCards] = useState<QuizCard[]>([])
  const [currentIndex, setCurrentIndex] = useState(0)
  const [current, setCurrent] = useState<CurrentCardState | null>(null)

  const [userAnswer, setUserAnswer] = useState('')
  const [attemptStartedAt, setAttemptStartedAt] = useState<number | null>(null)

  const [result, setResult] = useState<QuizAnswerResponse | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const hasMoreAfterCurrent = useMemo(
    () => current !== null && current.index < current.total - 1,
    [current],
  )

  useEffect(() => {
    let cancelled = false
    const run = async () => {
      setIsLoading(true)
      setError(null)
      try {
        const state = location.state as { topics?: string[] | null } | null
        const topics = state?.topics && state.topics.length ? state.topics : undefined
        const data = await getNextCards({ limit: 10, topics })
        if (cancelled) return
        const loadedCards = data.cards || []
        setCards(loadedCards)
        if (loadedCards.length > 0) {
          setCurrent({
            card: loadedCards[0],
            index: 0,
            total: loadedCards.length,
          })
          setAttemptStartedAt(performance.now())
        } else {
          setCurrent(null)
        }
      } catch (err) {
        if (cancelled) return
        const apiErr = err as ApiError
        setError(apiErr.detail || 'Failed to load review cards')
      } finally {
        if (!cancelled) setIsLoading(false)
      }
    }
    void run()
    return () => {
      cancelled = true
    }
  }, [location.state])

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!current) return
    setIsSubmitting(true)
    setError(null)
    try {
      const started = attemptStartedAt ?? performance.now()
      const responseTimeMs = Math.round(performance.now() - started)
      const res = await submitAnswer({
        card_id: current.card.card_id,
        user_answer: userAnswer.trim(),
        response_time_ms: responseTimeMs,
      })
      setResult(res)
    } catch (err) {
      const apiErr = err as ApiError
      setError(apiErr.detail || 'Failed to submit answer')
    } finally {
      setIsSubmitting(false)
    }
  }

  const goToNextCard = () => {
    if (!cards || cards.length === 0) return
    const nextIndex = currentIndex + 1
    if (nextIndex >= cards.length) {
      setCurrent(null)
      return
    }
    setCurrent({
      card: cards[nextIndex],
      index: nextIndex,
      total: cards.length,
    })
    setCurrentIndex(nextIndex)
    setUserAnswer('')
    setResult(null)
    setAttemptStartedAt(performance.now())
  }

  const noCards = !isLoading && !error && (!cards || cards.length === 0)

  const progressPercent = useMemo(() => {
    if (!current) return cards.length > 0 ? 100 : 0
    return Math.round(((current.index + 1) / current.total) * 100)
  }, [cards.length, current])

  const queueRemaining = useMemo(() => {
    if (!current) return 0
    return current.total - current.index - (result ? 1 : 0)
  }, [current, result])

  return (
    <div className="review layout-stack layout-stack--lg">
      <PageHeader
        eyebrow="Session"
        title="Review workspace"
        subtitle={
          current
            ? `Card ${current.index + 1} of ${current.total}`
            : 'No active card'
        }
        backHref="/"
        backLabel="Back to dashboard"
      />

      <section className="review-progress">
        <Card
          className="review-progress__card"
          kicker="Session progress"
          title={
            current ? `${progressPercent}% through this run` : 'Ready for the next run'
          }
          subtitle={
            current
              ? `${queueRemaining} cards remaining after this step`
              : 'Select new scope from dashboard when ready.'
          }
          actions={
            current ? (
              <Badge tone={result ? 'success' : 'info'}>
                {result ? 'Answered' : 'In progress'}
              </Badge>
            ) : (
              <Badge tone="neutral">Idle</Badge>
            )
          }
        >
          <div className="review-progress__track" role="presentation">
            <span
              className="review-progress__fill"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
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
            <Button type="button" onClick={() => navigate('/')}>
              Back to dashboard
            </Button>
          </div>
        </Card>
      ) : null}

      {!isLoading && !error && current ? (
        <section className="review-workspace">
          <Card
            className="review-question"
            tone="default"
            padding="lg"
            kicker={`Topic: ${current.card.topic}`}
            title="Question"
          >
            <p className="review-question__text">{current.card.question}</p>
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
                ? 'Answer submitted. Review feedback below or move to next card.'
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
              />

              <div className="review-compose__actions">
                <Button
                  type="submit"
                  disabled={isSubmitting || !!result}
                  loading={isSubmitting}
                  loadingLabel="Submitting..."
                >
                  Submit answer
                </Button>

                {result && hasMoreAfterCurrent ? (
                  <Button type="button" variant="secondary" onClick={goToNextCard}>
                    Next card
                  </Button>
                ) : null}

                {result && !hasMoreAfterCurrent ? (
                  <Button type="button" variant="secondary" onClick={() => navigate('/')}>
                    Finish session
                  </Button>
                ) : null}
              </div>
            </form>
          </Card>
        </section>
      ) : null}

      {result ? (
        <section className="review-feedback">
          <h3>Feedback</h3>
          <div>
            <strong>Model verdict:</strong> {result.verdict ?? 'n/a'}{' '}
            {typeof result.model_score === 'number'
              ? `(score ${result.model_score}/5)`
              : ''}
          </div>
          <div>
            <strong>Reference answer:</strong>
            <p>{result.answer}</p>
          </div>
          {result.explanation ? (
            <div>
              <strong>Context snippet:</strong>
              <p className="review-feedback__snippet">{result.explanation}</p>
            </div>
          ) : null}
          {result.next_due_at ? (
            <p className="review-feedback__next-due">
              Next review scheduled at {result.next_due_at}
            </p>
          ) : null}
        </section>
      ) : null}
    </div>
  )
}
