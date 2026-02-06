/**
 * TypeScript types matching backend Pydantic schemas.
 */

// Auth types
export interface SignupRequest {
  email: string
  username: string
  password: string
}

export interface LoginRequest {
  email_or_username: string
  password: string
}

export interface RefreshRequest {
  refresh_token: string
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
}

export interface UserOut {
  id: number
  email: string
  username: string
  is_active: boolean
}

// Quiz types
export interface QuizCard {
  card_id: number
  topic: string
  question: string
  difficulty?: string | null
  question_type?: string | null
}

export interface QuizNextRequest {
  topics?: string[] | null
  limit?: number
}

export interface QuizNextResponse {
  cards: QuizCard[]
  due_count: number
  new_count: number
}

export interface QuizAnswerRequest {
  card_id: number
  user_answer: string
  quality?: number | null
  response_time_ms?: number | null
}

export interface QuizAnswerResponse {
  answer: string
  explanation?: string | null
  source_chunk_id?: string | null
  model_score?: number | null
  verdict?: string | null
  next_due_at?: string | null
  interval_days?: number | null
}

export interface TopicStats {
  topic: string
  total: number
  learned: number
  due_today: number
  overdue: number
}

export interface QuizStatsResponse {
  topics: TopicStats[]
}
