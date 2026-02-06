import { useMemo } from 'react'

import { Badge, Button } from '../ui'

interface TopicScopeControlsProps {
  availableTopics: string[]
  selectedTopics: string[]
  dueTopicNames: string[]
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
  onToggleTopic,
  onSelectAll,
  onClearAll,
  onSelectDueOnly,
  onStartReview,
}: TopicScopeControlsProps) {
  const selectedCount = selectedTopics.length

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
    <section className="dashboard-scope">
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
        <Button type="button" size="sm" variant="ghost" onClick={onSelectAll}>
          Select all
        </Button>
        <Button type="button" size="sm" variant="ghost" onClick={onClearAll}>
          Clear all
        </Button>
        <Button
          type="button"
          size="sm"
          variant="secondary"
          onClick={onSelectDueOnly}
          disabled={dueTopicNames.length === 0}
        >
          Due only
        </Button>
        <Button type="button" variant="secondary" onClick={onStartReview}>
          Start with selection
        </Button>
      </div>

      <div className="dashboard-scope__chips">
        {availableTopics.map((topicName) => {
          const isSelected = selectedTopics.includes(topicName)
          return (
            <button
              key={topicName}
              type="button"
              aria-pressed={isSelected}
              onClick={() => onToggleTopic(topicName)}
              className={`dashboard-scope__chip${isSelected ? ' dashboard-scope__chip--active' : ''}`}
            >
              <span className="dashboard-scope__chip-dot" aria-hidden="true" />
              {topicName}
            </button>
          )
        })}
      </div>
    </section>
  )
}
