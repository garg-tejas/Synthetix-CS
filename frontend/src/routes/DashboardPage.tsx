import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { getStats } from '../api/quiz'
import type { ApiError } from '../api/client'
import type { TopicStats } from '../api/types'
import { useAuth } from '../auth/AuthContext'

export default function DashboardPage() {
  const { user, clearSession } = useAuth()
  const navigate = useNavigate()

  const [topics, setTopics] = useState<TopicStats[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    const run = async () => {
      setIsLoading(true)
      setError(null)
      try {
        const data = await getStats()
        if (cancelled) return
        setTopics(data.topics || [])
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
    const dueToday = topics.reduce((acc, t) => acc + (t.due_today || 0), 0)
    const overdue = topics.reduce((acc, t) => acc + (t.overdue || 0), 0)
    return { totalCards, dueToday, overdue }
  }, [topics])

  return (
    <div style={{ padding: 24, maxWidth: 980, margin: '0 auto' }}>
      <header
        style={{
          display: 'flex',
          alignItems: 'baseline',
          justifyContent: 'space-between',
          gap: 12,
          marginBottom: 18,
        }}
      >
        <div>
          <h1 style={{ marginBottom: 6 }}>Dashboard</h1>
          <div style={{ opacity: 0.8 }}>
            {user ? (
              <>
                Signed in as <strong>{user.username}</strong>
              </>
            ) : (
              'Signed in'
            )}
          </div>
        </div>
        <button onClick={clearSession} style={{ padding: 10, cursor: 'pointer' }}>
          Log out
        </button>
      </header>

      <section
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(3, minmax(0, 1fr))',
          gap: 12,
          marginBottom: 18,
        }}
      >
        <StatCard label="Total cards" value={totals.totalCards} />
        <StatCard label="Due today" value={totals.dueToday} />
        <StatCard label="Overdue" value={totals.overdue} />
      </section>

      <section style={{ marginBottom: 18 }}>
        <button
          type="button"
          onClick={() => navigate('/review')}
          style={{
            padding: '10px 12px',
            cursor: 'pointer',
          }}
        >
          Start review
        </button>
      </section>

      <section>
        <h2 style={{ marginBottom: 10 }}>By topic</h2>

        {isLoading ? <div>Loading…</div> : null}
        {error ? <div style={{ color: '#b00020' }}>{error}</div> : null}

        {!isLoading && !error && topics.length === 0 ? (
          <div style={{ opacity: 0.8 }}>No topics found yet.</div>
        ) : null}

        {!isLoading && !error && topics.length > 0 ? (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ textAlign: 'left' }}>
                  <th style={{ padding: '10px 8px', borderBottom: '1px solid #ddd' }}>
                    Topic
                  </th>
                  <th style={{ padding: '10px 8px', borderBottom: '1px solid #ddd' }}>
                    Total
                  </th>
                  <th style={{ padding: '10px 8px', borderBottom: '1px solid #ddd' }}>
                    Learned
                  </th>
                  <th style={{ padding: '10px 8px', borderBottom: '1px solid #ddd' }}>
                    Due today
                  </th>
                  <th style={{ padding: '10px 8px', borderBottom: '1px solid #ddd' }}>
                    Overdue
                  </th>
                </tr>
              </thead>
              <tbody>
                {topics.map((t) => (
                  <tr key={t.topic}>
                    <td style={{ padding: '10px 8px', borderBottom: '1px solid #eee' }}>
                      <strong>{t.topic}</strong>
                    </td>
                    <td style={{ padding: '10px 8px', borderBottom: '1px solid #eee' }}>
                      {t.total}
                    </td>
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

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div
      style={{
        border: '1px solid #e5e5e5',
        borderRadius: 12,
        padding: 14,
        background: '#fff',
      }}
    >
      <div style={{ fontSize: 12, letterSpacing: 0.2, opacity: 0.7 }}>{label}</div>
      <div style={{ fontSize: 28, marginTop: 4 }}>{value}</div>
    </div>
  )
}

