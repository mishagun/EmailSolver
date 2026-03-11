import type {
  AnalysisCreateRequest,
  AnalysisListResponse,
  AnalysisResponse,
  ApplyActionsRequest,
  AuthStatusResponse,
  EmailStatsResponse,
  MessageResponse,
  SenderGroupSummary,
} from './types';

export class ApiError extends Error {
  statusCode: number;
  detail: string;

  constructor(statusCode: number, detail: string) {
    super(`[${statusCode}] ${detail}`);
    this.statusCode = statusCode;
    this.detail = detail;
  }
}

class TidyInboxClient {
  private baseUrl: string;
  private token: string | null = null;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  setToken(token: string): void {
    this.token = token;
  }

  clearToken(): void {
    this.token = null;
  }

  getLoginUrl(redirectUrl: string): string {
    return `${this.baseUrl}/api/v1/auth/login?redirect_url=${encodeURIComponent(redirectUrl)}`;
  }

  private async request<T>(method: string, path: string, body?: unknown, params?: Record<string, string>): Promise<T> {
    let url = `${this.baseUrl}${path}`;
    if (params) {
      const searchParams = new URLSearchParams(params);
      url += `?${searchParams.toString()}`;
    }

    const headers: Record<string, string> = {};
    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }
    if (body) {
      headers['Content-Type'] = 'application/json';
    }

    const response = await fetch(url, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
    });

    if (!response.ok) {
      let detail: string;
      try {
        const json = await response.json();
        detail = json.detail || response.statusText;
      } catch {
        detail = response.statusText;
      }
      throw new ApiError(response.status, detail);
    }

    return response.json();
  }

  async getAuthStatus(): Promise<AuthStatusResponse> {
    return this.request('GET', '/api/v1/auth/status');
  }

  async logout(): Promise<MessageResponse> {
    return this.request('DELETE', '/api/v1/auth/logout');
  }

  async getEmailStats(): Promise<EmailStatsResponse> {
    return this.request('GET', '/api/v1/emails/stats');
  }

  async createAnalysis(req: AnalysisCreateRequest): Promise<AnalysisResponse> {
    return this.request('POST', '/api/v1/analysis', req);
  }

  async listAnalyses(): Promise<AnalysisListResponse> {
    return this.request('GET', '/api/v1/analysis');
  }

  async getAnalysis(id: number): Promise<AnalysisResponse> {
    return this.request('GET', `/api/v1/analysis/${id}`);
  }

  async applyActions(id: number, req: ApplyActionsRequest): Promise<MessageResponse> {
    return this.request('POST', `/api/v1/analysis/${id}/apply`, req);
  }

  async getSenderGroups(id: number, category?: string): Promise<SenderGroupSummary[]> {
    const params: Record<string, string> = {};
    if (category) {
      params.category = category;
    }
    return this.request('GET', `/api/v1/analysis/${id}/senders`, undefined, Object.keys(params).length ? params : undefined);
  }

  async deleteAnalysis(id: number): Promise<MessageResponse> {
    return this.request('DELETE', `/api/v1/analysis/${id}`);
  }
}

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
export const apiClient = new TidyInboxClient(API_BASE);
