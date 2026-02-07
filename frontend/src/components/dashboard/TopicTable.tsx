import { useMemo } from 'react'

import type { TopicStats } from '../../api/types'
import { Badge } from '../ui'
import ProgressBar from '../ui/ProgressBar'

interface TopicTableProps {
  topics: TopicStats[]
}

type TopicTone = 'success' | 'warning' | 'danger'

interface TopicRowState {
  topicName: string
  learned: number
  total: number
  dueToday: number
  overdue: number
  queue: number
  progressPercent: number
  statusTone: TopicTone
  statusLabel: string
}

export default function TopicTable({ topics }: TopicTableProps) {
  const sorted = useMemo<TopicRowState[]>(() => {
    return topics
      .map((topic) => {
        const queue = topic.due_today + topic.overdue
        const progressPercent =
          topic.total > 0 ? Math.round((topic.learned / topic.total) * 100) : 0
        const statusTone: TopicTone =
          topic.overdue > 0 ? 'danger' : topic.due_today > 0 ? 'warning' : 'success'
        const statusLabel =
          topic.overdue > 0 ? 'Overdue' : topic.due_today > 0 ? 'Due' : 'Stable'

        return {
          topicName: topic.topic,
          learned: topic.learned,
          total: topic.total,
          dueToday: topic.due_today,
          overdue: topic.overdue,
          queue,
          progressPercent,
          statusTone,
          statusLabel,
        }
      })
      .sort((a, b) => {
        if (a.queue !== b.queue) {
          return b.queue - a.queue
        }
        return a.topicName.localeCompare(b.topicName)
      })
  }, [topics])

  return (
    <div className="dashboard-topic-grid">
      <div className="dashboard-topic-table">
        <table className="dashboard-topic-table__table">
          <thead>
            <tr>
              <th>Topic</th>
              <th>Progress</th>
              <th>Due today</th>
              <th>Overdue</th>
              <th>Queue</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((topic) => (
              <tr key={topic.topicName} data-tone={topic.statusTone}>
                <td className="dashboard-topic-table__topic">
                  <strong>{topic.topicName}</strong>
                  <Badge tone={topic.statusTone}>{topic.statusLabel}</Badge>
                </td>
                <td className="dashboard-topic-table__progress">
                  <div className="dashboard-topic-table__progress-meta">
                    <span>
                      {topic.learned}/{topic.total}
                    </span>
                    <span>{topic.progressPercent}%</span>
                  </div>
                  <ProgressBar
                    value={topic.progressPercent}
                    className="dashboard-topic-table__progress-bar"
                    ariaLabel={`${topic.topicName} progress`}
                  />
                </td>
                <td className="dashboard-topic-table__metric">{topic.dueToday}</td>
                <td className="dashboard-topic-table__metric">{topic.overdue}</td>
                <td className="dashboard-topic-table__metric">{topic.queue}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="dashboard-topic-cards" aria-label="Topic statistics">
        {sorted.map((topic) => (
          <article
            key={`${topic.topicName}-card`}
            className="dashboard-topic-card"
            data-tone={topic.statusTone}
          >
            <div className="dashboard-topic-card__head">
              <strong>{topic.topicName}</strong>
              <Badge tone={topic.statusTone}>{topic.statusLabel}</Badge>
            </div>
            <div className="dashboard-topic-card__progress">
              <div className="dashboard-topic-table__progress-meta">
                <span>
                  {topic.learned}/{topic.total}
                </span>
                <span>{topic.progressPercent}%</span>
              </div>
              <ProgressBar
                value={topic.progressPercent}
                className="dashboard-topic-table__progress-bar"
                ariaLabel={`${topic.topicName} progress`}
              />
            </div>
            <dl className="dashboard-topic-card__metrics">
              <div>
                <dt>Due</dt>
                <dd>{topic.dueToday}</dd>
              </div>
              <div>
                <dt>Overdue</dt>
                <dd>{topic.overdue}</dd>
              </div>
              <div>
                <dt>Queue</dt>
                <dd>{topic.queue}</dd>
              </div>
            </dl>
          </article>
        ))}
      </div>
    </div>
  )
}
