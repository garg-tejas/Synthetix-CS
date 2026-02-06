/**
 * Quiz API endpoints.
 */

import { apiRequest } from './client'
import type {
  QuizNextRequest,
  QuizNextResponse,
  QuizAnswerRequest,
  QuizAnswerResponse,
  QuizStatsResponse,
  TopicStats,
} from './types'

export async function getTopics(): Promise<TopicStats[]> {
  return apiRequest<TopicStats[]>('/api/quiz/topics', {
    method: 'GET',
  })
}

export async function getNextCards(
  data: QuizNextRequest = {}
): Promise<QuizNextResponse> {
  return apiRequest<QuizNextResponse>('/api/quiz/next', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function submitAnswer(
  data: QuizAnswerRequest
): Promise<QuizAnswerResponse> {
  return apiRequest<QuizAnswerResponse>('/api/quiz/answer', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function getStats(): Promise<QuizStatsResponse> {
  return apiRequest<QuizStatsResponse>('/api/quiz/stats', {
    method: 'GET',
  })
}
