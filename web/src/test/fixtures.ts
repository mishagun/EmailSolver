import type { AnalysisResponse, ClassifiedEmail, SenderGroupSummary } from '../api/types';

export const mockEmail: ClassifiedEmail = {
  id: 1,
  gmail_message_id: 'msg-1',
  gmail_thread_id: 'thread-1',
  sender: 'test@example.com',
  sender_domain: 'example.com',
  subject: 'test email subject',
  snippet: 'this is a test email snippet',
  received_at: '2026-03-10T10:00:00Z',
  category: 'primary',
  importance: 3,
  sender_type: 'person',
  confidence: 0.95,
  has_unsubscribe: false,
  unsubscribe_header: null,
  unsubscribe_post_header: null,
  action_taken: null,
};

export const mockEmail2: ClassifiedEmail = {
  id: 2,
  gmail_message_id: 'msg-2',
  gmail_thread_id: 'thread-2',
  sender: 'newsletter@news.com',
  sender_domain: 'news.com',
  subject: 'weekly newsletter',
  snippet: 'this week in tech',
  received_at: '2026-03-09T10:00:00Z',
  category: 'newsletters',
  importance: 1,
  sender_type: 'newsletter',
  confidence: 0.88,
  has_unsubscribe: true,
  unsubscribe_header: 'https://news.com/unsub',
  unsubscribe_post_header: 'List-Unsubscribe=One-Click',
  action_taken: null,
};

export const mockAnalysis: AnalysisResponse = {
  id: 1,
  analysis_type: 'ai',
  status: 'completed',
  unread_only: true,
  total_emails: 2,
  processed_emails: 2,
  error_message: null,
  created_at: '2026-03-10T09:00:00Z',
  completed_at: '2026-03-10T09:05:00Z',
  summary: [
    { category: 'primary', count: 1, recommended_actions: ['keep'] },
    { category: 'newsletters', count: 1, recommended_actions: ['unsubscribe', 'mark_read'] },
  ],
  classified_emails: [mockEmail, mockEmail2],
  ai_insights: ["only 1 out of 2 emails here was from a human", "newsletters outnumber real mail"],
};

export const mockProcessingAnalysis: AnalysisResponse = {
  id: 2,
  analysis_type: 'ai',
  status: 'processing',
  unread_only: true,
  total_emails: 50,
  processed_emails: 25,
  error_message: null,
  created_at: '2026-03-10T10:00:00Z',
  completed_at: null,
  summary: null,
  classified_emails: null,
  ai_insights: null,
};

export const mockSenders: SenderGroupSummary[] = [
  { sender_domain: 'example.com', sender_display: 'test user', count: 5, has_unsubscribe: false },
  { sender_domain: 'news.com', sender_display: 'news corp', count: 12, has_unsubscribe: true },
];
