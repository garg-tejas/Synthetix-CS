export interface ReviewSessionScopeState {
  topics?: string[] | null
  subject?: string | null
  limit?: number | null
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
