import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

export interface PageHeaderProps {
  title: string
  subtitle?: ReactNode
  eyebrow?: string
  actions?: ReactNode
  backHref?: string
  backLabel?: string
}

export default function PageHeader({
  title,
  subtitle,
  eyebrow,
  actions,
  backHref,
  backLabel,
}: PageHeaderProps) {
  return (
    <header className="page-header">
      <div className="page-header__copy">
        {eyebrow ? <p className="page-header__eyebrow">{eyebrow}</p> : null}
        <h1 className="page-header__title">{title}</h1>
        {subtitle ? <div className="page-header__subtitle">{subtitle}</div> : null}
      </div>
      <div className="page-header__actions">
        {backHref && backLabel ? (
          <Link to={backHref} className="page-header__back-link">
            {backLabel}
          </Link>
        ) : null}
        {actions}
      </div>
    </header>
  )
}
