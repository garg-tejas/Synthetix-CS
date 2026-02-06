import { useEffect, useMemo, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'

import { getNextCards, submitAnswer } from '../api/quiz'
import type { ApiError } from '../api/client'
import type { QuizAnswerResponse, QuizCard } from '../api/types'

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
    [current]
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
        setCards(data.cards || [])
        if (data.cards && data.cards.length > 0) {
          setCurrent({
            card: data.cards[0],
            index: 0,
            total: data.cards.length,
          })
          setAttemptStartedAt(performance.now())
        }
      } catch (err) {
        if (cancelled) return
        const apiErr = err as ApiError
        setError(apiErr.detail || 'Failed to load review cards')
      } finally {
        if (!cancelled) setIsLoading(false)
      }
    }
    run()
    return () => {
      cancelled = true
    }
  }, [])

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

  return (
    <div style={{ padding: 24, maxWidth: 800, margin: '0 auto' }}>
      <header
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 12,
          marginBottom: 18,
        }}
      >
        <div>
          <h1 style={{ marginBottom: 6 }}>Review</h1>
          {current ? (
            <div style={{ opacity: 0.8 }}>
              Card {current.index + 1} of {current.total}
            </div>
          ) : (
            <div style={{ opacity: 0.8 }}>No active card</div>
          )}
        </div>
        <Link to="/" style={{ textDecoration: 'none', fontSize: 14 }}>
          ← Back to dashboard
        </Link>
      </header>

      {isLoading && <div>Loading cards…</div>}
      {error && <div style={{ color: '#b00020' }}>{error}</div>}

      {noCards && (
        <div style={{ marginTop: 16 }}>
          <p style={{ marginBottom: 8 }}>No cards are due right now.</p>
          <button type="button" onClick={() => navigate('/')} style={{ padding: 10 }}>
            Back to dashboard
          </button>
        </div>
      )}

      {!isLoading && !error && current && (
        <section style={{ marginTop: 16 }}>
          <article
            style={{
              border: '1px solid #e5e5e5',
              borderRadius: 12,
              padding: 16,
              marginBottom: 16,
              background: '#fff',
            }}
          >
            <div style={{ fontSize: 12, opacity: 0.7, marginBottom: 6 }}>
              Topic: {current.card.topic}
            </div>
            <h2 style={{ marginBottom: 10 }}>{current.card.question}</h2>
          </article>

          <form onSubmit={onSubmit} style={{ display: 'grid', gap: 12 }}>
            <label style={{ display: 'grid', gap: 6 }}>
              <span>Your answer</span>
              <textarea
                value={userAnswer}
                onChange={(e) => setUserAnswer(e.target.value)}
                rows={6}
                required
                style={{ padding: 10, resize: 'vertical' }}
              />
            </label>

            <div style={{ display: 'flex', gap: 10 }}>
              <button
                type="submit"
                disabled={isSubmitting || !!result}
                style={{ padding: '10px 12px', cursor: 'pointer' }}
              >
                {isSubmitting ? 'Submitting…' : 'Submit answer'}
              </button>
              {result && hasMoreAfterCurrent && (
                <button
                  type="button"
                  onClick={goToNextCard}
                  style={{ padding: '10px 12px', cursor: 'pointer' }}
                >
                  Next card
                </button>
              )}
              {result && !hasMoreAfterCurrent && (
                <button
                  type="button"
                  onClick={() => navigate('/')}
                  style={{ padding: '10px 12px', cursor: 'pointer' }}
                >
                  Finish session
                </button>
              )}
            </div>
          </form>

          {result && (
            <section
              style={{
                marginTop: 20,
                borderTop: '1px solid #eee',
                paddingTop: 16,
              }}
            >
              <h3 style={{ marginBottom: 8 }}>Feedback</h3>
              <div style={{ marginBottom: 8 }}>
                <strong>Model verdict:</strong>{' '}
                {result.verdict ?? 'n/a'}{' '}
                {typeof result.model_score === 'number'
                  ? `(score ${result.model_score}/5)`
                  : ''}
              </div>
              <div style={{ marginBottom: 8 }}>
                <strong>Reference answer:</strong>
                <div style={{ marginTop: 4 }}>{result.answer}</div>
              </div>
              {result.explanation && (
                <div style={{ marginTop: 8 }}>
                  <strong>Context snippet:</strong>
                  <div style={{ marginTop: 4, whiteSpace: 'pre-wrap' }}>
                    {result.explanation}
                  </div>
                </div>
              )}
              {result.next_due_at && (
                <div style={{ marginTop: 8, fontSize: 13, opacity: 0.8 }}>
                  Next review scheduled at {result.next_due_at}
                </div>
              )}
            </section>
          )}
        </section>
      )}
    </div>
  )
}

