export interface AuthStatusResponse {
  authenticated: boolean;
  email: string | null;
  display_name: string | null;
}

export interface MessageResponse {
  message: string;
}

export interface EmailStatsResponse {
  unread_count: number;
  total_count: number;
}

export interface CategorySummary {
  category: string;
  count: number;
  recommended_actions: string[];
}

export interface SenderGroupSummary {
  sender_domain: string;
  sender_display: string;
  count: number;
  has_unsubscribe: boolean;
}

export interface ClassifiedEmail {
  id: number;
  gmail_message_id: string;
  gmail_thread_id: string | null;
  sender: string | null;
  sender_domain: string | null;
  subject: string | null;
  snippet: string | null;
  received_at: string | null;
  category: string | null;
  importance: number | null;
  sender_type: string | null;
  confidence: number | null;
  has_unsubscribe: boolean | null;
  unsubscribe_header: string | null;
  unsubscribe_post_header: string | null;
  action_taken: string | null;
}

export interface AnalysisResponse {
  id: number;
  analysis_type: string;
  status: string;
  unread_only: boolean;
  total_emails: number | null;
  processed_emails: number | null;
  use_batch: boolean;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
  summary: CategorySummary[] | null;
  classified_emails: ClassifiedEmail[] | null;
  ai_insights: string[] | null;
}

export interface AnalysisListResponse {
  analyses: AnalysisResponse[];
  total: number;
}

export interface AnalysisCreateRequest {
  analysis_type?: 'inbox_scan' | 'ai';
  unread_only?: boolean;
  max_emails?: number;
  auto_apply?: boolean;
  custom_categories?: string[];
}

export type ActionType = 'keep' | 'move_to_category' | 'mark_read' | 'mark_spam' | 'unsubscribe' | 'undo';

export interface ApplyActionsRequest {
  action: ActionType;
  category?: string;
  sender_domain?: string;
  email_ids?: number[];
}
