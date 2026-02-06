import type { HTMLAttributes, ReactNode } from 'react'

import { cx } from './cx'

type StateTone = 'info' | 'success' | 'warning' | 'danger'

export interface StateMessageProps extends HTMLAttributes<HTMLDivElement> {
  title?: string
  tone?: StateTone
  icon?: ReactNode
}

export default function StateMessage({
  title,
  tone = 'info',
  icon,
  className,
  children,
  ...rest
}: StateMessageProps) {
  return (
    <div className={cx('ui-state', `ui-state--${tone}`, className)} {...rest}>
      {icon ? <div className="ui-state__icon">{icon}</div> : null}
      <div className="ui-state__body">
        {title ? <h4 className="ui-state__title">{title}</h4> : null}
        {children ? <p className="ui-state__text">{children}</p> : null}
      </div>
    </div>
  )
}
