import type { HTMLAttributes } from 'react'

import { cx } from './cx'

type BadgeTone = 'neutral' | 'info' | 'success' | 'warning' | 'danger'

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: BadgeTone
}

export default function Badge({
  tone = 'neutral',
  className,
  children,
  ...rest
}: BadgeProps) {
  return (
    <span className={cx('ui-badge', `ui-badge--${tone}`, className)} {...rest}>
      {children}
    </span>
  )
}
