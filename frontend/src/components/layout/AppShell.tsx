import type { ReactNode } from 'react'
import { Outlet } from 'react-router-dom'

import { cx } from '../ui/cx'

type ShellMode = 'workspace' | 'auth' | 'plain'
type ShellWidth = 'narrow' | 'content' | 'wide'

export interface AppShellProps {
  mode?: ShellMode
  width?: ShellWidth
  children?: ReactNode
}

export default function AppShell({
  mode = 'workspace',
  width = 'content',
  children,
}: AppShellProps) {
  return (
    <div className={cx('app-shell', `app-shell--${mode}`)}>
      <div className="app-shell__orb app-shell__orb--a" aria-hidden="true" />
      <div className="app-shell__orb app-shell__orb--b" aria-hidden="true" />
      <main className={cx('app-shell__content', `app-shell__content--${width}`)}>
        {children ?? <Outlet />}
      </main>
    </div>
  )
}
