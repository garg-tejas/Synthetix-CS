import { useMemo } from 'react'

import { Badge, Button } from '../ui'

interface TopicScopeControlsProps {
  availableTopics: string[]
  selectedTopics: string[]
  dueTopicNames: string[]
  isBusy: boolean
  onToggleTopic: (topicName: string) => void
  onSelectAll: () => void
  onClearAll: () => void
  onSelectDueOnly: () => void
  onStartReview: () => void
}

export default function TopicScopeControls({
  availableTopics,
  selectedTopics,
  dueTopicNames,
  isBusy,
  onToggleTopic,
  onSelectAll,
  onClearAll,
  onSelectDueOnly,
  onStartReview,
}: TopicScopeControlsProps) {
  const selectedCount = selectedTopics.length
  const hasTopics = availableTopics.length > 0

  const summary = useMemo(() => {
    if (availableTopics.length === 0) {
      return 'No topics available'
    }
    if (selectedCount === availableTopics.length) {
      return 'All topics selected'
    }
    if (selectedCount === 0) {
      return 'No topic selected'
    }
    return `${selectedCount} of ${availableTopics.length} selected`
  }, [availableTopics.length, selectedCount])

  return (
    <section className="dashboard-scope" aria-busy={isBusy} aria-live="polite">
      <div className="dashboard-scope__header">
        <div className="dashboard-scope__title-wrap">
          <h2 className="dashboard-scope__title">Topic scope</h2>
          <p className="dashboard-scope__subtitle">
            Choose the subjects for this review sprint.
          </p>
        </div>
        <div className="dashboard-scope__meta">
          <Badge tone="info">{summary}</Badge>
          <Badge tone={dueTopicNames.length > 0 ? 'warning' : 'neutral'}>
            {dueTopicNames.length} due topics
          </Badge>
        </div>
      </div>

      <div className="dashboard-scope__actions">
        <Button
          type="button"
          size="sm"
          variant="ghost"
          onClick={onSelectAll}
          disabled={!hasTopics || isBusy}
        >
          Select all
        </Button>
        <Button
          type="button"
          size="sm"
          variant="ghost"
          onClick={onClearAll}
          disabled={!hasTopics || isBusy}
        >
          Clear all
        </Button>
        <Button
          type="button"
          size="sm"
          variant="secondary"
          onClick={onSelectDueOnly}
          disabled={dueTopicNames.length === 0 || isBusy}
        >
          Due only
        </Button>
        <Button
          type="button"
          variant="secondary"
          onClick={onStartReview}
          disabled={!hasTopics || isBusy}
        >
          Start with selection
        </Button>
      </div>

      {hasTopics ? (
        <div className="dashboard-scope__chips">
          {availableTopics.map((topicName) => {
            const isSelected = selectedTopics.includes(topicName)
            return (
              <button
                key={topicName}
                type="button"
                aria-pressed={isSelected}
                disabled={isBusy}
                onClick={() => onToggleTopic(topicName)}
                className={`dashboard-scope__chip${isSelected ? ' dashboard-scope__chip--active' : ''}`}
              >
                <span className="dashboard-scope__chip-dot" aria-hidden="true" />
                {topicName}
              </button>
            )
          })}
        </div>
      ) : (
        <p className="dashboard-scope__empty">Topics will appear here after initial seeding.</p>
      )}
    </section>
  )
}
