import { cx } from './cx'

type ProgressTone = 'accent' | 'neutral'

export interface ProgressBarProps {
  value: number
  max?: number
  tone?: ProgressTone
  className?: string
  ariaLabel?: string
}

export default function ProgressBar({
  value,
  max = 100,
  tone = 'accent',
  className,
  ariaLabel = 'Progress',
}: ProgressBarProps) {
  const clamped = Math.max(0, Math.min(max, value))

  return (
    <div className={cx('ui-progress', `ui-progress--${tone}`, className)}>
      <progress
        className="ui-progress__track"
        value={clamped}
        max={max}
        aria-label={ariaLabel}
      />
    </div>
  )
}
