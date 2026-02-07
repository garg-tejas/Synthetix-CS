import { useMemo } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { useAuth } from '../auth/AuthContext'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import Card from '../components/ui/Card'
import './landing.css'

interface LandingStep {
  title: string
  detail: string
}

interface LandingCta {
  primaryLabel: string
  primaryTarget: string
  secondaryLabel: string
  secondaryTarget: string
  supportLabel: string
  supportTarget: string
}

const workflowSteps: LandingStep[] = [
  {
    title: 'Capture weak spots',
    detail: 'Spin up a focused card set by topic so each session attacks what is slipping now.',
  },
  {
    title: 'Get instant feedback',
    detail: 'Score quality, see concise guidance, and close each card with a clear next action.',
  },
  {
    title: 'Lock retention rhythm',
    detail: 'Track due and overdue load so daily review stays short, consistent, and compounding.',
  },
]

export default function LandingPage() {
  const { status, user } = useAuth()
  const navigate = useNavigate()

  const cta = useMemo<LandingCta>(() => {
    if (status === 'authenticated') {
      return {
        primaryLabel: 'Open dashboard',
        primaryTarget: '/dashboard',
        secondaryLabel: 'Resume review',
        secondaryTarget: '/review',
        supportLabel: 'Jump into review',
        supportTarget: '/review',
      }
    }

    return {
      primaryLabel: 'Start for free',
      primaryTarget: '/signup',
      secondaryLabel: 'I already have an account',
      secondaryTarget: '/login',
      supportLabel: 'Log in to continue',
      supportTarget: '/login',
    }
  }, [status])

  return (
    <div className="landing layout-stack layout-stack--lg">
      <section className="landing-hero" aria-label="Product overview">
        <div className="landing-hero__glow landing-hero__glow--a" aria-hidden="true" />
        <div className="landing-hero__glow landing-hero__glow--b" aria-hidden="true" />

        <header className="landing-hero__topbar">
          <Link to="/" className="landing-hero__brand">
            <span className="landing-hero__brand-mark" aria-hidden="true" />
            Signal Lab
          </Link>
          <div className="landing-hero__topbar-actions">
            <Badge tone={status === 'authenticated' ? 'success' : 'info'}>
              {status === 'authenticated'
                ? `Signed in as ${user?.username ?? 'member'}`
                : 'Built for consistent recall'}
            </Badge>
          </div>
        </header>

        <div className="landing-hero__content">
          <div className="landing-hero__copy">
            <p className="landing-hero__eyebrow">Memory training, not random quizzes</p>
            <h1 className="landing-hero__title">
              Give your study loop a control room with clear next moves.
            </h1>
            <p className="landing-hero__subtitle">
              Signal Lab helps you review what matters now, score every response, and keep
              retention climbing with short daily sprints.
            </p>

            <div className="landing-hero__actions">
              <Button
                size="lg"
                onClick={() => navigate(cta.primaryTarget)}
              >
                {cta.primaryLabel}
              </Button>
              <Button
                size="lg"
                variant="ghost"
                onClick={() => navigate(cta.secondaryTarget)}
              >
                {cta.secondaryLabel}
              </Button>
            </div>

            <ul className="landing-hero__proof-list">
              <li>Topic-scoped review sessions</li>
              <li>Actionable per-answer feedback</li>
              <li>Daily due and overdue tracking</li>
            </ul>
          </div>

          <Card
            tone="accent"
            padding="lg"
            className="landing-hero__panel"
            kicker="Session blueprint"
            title="From prompt to retention in one flow"
            subtitle="Built to keep your queue clean without long study marathons."
          >
            <div className="landing-hero__panel-stats" role="list" aria-label="Core outcomes">
              <div role="listitem">
                <span>Focus</span>
                <strong>Topic-level filtering</strong>
              </div>
              <div role="listitem">
                <span>Feedback</span>
                <strong>Answer quality signal</strong>
              </div>
              <div role="listitem">
                <span>Rhythm</span>
                <strong>Due queue visibility</strong>
              </div>
            </div>
          </Card>
        </div>
      </section>

      <section className="landing-workflow" aria-label="How it works">
        {workflowSteps.map((step, index) => (
          <Card
            key={step.title}
            className="landing-workflow__card"
            tone={index === 1 ? 'accent' : 'default'}
            padding="md"
            kicker={`Step ${index + 1}`}
            title={step.title}
            subtitle={step.detail}
          />
        ))}
      </section>

      <section className="landing-final-cta" aria-label="Call to action">
        <h2>Ready to make review sessions feel deliberate?</h2>
        <p>
          Start with your current topics and run one focused loop today.
        </p>
        <div className="landing-final-cta__actions">
          <Button size="lg" onClick={() => navigate(cta.primaryTarget)}>
            {cta.primaryLabel}
          </Button>
          <Button size="lg" variant="secondary" onClick={() => navigate(cta.supportTarget)}>
            {cta.supportLabel}
          </Button>
        </div>
      </section>
    </div>
  )
}
