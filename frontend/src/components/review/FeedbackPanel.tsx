import { useMemo } from 'react'

import type { QuizAnswerResponse } from '../../api/types'
import Badge from '../ui/Badge'
import Button from '../ui/Button'
import Card from '../ui/Card'

interface FeedbackPanelProps {
  result: QuizAnswerResponse
  hasMoreAfterCurrent: boolean
  onNextCard: () => void
  onFinishSession: () => void
  onBackToDashboard: () => void
}

type FeedbackTone = 'info' | 'success' | 'warning' | 'danger'

export default function FeedbackPanel({
  result,
  hasMoreAfterCurrent,
  onNextCard,
  onFinishSession,
  onBackToDashboard,
}: FeedbackPanelProps) {
  const normalizedVerdict = (result.verdict || 'n/a').toLowerCase()

  const verdictTone = useMemo<FeedbackTone>(() => {
    if (normalizedVerdict.includes('incorrect')) return 'danger'
    if (normalizedVerdict.includes('partial')) return 'warning'
    if (normalizedVerdict.includes('correct')) return 'success'
    return 'info'
  }, [normalizedVerdict])

  const scoreLabel = useMemo(() => {
    if (typeof result.model_score !== 'number') return 'No score available'
    return `${result.model_score}/5`
  }, [result.model_score])

  const scorePercent = useMemo(() => {
    if (typeof result.model_score !== 'number') return 0
    return Math.max(0, Math.min(100, Math.round((result.model_score / 5) * 100)))
  }, [result.model_score])

  const nextDueLabel = useMemo(() => {
    if (!result.next_due_at) return null
    const parsed = new Date(result.next_due_at)
    if (Number.isNaN(parsed.getTime())) return result.next_due_at
    return parsed.toLocaleString()
  }, [result.next_due_at])

  return (
    <Card
      className="review-feedback-panel"
      tone="default"
      padding="lg"
      kicker="Feedback"
      title="Assessment complete"
      subtitle="Review the explanation, then continue your session."
      actions={<Badge tone={verdictTone}>{result.verdict ?? 'n/a'}</Badge>}
    >
      <div className="review-feedback-panel__score">
        <div className="review-feedback-panel__score-meta">
          <span>Model score</span>
          <strong>{scoreLabel}</strong>
        </div>
        <div className="review-feedback-panel__score-track" role="presentation">
          <span
            className="review-feedback-panel__score-fill"
            style={{ width: `${scorePercent}%` }}
          />
        </div>
      </div>

      <section className="review-feedback-panel__section">
        <h4>Reference answer</h4>
        <p>{result.answer}</p>
      </section>

      {result.explanation ? (
        <section className="review-feedback-panel__section">
          <h4>Context snippet</h4>
          <p className="review-feedback-panel__snippet">{result.explanation}</p>
        </section>
      ) : null}

      {nextDueLabel ? (
        <p className="review-feedback-panel__next-due">
          Next review scheduled at {nextDueLabel}
        </p>
      ) : null}

      <div className="review-feedback-panel__actions">
        {hasMoreAfterCurrent ? (
          <Button type="button" onClick={onNextCard}>
            Continue to next card
          </Button>
        ) : (
          <Button type="button" onClick={onFinishSession}>
            Finish session
          </Button>
        )}
        <Button type="button" variant="ghost" onClick={onBackToDashboard}>
          Back to dashboard
        </Button>
      </div>
    </Card>
  )
}
