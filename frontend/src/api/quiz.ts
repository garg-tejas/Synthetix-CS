/**
 * Quiz API endpoints.
 */

import { apiRequest } from './client'
import type {
  QuizSessionAnswerRequest,
  QuizSessionAnswerResponse,
  QuizSessionFinishResponse,
  QuizSessionStartRequest,
  QuizSessionStartResponse,
  QuizStatsResponse,
  TopicStats,
} from './types'

export async function getTopics(): Promise<TopicStats[]> {
  return apiRequest<TopicStats[]>('/api/quiz/topics', {
    method: 'GET',
  })
}

export async function startQuizSession(
  data: QuizSessionStartRequest = {}
): Promise<QuizSessionStartResponse> {
  return apiRequest<QuizSessionStartResponse>('/api/quiz/sessions/start', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function answerQuizSession(
  sessionId: string,
  data: QuizSessionAnswerRequest
): Promise<QuizSessionAnswerResponse> {
  return apiRequest<QuizSessionAnswerResponse>(`/api/quiz/sessions/${sessionId}/answer`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function finishQuizSession(
  sessionId: string
): Promise<QuizSessionFinishResponse> {
  return apiRequest<QuizSessionFinishResponse>(`/api/quiz/sessions/${sessionId}/finish`, {
    method: 'POST',
  })
}

export async function getStats(): Promise<QuizStatsResponse> {
  return apiRequest<QuizStatsResponse>('/api/quiz/stats', {
    method: 'GET',
  })
}
