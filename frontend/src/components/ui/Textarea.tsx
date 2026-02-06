import { forwardRef, useId } from 'react'
import type { TextareaHTMLAttributes } from 'react'

import { cx } from './cx'

type FieldDensity = 'sm' | 'md' | 'lg'

export interface TextareaProps
  extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string
  hint?: string
  error?: string
  hideLabel?: boolean
  density?: FieldDensity
}

const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  function Textarea(
    {
      label,
      hint,
      error,
      hideLabel = false,
      density = 'md',
      className,
      rows = 5,
      id,
      ...rest
    },
    ref,
  ) {
    const generatedId = useId()
    const fieldId = id ?? `textarea-${generatedId}`
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
        <textarea
          ref={ref}
          id={fieldId}
          rows={rows}
          className={cx(
            'ui-input',
            'ui-textarea',
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
  },
)

export default Textarea
