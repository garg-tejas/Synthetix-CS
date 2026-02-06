import type { TopicStats } from '../../api/types'
import { Badge } from '../ui'

interface TopicTableProps {
  topics: TopicStats[]
}

export default function TopicTable({ topics }: TopicTableProps) {
  const sorted = [...topics].sort((a, b) => {
    const pressureA = a.overdue + a.due_today
    const pressureB = b.overdue + b.due_today
    if (pressureA !== pressureB) {
      return pressureB - pressureA
    }
    return a.topic.localeCompare(b.topic)
  })

  return (
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
          {sorted.map((topic) => {
            const queue = topic.due_today + topic.overdue
            const progressPercent =
              topic.total > 0 ? Math.round((topic.learned / topic.total) * 100) : 0
            const statusTone =
              topic.overdue > 0
                ? 'danger'
                : topic.due_today > 0
                  ? 'warning'
                  : 'success'
            const statusLabel =
              topic.overdue > 0
                ? 'Overdue'
                : topic.due_today > 0
                  ? 'Due'
                  : 'Stable'

            return (
              <tr
                key={topic.topic}
                data-tone={statusTone}
              >
                <td className="dashboard-topic-table__topic">
                  <strong>{topic.topic}</strong>
                  <Badge tone={statusTone}>{statusLabel}</Badge>
                </td>
                <td className="dashboard-topic-table__progress">
                  <div className="dashboard-topic-table__progress-meta">
                    <span>{topic.learned}/{topic.total}</span>
                    <span>{progressPercent}%</span>
                  </div>
                  <div className="dashboard-topic-table__progress-track" role="presentation">
                    <span
                      className="dashboard-topic-table__progress-fill"
                      style={{ width: `${progressPercent}%` }}
                    />
                  </div>
                </td>
                <td className="dashboard-topic-table__metric">{topic.due_today}</td>
                <td className="dashboard-topic-table__metric">{topic.overdue}</td>
                <td className="dashboard-topic-table__metric">{queue}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
