import { forwardRef, useId } from 'react'
import type { InputHTMLAttributes } from 'react'

import { cx } from './cx'

type FieldDensity = 'sm' | 'md' | 'lg'

export interface InputProps
  extends Omit<InputHTMLAttributes<HTMLInputElement>, 'size'> {
  label?: string
  hint?: string
  error?: string
  hideLabel?: boolean
  density?: FieldDensity
}

const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  {
    label,
    hint,
    error,
    hideLabel = false,
    density = 'md',
    className,
    id,
    ...rest
  },
  ref,
) {
  const generatedId = useId()
  const fieldId = id ?? `input-${generatedId}`
  const hintId = hint ? `${fieldId}-hint` : undefined
  const errorId = error ? `${fieldId}-error` : undefined
  const describedBy =
    [hintId, errorId].filter(Boolean).join(' ') || undefined

  return (
    <label className={cx('ui-field', className)}>
      {label ? (
        <span className={cx('ui-field__label', hideLabel && 'ui-sr-only')}>
          {label}
        </span>
      ) : null}
      <input
        ref={ref}
        id={fieldId}
        className={cx(
          'ui-input',
          `ui-input--${density}`,
          error && 'ui-input--error',
        )}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        {...rest}
      />
      {hint ? (
        <span id={hintId} className="ui-field__hint">
          {hint}
        </span>
      ) : null}
      {error ? (
        <span id={errorId} className="ui-field__error">
          {error}
        </span>
      ) : null}
    </label>
  )
})

export default Input
