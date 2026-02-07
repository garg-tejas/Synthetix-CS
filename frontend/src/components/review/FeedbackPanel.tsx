import { useMemo } from 'react'

import type { QuizSessionAnswerResponse } from '../../api/types'
import Badge from '../ui/Badge'
import Button from '../ui/Button'
import Card from '../ui/Card'
import ProgressBar from '../ui/ProgressBar'

interface FeedbackPanelProps {
  result: QuizSessionAnswerResponse
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
  const shouldRemediate = useMemo(() => {
    if (typeof result.should_remediate === 'boolean') {
      return result.should_remediate
    }
    return normalizedVerdict.includes('incorrect') || normalizedVerdict.includes('partial')
  }, [normalizedVerdict, result.should_remediate])

  const conceptSummary = useMemo(() => {
    const text = (result.concept_summary || '').trim()
    if (text) return text
    return 'Your answer missed key concepts needed for a complete explanation.'
  }, [result.concept_summary])

  const whereYouMissed = useMemo(() => {
    const points = result.where_you_missed || []
    return points
      .map((point) => point.trim())
      .filter(Boolean)
      .slice(0, 3)
  }, [result.where_you_missed])

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
      subtitle="Review the feedback, then continue your session."
      actions={<Badge tone={verdictTone}>{result.verdict ?? 'n/a'}</Badge>}
    >
      <div className="review-feedback-panel__score">
        <div className="review-feedback-panel__score-meta">
          <span>Model score</span>
          <strong>{scoreLabel}</strong>
        </div>
        <ProgressBar
          value={scorePercent}
          className="review-feedback-panel__score-bar"
          ariaLabel="Model score"
        />
      </div>

      <section className="review-feedback-panel__section">
        <h4>Reference answer</h4>
        <p>{result.answer}</p>
      </section>

      {shouldRemediate ? (
        <section className="review-feedback-panel__section">
          <h4>Concept in brief</h4>
          <p>{conceptSummary}</p>
        </section>
      ) : null}

      {shouldRemediate ? (
        <section className="review-feedback-panel__section">
          <h4>Where your answer missed</h4>
          {whereYouMissed.length > 0 ? (
            <ul className="review-feedback-panel__list">
              {whereYouMissed.map((point) => (
                <li key={point}>{point}</li>
              ))}
            </ul>
          ) : (
            <p>Your answer missed key concepts from the reference answer.</p>
          )}
        </section>
      ) : null}

      {result.show_source_context && result.explanation ? (
        <details className="review-feedback-panel__context">
          <summary>View source context</summary>
          <p className="review-feedback-panel__snippet">{result.explanation}</p>
        </details>
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
