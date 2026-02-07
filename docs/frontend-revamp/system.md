# Frontend Design System Usage (C5.2)

Date: 2026-02-07
Scope: `frontend/src` (routes + shared UI/layout)

## 1. Style Layering

Use this order for any new styling work:

1. `frontend/src/styles/tokens.css`
2. `frontend/src/styles/base.css`
3. `frontend/src/styles/motion.css`
4. `frontend/src/styles/utilities.css`
5. Component or route scoped CSS files

Rules:
- Add or change shared primitives in `tokens.css` first.
- Keep route-specific visuals in route CSS (`dashboard.css`, `review.css`).
- Keep global motion and reduced-motion logic in `motion.css`.

## 2. Core Tokens

Primary token groups:
- Typography: `--font-display`, `--font-body`, `--font-mono`
- Surfaces: `--surface-canvas`, `--surface-0`, `--surface-1`, `--surface-inset`
- Text: `--text-strong`, `--text-body`, `--text-muted`
- Accent/status: `--accent-primary`, `--accent-secondary`, `--danger-strong`
- Motion: `--motion-fast`, `--motion-base`, `--motion-slow`, `--ease-standard`, `--ease-emphasis`

Token usage rule:
- Do not hardcode color values in route components.
- If a value repeats across at least two components, promote it to a token.

## 3. Shared Components

Prefer these primitives before writing custom markup:
- `Button`, `Input`, `Textarea`, `Card`, `Badge`, `StateMessage`, `ProgressBar`
- Layout: `AppShell`, `PageHeader`, `AuthLayout`

Progress visuals:
- Use `ProgressBar` instead of inline width styles.
- Keep track-specific sizing in local CSS through `.ui-progress__track`.

Import convention:
- Prefer direct imports from concrete component files for app routes.
- Avoid broad barrel imports in route files for clearer bundle ownership.

## 4. Accessibility Baseline

Minimum requirements for new UI:
- Keyboard-visible focus states on all interactive controls.
- `role="alert"` for blocking form errors.
- `role="status"` with `aria-live="polite"` for async pending status.
- Inputs must have label text and meaningful hints/errors.
- Respect `prefers-reduced-motion` (do not bypass global motion guardrails).

## 5. Route Responsibilities

- `DashboardPage`: mission framing, scope controls, topic queue status
- `ReviewPage`: question workspace, answer composer, feedback transition
- `LoginPage` and `SignupPage`: account entry and validation flows

When a route grows:
- Extract repeated blocks to `frontend/src/components/<domain>/`.
- Keep API logic in route container; move pure display into local components.

## 6. Inline Style Policy

Current target:
- No remaining `style={{ ... }}` in route and domain components.

Policy:
- Use classes and tokens for static and stateful styling.
- If a dynamic visual value is needed, prefer semantic component props (example: `ProgressBar value`) over inline style objects.

## 7. Checklist for Future UI Changes

Before commit:
1. No new hardcoded color literals in TSX.
2. No new inline style objects in route/domain components.
3. Focus-visible and reduced-motion behavior preserved.
4. `pnpm --dir frontend build` passes.
5. Verify desktop and mobile layouts for each touched route.
