import type { HTMLAttributes, ReactNode } from 'react'

import { cx } from './cx'

type CardTone = 'default' | 'inset' | 'accent'
type CardPadding = 'sm' | 'md' | 'lg'

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  title?: string
  subtitle?: string
  kicker?: string
  actions?: ReactNode
  tone?: CardTone
  padding?: CardPadding
  interactive?: boolean
}

export default function Card({
  title,
  subtitle,
  kicker,
  actions,
  tone = 'default',
  padding = 'md',
  interactive = false,
  className,
  children,
  ...rest
}: CardProps) {
  return (
    <div
      className={cx(
        'ui-card',
        `ui-card--${tone}`,
        `ui-card--pad-${padding}`,
        interactive && 'ui-card--interactive',
        className,
      )}
      {...rest}
    >
      {title || subtitle || kicker || actions ? (
        <header className="ui-card__header">
          <div className="ui-card__title-wrap">
            {kicker ? <span className="ui-card__kicker">{kicker}</span> : null}
            {title ? <h3 className="ui-card__title">{title}</h3> : null}
            {subtitle ? <p className="ui-card__subtitle">{subtitle}</p> : null}
          </div>
          {actions ? <div className="ui-card__actions">{actions}</div> : null}
        </header>
      ) : null}
      {children}
    </div>
  )
}
