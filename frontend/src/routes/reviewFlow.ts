export interface ReviewSessionScopeState {
  topics?: string[] | null
  subject?: string | null
  limit?: number | null
  pathTopicsOrdered?: string[] | null
  preferredTopic?: string | null
  source?: 'learning-path' | 'setup' | null
}

export interface ReviewSummaryState {
  answeredCount: number
  totalCards: number
  averageScore: number | null
  correctCount: number
  partialCount: number
  incorrectCount: number
  remediationCount: number
  topics: string[]
}
