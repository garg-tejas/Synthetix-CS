import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import type { ApiError } from '../api/client'
import { getStats, getTopics } from '../api/quiz'
import type { TopicStats } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { PageHeader } from '../components/layout'
import { Badge, Button, Card, StateMessage } from '../components/ui'
import './dashboard.css'

interface MissionState {
  title: string
  description: string
  badgeTone: 'success' | 'warning' | 'danger'
  badgeLabel: string
}

export default function DashboardPage() {
  const { user, clearSession } = useAuth()
  const navigate = useNavigate()

  const [topics, setTopics] = useState<TopicStats[]>([])
  const [availableTopics, setAvailableTopics] = useState<string[]>([])
  const [selectedTopics, setSelectedTopics] = useState<string[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    const run = async () => {
      setIsLoading(true)
      setError(null)
      try {
        const [stats, topicsList] = await Promise.all([getStats(), getTopics()])
        if (cancelled) return
        setTopics(stats.topics || [])
        const names = (topicsList || []).map((t) => t.topic).sort()
        setAvailableTopics(names)
        setSelectedTopics(names)
      } catch (err) {
        if (cancelled) return
        const apiErr = err as ApiError
        setError(apiErr.detail || 'Failed to load stats')
      } finally {
        if (!cancelled) setIsLoading(false)
      }
    }
    run()
    return () => {
      cancelled = true
    }
  }, [])

  const totals = useMemo(() => {
    const totalCards = topics.reduce((acc, t) => acc + (t.total || 0), 0)
    const learnedCards = topics.reduce((acc, t) => acc + (t.learned || 0), 0)
    const dueToday = topics.reduce((acc, t) => acc + (t.due_today || 0), 0)
    const overdue = topics.reduce((acc, t) => acc + (t.overdue || 0), 0)
    return { totalCards, learnedCards, dueToday, overdue }
  }, [topics])

  const completionRate = useMemo(() => {
    if (totals.totalCards === 0) return 0
    return Math.round((totals.learnedCards / totals.totalCards) * 100)
  }, [totals.learnedCards, totals.totalCards])

  const mission = useMemo<MissionState>(() => {
    if (totals.overdue > 0) {
      return {
        title: 'Recover the overdue queue',
        description: `${totals.overdue} cards have slipped. Prioritize a short cleanup sprint now.`,
        badgeTone: 'danger',
        badgeLabel: 'Critical',
      }
    }

    if (totals.dueToday > 0) {
      return {
        title: 'Finish today\'s review set',
        description: `${totals.dueToday} cards are due today. Keep your streak stable with one focused session.`,
        badgeTone: 'warning',
        badgeLabel: 'Active',
      }
    }

    return {
      title: 'Rhythm is on track',
      description: 'No immediate backlog. A light review pass can build buffer for tomorrow.',
      badgeTone: 'success',
      badgeLabel: 'Stable',
    }
  }, [totals.dueToday, totals.overdue])

  const selectionSummary =
    selectedTopics.length === availableTopics.length
      ? 'All topics selected'
      : `${selectedTopics.length} of ${availableTopics.length} topics selected`

  const startReview = () => {
    navigate('/review', {
      state: { topics: selectedTopics.length ? selectedTopics : null },
    })
  }

  return (
    <div className="dashboard layout-stack layout-stack--lg">
      <PageHeader
        eyebrow="Signal Lab"
        title="Dashboard"
        subtitle="Monitor your study rhythm and launch the next review sprint."
      />

      <section className="dashboard-hero">
        <Card
          tone="accent"
          padding="lg"
          className="dashboard-hero__mission"
          kicker="Daily mission"
          title={mission.title}
          subtitle={mission.description}
          actions={<Badge tone={mission.badgeTone}>{mission.badgeLabel}</Badge>}
        >
          <div className="dashboard-hero__mission-grid">
            <div className="dashboard-hero__metric">
              <span className="dashboard-hero__metric-label">Due now</span>
              <strong className="dashboard-hero__metric-value">
                {totals.dueToday + totals.overdue}
              </strong>
            </div>
            <div className="dashboard-hero__metric">
              <span className="dashboard-hero__metric-label">Completion</span>
              <strong className="dashboard-hero__metric-value">{completionRate}%</strong>
            </div>
            <div className="dashboard-hero__metric">
              <span className="dashboard-hero__metric-label">Topics in scope</span>
              <strong className="dashboard-hero__metric-value">{selectedTopics.length}</strong>
            </div>
          </div>
          <div className="dashboard-hero__actions">
            <Button type="button" size="lg" onClick={startReview}>
              Start review session
            </Button>
            <p className="dashboard-hero__hint">{selectionSummary}</p>
          </div>
        </Card>

        <Card
          tone="default"
          className="dashboard-hero__profile"
          kicker="Account overview"
          title={user?.username ?? 'Signed in'}
          subtitle={user?.email ?? 'Authenticated session'}
          actions={<Button variant="ghost" size="sm" onClick={clearSession}>Log out</Button>}
        >
          <dl className="dashboard-summary">
            <div className="dashboard-summary__item">
              <dt>Cards learned</dt>
              <dd>{totals.learnedCards}</dd>
            </div>
            <div className="dashboard-summary__item">
              <dt>Total cards</dt>
              <dd>{totals.totalCards}</dd>
            </div>
            <div className="dashboard-summary__item">
              <dt>Topics tracked</dt>
              <dd>{availableTopics.length}</dd>
            </div>
            <div className="dashboard-summary__item">
              <dt>Completion</dt>
              <dd>{completionRate}%</dd>
            </div>
          </dl>
        </Card>
      </section>

      <section className="dashboard-stats" aria-label="Review statistics">
        <DashboardStat
          label="Total cards"
          value={totals.totalCards}
          detail={`${totals.learnedCards} learned`}
          tone="info"
        />
        <DashboardStat
          label="Due today"
          value={totals.dueToday}
          detail={totals.dueToday > 0 ? 'Ready in this cycle' : 'Nothing new due'}
          tone={totals.dueToday > 0 ? 'warning' : 'success'}
        />
        <DashboardStat
          label="Overdue"
          value={totals.overdue}
          detail={totals.overdue > 0 ? 'Needs catch-up' : 'Queue is clean'}
          tone={totals.overdue > 0 ? 'danger' : 'success'}
        />
      </section>

      <section className="dashboard-filter">
        <h2 className="dashboard-filter__title">Topic scope</h2>
        <div className="dashboard-filter__controls">
          {availableTopics.map((name) => {
            const checked = selectedTopics.includes(name)
            return (
              <label key={name} className="dashboard-filter__chip">
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={() => {
                    setSelectedTopics((prev) =>
                      prev.includes(name) ? prev.filter((t) => t !== name) : [...prev, name],
                    )
                  }}
                />
                {name}
              </label>
            )
          })}
          <Button type="button" variant="secondary" onClick={startReview}>
            Start review
          </Button>
        </div>
      </section>

      <section className="dashboard-topics">
        <h2 className="dashboard-topics__title">By topic</h2>

        {isLoading ? (
          <StateMessage title="Loading dashboard data" tone="info">
            Fetching topic stats and review availability.
          </StateMessage>
        ) : null}

        {error ? (
          <StateMessage title="Failed to load dashboard" tone="danger">
            {error}
          </StateMessage>
        ) : null}

        {!isLoading && !error && topics.length === 0 ? (
          <StateMessage title="No topics available yet" tone="warning">
            Seed cards first to populate your review workspace.
          </StateMessage>
        ) : null}

        {!isLoading && !error && topics.length > 0 ? (
          <div className="dashboard-topics__table-wrap">
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ textAlign: 'left' }}>
                  <th style={{ padding: '10px 8px', borderBottom: '1px solid #ddd' }}>Topic</th>
                  <th style={{ padding: '10px 8px', borderBottom: '1px solid #ddd' }}>Total</th>
                  <th style={{ padding: '10px 8px', borderBottom: '1px solid #ddd' }}>Learned</th>
                  <th style={{ padding: '10px 8px', borderBottom: '1px solid #ddd' }}>
                    Due today
                  </th>
                  <th style={{ padding: '10px 8px', borderBottom: '1px solid #ddd' }}>Overdue</th>
                </tr>
              </thead>
              <tbody>
                {topics.map((t) => (
                  <tr key={t.topic}>
                    <td style={{ padding: '10px 8px', borderBottom: '1px solid #eee' }}>
                      <strong>{t.topic}</strong>
                    </td>
                    <td style={{ padding: '10px 8px', borderBottom: '1px solid #eee' }}>{t.total}</td>
                    <td style={{ padding: '10px 8px', borderBottom: '1px solid #eee' }}>
                      {t.learned}
                    </td>
                    <td style={{ padding: '10px 8px', borderBottom: '1px solid #eee' }}>
                      {t.due_today}
                    </td>
                    <td style={{ padding: '10px 8px', borderBottom: '1px solid #eee' }}>
                      {t.overdue}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </section>
    </div>
  )
}

interface DashboardStatProps {
  label: string
  value: number
  detail: string
  tone: 'info' | 'success' | 'warning' | 'danger'
}

function DashboardStat({ label, value, detail, tone }: DashboardStatProps) {
  return (
    <article className={`dashboard-stat dashboard-stat--${tone}`}>
      <p className="dashboard-stat__label">{label}</p>
      <p className="dashboard-stat__value">{value}</p>
      <p className="dashboard-stat__detail">{detail}</p>
    </article>
  )
}
