import { useCallback, useEffect, useMemo, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

import type { ApiError } from '../api/client'
import { finishQuizSession, startQuizSession } from '../api/quiz'
import type { LearningPathNode, QuizCard, SessionProgress } from '../api/types'
import PageHeader from '../components/layout/PageHeader'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import Card from '../components/ui/Card'
import StateMessage from '../components/ui/StateMessage'
import type { ReviewSessionScopeState } from './reviewFlow'
import './learning-path.css'

type SWOTBucket = 'strength' | 'weakness' | 'opportunity' | 'threat'
type PathStatus = 'completed' | 'current' | 'upcoming' | 'locked'

interface PathStageNode {
  node: LearningPathNode
  index: number
  status: PathStatus
  unresolvedPrerequisiteKeys: string[]
}

interface SubjectSWOTSummary {
  subject: string
  buckets: Record<SWOTBucket, LearningPathNode[]>
}

function clampLimit(value: number): number {
  return Math.max(1, Math.min(100, Math.round(value)))
}

function normalizeBucket(value: string): SWOTBucket {
  const normalized = value.trim().toLowerCase()
  if (normalized === 'strength') return 'strength'
  if (normalized === 'weakness') return 'weakness'
  if (normalized === 'threat') return 'threat'
  return 'opportunity'
}

function emptyBuckets(): Record<SWOTBucket, LearningPathNode[]> {
  return {
    strength: [],
    weakness: [],
    opportunity: [],
    threat: [],
  }
}

function statusTone(status: PathStatus): 'neutral' | 'info' | 'success' | 'warning' {
  if (status === 'completed') return 'success'
  if (status === 'current') return 'info'
  if (status === 'upcoming') return 'warning'
  return 'neutral'
}

function swotTone(bucket: SWOTBucket): 'neutral' | 'info' | 'success' | 'warning' | 'danger' {
  if (bucket === 'strength') return 'success'
  if (bucket === 'weakness') return 'danger'
  if (bucket === 'threat') return 'warning'
  return 'info'
}

function toTopicLabel(topicKey: string): string {
  const tail = topicKey.split(':').pop() || topicKey
  return tail.replace(/[-_]/g, ' ')
}

export default function LearningPathPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const routeState = (location.state as ReviewSessionScopeState | null) ?? null

  const [pathNodes, setPathNodes] = useState<LearningPathNode[]>([])
  const [progress, setProgress] = useState<SessionProgress | null>(null)
  const [currentCard, setCurrentCard] = useState<QuizCard | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadPathPreview = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    const topics = routeState?.topics && routeState.topics.length ? routeState.topics : undefined
    const subject = (routeState?.subject || '').trim().toLowerCase() || undefined
    const limit = typeof routeState?.limit === 'number' ? clampLimit(routeState.limit) : 10

    try {
      const preview = await startQuizSession({ topics, subject, limit })
      setPathNodes(preview.path || [])
      setProgress(preview.progress)
      setCurrentCard(preview.current_card || null)
      // Path preview uses a temporary session only to fetch scoped path metadata.
      void finishQuizSession(preview.session_id).catch(() => undefined)
    } catch (err) {
      const apiErr = err as ApiError
      setError(apiErr.detail || 'Failed to load learning path preview')
    } finally {
      setIsLoading(false)
    }
  }, [routeState?.limit, routeState?.subject, routeState?.topics])

  useEffect(() => {
    void loadPathPreview()
  }, [loadPathPreview])

  const nextScopeState = useMemo<ReviewSessionScopeState>(
    () => ({
      topics: routeState?.topics && routeState.topics.length > 0 ? routeState.topics : null,
      subject: routeState?.subject || null,
      limit: typeof routeState?.limit === 'number' ? clampLimit(routeState.limit) : 10,
    }),
    [routeState?.limit, routeState?.subject, routeState?.topics],
  )

  const currentIndex = useMemo(() => {
    if (pathNodes.length === 0) return -1
    const pointer = progress?.completed ? pathNodes.length - 1 : progress?.current_index ?? 0
    return Math.max(0, Math.min(pathNodes.length - 1, pointer))
  }, [pathNodes.length, progress?.completed, progress?.current_index])

  const displayNameByTopicKey = useMemo(() => {
    const map = new Map<string, string>()
    for (const node of pathNodes) {
      map.set(node.topic_key, node.display_name)
    }
    return map
  }, [pathNodes])

  const stageNodes = useMemo<PathStageNode[]>(() => {
    if (pathNodes.length === 0) return []
    const completedKeys = new Set(
      pathNodes.slice(0, Math.max(0, currentIndex)).map((node) => node.topic_key),
    )
    return pathNodes.map((node, index) => {
      const prerequisites = node.prerequisite_topic_keys || []
      const unresolvedPrerequisiteKeys = prerequisites.filter(
        (topicKey) => !completedKeys.has(topicKey),
      )
      let status: PathStatus
      if (index < currentIndex) {
        status = 'completed'
      } else if (index === currentIndex) {
        status = 'current'
      } else if (unresolvedPrerequisiteKeys.length > 0) {
        status = 'locked'
      } else {
        status = 'upcoming'
      }
      return { node, index, status, unresolvedPrerequisiteKeys }
    })
  }, [currentIndex, pathNodes])

  const currentNode = useMemo(
    () => stageNodes.find((entry) => entry.status === 'current') ?? null,
    [stageNodes],
  )

  const subjectSummaries = useMemo<SubjectSWOTSummary[]>(() => {
    const bySubject = new Map<string, SubjectSWOTSummary>()
    for (const node of pathNodes) {
      const subjectKey = node.subject.toUpperCase()
      if (!bySubject.has(subjectKey)) {
        bySubject.set(subjectKey, {
          subject: subjectKey,
          buckets: emptyBuckets(),
        })
      }
      const summary = bySubject.get(subjectKey)
      if (!summary) continue
      const bucket = normalizeBucket(node.swot_bucket)
      summary.buckets[bucket].push(node)
    }
    return Array.from(bySubject.values()).map((summary) => ({
      ...summary,
      buckets: {
        strength: [...summary.buckets.strength].sort(
          (left, right) => right.priority_score - left.priority_score,
        ),
        weakness: [...summary.buckets.weakness].sort(
          (left, right) => right.priority_score - left.priority_score,
        ),
        opportunity: [...summary.buckets.opportunity].sort(
          (left, right) => right.priority_score - left.priority_score,
        ),
        threat: [...summary.buckets.threat].sort(
          (left, right) => right.priority_score - left.priority_score,
        ),
      },
    }))
  }, [pathNodes])

  const priorityQueue = useMemo(
    () => [...pathNodes].sort((left, right) => right.priority_score - left.priority_score),
    [pathNodes],
  )

  return (
    <div className="learning-path layout-stack layout-stack--lg">
      <PageHeader
        eyebrow="Planning"
        title="Learning path preview"
        subtitle="Review current node, upcoming sequence, and SWOT posture before entering the question workspace."
        backHref="/review/setup"
        backLabel="Back to setup"
      />

      {isLoading ? (
        <StateMessage title="Loading path preview" tone="info">
          Building your path from current mastery and SWOT signals.
        </StateMessage>
      ) : null}

      {error ? (
        <Card tone="default" padding="md" className="learning-path__error">
          <StateMessage title="Path unavailable" tone="danger">
            {error}
          </StateMessage>
          <div className="learning-path__error-actions">
            <Button type="button" onClick={() => void loadPathPreview()}>
              Retry
            </Button>
            <Button type="button" variant="ghost" onClick={() => navigate('/review/setup')}>
              Back to setup
            </Button>
          </div>
        </Card>
      ) : null}

      {!isLoading && !error && pathNodes.length === 0 ? (
        <Card tone="inset" padding="lg">
          <StateMessage title="No path nodes available" tone="warning">
            No eligible nodes were generated for current scope. Try broader topics or remove subject filter.
          </StateMessage>
          <div className="learning-path__actions">
            <Button type="button" variant="secondary" onClick={() => navigate('/review/setup')}>
              Adjust setup
            </Button>
            <Button
              type="button"
              onClick={() =>
                navigate('/review', {
                  state: nextScopeState,
                })
              }
            >
              Start anyway
            </Button>
          </div>
        </Card>
      ) : null}

      {!isLoading && !error && pathNodes.length > 0 ? (
        <>
          <section className="learning-path__hero-grid">
            <Card
              tone="accent"
              padding="lg"
              className="learning-path__focus"
              kicker="Current node"
              title={currentNode ? currentNode.node.display_name : 'No active node'}
              subtitle={
                currentNode
                  ? `${currentNode.node.subject.toUpperCase()} | mastery ${Math.round(currentNode.node.mastery_score)}`
                  : 'Path generation did not return a current node.'
              }
              actions={
                currentNode ? (
                  <Badge tone={swotTone(normalizeBucket(currentNode.node.swot_bucket))}>
                    {currentNode.node.swot_bucket}
                  </Badge>
                ) : undefined
              }
            >
              <div className="learning-path__focus-metrics">
                <article>
                  <span>Queue length</span>
                  <strong>{pathNodes.length}</strong>
                </article>
                <article>
                  <span>Session limit</span>
                  <strong>{nextScopeState.limit}</strong>
                </article>
                <article>
                  <span>Preview question</span>
                  <strong>{currentCard ? 'ready' : 'none'}</strong>
                </article>
              </div>
            </Card>

            <Card
              tone="default"
              padding="lg"
              className="learning-path__sequence"
              kicker="Path sequence"
              title="Current and upcoming nodes"
              subtitle="Locks are based on actual prerequisite edges from topic dependency graph."
            >
              <ol className="learning-path__timeline">
                {stageNodes.slice(0, 8).map((stage) => (
                  <li key={`${stage.node.subject}:${stage.node.topic_key}:${stage.index}`}>
                    <div className="learning-path__timeline-head">
                      <strong>{stage.node.display_name}</strong>
                      <Badge tone={statusTone(stage.status)}>{stage.status}</Badge>
                    </div>
                    <p>
                      {stage.node.subject.toUpperCase()} | mastery {Math.round(stage.node.mastery_score)}
                      {' '}| priority {stage.node.priority_score.toFixed(1)}
                    </p>
                    {stage.node.prerequisite_topic_keys.length > 0 ? (
                      <p className="learning-path__prereq-note">
                        Requires:{' '}
                        {stage.node.prerequisite_topic_keys
                          .map((topicKey) => displayNameByTopicKey.get(topicKey) || toTopicLabel(topicKey))
                          .join(', ')}
                      </p>
                    ) : null}
                    {stage.status === 'locked' ? (
                      <p className="learning-path__lock-note">
                        Locked by pending prerequisites:{' '}
                        {stage.unresolvedPrerequisiteKeys
                          .map((topicKey) => displayNameByTopicKey.get(topicKey) || toTopicLabel(topicKey))
                          .join(', ')}
                      </p>
                    ) : null}
                  </li>
                ))}
              </ol>
            </Card>
          </section>

          <section className="learning-path__swot">
            <h2>SWOT panels by subject</h2>
            <div className="learning-path__swot-grid">
              {subjectSummaries.map((summary) => (
                <Card
                  key={summary.subject}
                  tone="default"
                  padding="md"
                  className="learning-path__swot-card"
                  kicker={summary.subject}
                  title="Subject SWOT"
                >
                  <div className="learning-path__swot-counts">
                    <Badge tone="success">S {summary.buckets.strength.length}</Badge>
                    <Badge tone="danger">W {summary.buckets.weakness.length}</Badge>
                    <Badge tone="info">O {summary.buckets.opportunity.length}</Badge>
                    <Badge tone="warning">T {summary.buckets.threat.length}</Badge>
                  </div>
                  <dl className="learning-path__swot-topics">
                    <div>
                      <dt>Weakness focus</dt>
                      <dd>
                        {summary.buckets.weakness.slice(0, 3).map((node) => node.display_name).join(', ') ||
                          'No weakness nodes in current scope.'}
                      </dd>
                    </div>
                    <div>
                      <dt>Threat watch</dt>
                      <dd>
                        {summary.buckets.threat.slice(0, 3).map((node) => node.display_name).join(', ') ||
                          'No threat nodes in current scope.'}
                      </dd>
                    </div>
                  </dl>
                </Card>
              ))}
            </div>
          </section>

          <Card
            tone="default"
            padding="lg"
            className="learning-path__priority"
            kicker="Topic queue"
            title="Priority-ordered topics"
            subtitle="Higher scores appear first and should be addressed earlier in session."
          >
            <ul className="learning-path__priority-list">
              {priorityQueue.slice(0, 10).map((node) => {
                const bucket = normalizeBucket(node.swot_bucket)
                return (
                  <li key={`${node.subject}:${node.topic_key}`}>
                    <div>
                      <strong>{node.display_name}</strong>
                      <p>
                        {node.subject.toUpperCase()} | mastery {Math.round(node.mastery_score)}
                      </p>
                    </div>
                    <div className="learning-path__priority-meta">
                      <Badge tone={swotTone(bucket)}>{bucket}</Badge>
                      <span>{node.priority_score.toFixed(1)}</span>
                    </div>
                  </li>
                )
              })}
            </ul>
          </Card>

          <section className="learning-path__actions">
            <Button
              type="button"
              variant="ghost"
              onClick={() =>
                navigate('/review/setup', {
                  state: nextScopeState,
                })
              }
            >
              Back to setup
            </Button>
            <Button
              type="button"
              size="lg"
              onClick={() =>
                navigate('/review', {
                  state: nextScopeState,
                })
              }
            >
              Enter review workspace
            </Button>
          </section>
        </>
      ) : null}
    </div>
  )
}
