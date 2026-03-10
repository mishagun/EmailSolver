import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '../api/client';
import type { AnalysisResponse, EmailStatsResponse } from '../api/types';

export function DashboardPage() {
  const navigate = useNavigate();
  const [stats, setStats] = useState<EmailStatsResponse | null>(null);
  const [analyses, setAnalyses] = useState<AnalysisResponse[]>([]);
  const [loading, setLoading] = useState(true);

  const [query, setQuery] = useState('is:unread');
  const [maxEmails, setMaxEmails] = useState(100);
  const [autoApply, setAutoApply] = useState(false);
  const [customCategories, setCustomCategories] = useState('');
  const [creating, setCreating] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const [s, a] = await Promise.all([
        apiClient.getEmailStats(),
        apiClient.listAnalyses(),
      ]);
      setStats(s);
      setAnalyses(a.analyses);
    } catch {
      // handled by auth context on 401
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const handleCreate = async (analysisType: 'inbox_scan' | 'ai') => {
    setCreating(true);
    try {
      const cats = analysisType === 'ai' && customCategories.trim()
        ? customCategories.split(',').map(c => c.trim()).filter(Boolean)
        : undefined;
      const analysis = await apiClient.createAnalysis({
        analysis_type: analysisType,
        query,
        max_emails: maxEmails,
        auto_apply: autoApply,
        custom_categories: cats,
      });
      navigate(`/analysis/${analysis.id}`);
    } catch {
      setCreating(false);
    }
  };

  const handleDelete = async (id: number, e: React.MouseEvent) => {
    e.stopPropagation();
    await apiClient.deleteAnalysis(id);
    refresh();
  };

  const statusBadge = (status: string) => {
    const cls = status === 'completed' ? 'completed' : status === 'error' ? 'error' : 'processing';
    return <span className={`badge ${cls}`}>{status}</span>;
  };

  const typeBadge = (analysisType: string) => {
    return <span className="badge">{analysisType === 'inbox_scan' ? 'scan' : 'ai'}</span>;
  };

  const progressText = (a: AnalysisResponse) => {
    if (a.total_emails == null) return '—';
    const processed = a.processed_emails ?? 0;
    return `${processed}/${a.total_emails}`;
  };

  if (loading) {
    return <div className="empty-state">loading...</div>;
  }

  return (
    <div>
      {stats && (
        <div className="animate-in stagger-1 flex gap-24 mb-24">
          <span>unread: {stats.unread_count}</span>
          <span>total: {stats.total_count}</span>
        </div>
      )}

      <div className="animate-in stagger-2 flex gap-24 mb-24" style={{ alignItems: 'stretch' }}>
        <div className="section" style={{ flex: 1, marginBottom: 0 }}>
          <div className="section-title">inbox scan</div>
          <p className="muted mb-8" style={{ fontSize: 13, lineHeight: 1.5 }}>
            fast overview of your inbox. groups emails by gmail's built-in categories
            (primary, promotions, social, etc.) and sender domains. no ai needed.
          </p>
          <p className="muted mb-16" style={{ fontSize: 13, lineHeight: 1.5, opacity: 0.7 }}>
            with auto-apply: spam → marked as spam, promotions → marked as read.
          </p>
          <button
            className="primary"
            disabled={creating}
            onClick={() => handleCreate('inbox_scan')}
          >
            {creating ? 'starting...' : 'start inbox scan'}
          </button>
        </div>
        <div className="section" style={{ flex: 1, marginBottom: 0 }}>
          <div className="section-title">ai analysis</div>
          <p className="muted mb-8" style={{ fontSize: 13, lineHeight: 1.5 }}>
            classifies each email using claude ai. assigns categories, importance (0-5),
            sender type, and confidence scores. includes a verification pass.
          </p>
          <p className="muted mb-8" style={{ fontSize: 13, lineHeight: 1.5, opacity: 0.7 }}>
            base categories: primary, promotions, social, updates, spam, newsletters, receipts.
            ai can also discover new categories from your content.
          </p>
          <p className="muted mb-16" style={{ fontSize: 13, lineHeight: 1.5, opacity: 0.7 }}>
            with auto-apply: ai determines best action per category
            (e.g. newsletters → mark read, spam → mark spam).
          </p>
          <div className="mb-16">
            <div className="field-label">custom categories</div>
            <input
              value={customCategories}
              onChange={e => setCustomCategories(e.target.value)}
              placeholder="comma separated"
              style={{ width: '100%' }}
            />
          </div>
          <button
            className="primary"
            disabled={creating}
            onClick={() => handleCreate('ai')}
          >
            {creating ? 'starting...' : 'start ai analysis'}
          </button>
        </div>
      </div>

      <div className="animate-in stagger-3 section" style={{ marginBottom: 24 }}>
        <div className="section-title">options</div>
        <div className="flex gap-16" style={{ flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <div>
            <div className="field-label">query</div>
            <input
              value={query}
              onChange={e => setQuery(e.target.value)}
              style={{ width: 200 }}
            />
          </div>
          <div>
            <div className="field-label">max emails</div>
            <input
              type="number"
              value={maxEmails}
              onChange={e => setMaxEmails(Number(e.target.value))}
              style={{ width: 100 }}
            />
          </div>
          <div>
            <label>
              <input
                type="checkbox"
                checked={autoApply}
                onChange={e => setAutoApply(e.target.checked)}
              />
              auto-apply actions
            </label>
            <div className="muted" style={{ fontSize: 12, marginTop: 4, lineHeight: 1.4 }}>
              automatically apply recommended actions when analysis completes.
              when off, you review results first and apply actions manually.
            </div>
          </div>
        </div>
      </div>

      <div className="animate-in stagger-4 section">
        <div className="section-title">analyses</div>
        {analyses.length === 0 ? (
          <div className="empty-state">no analyses yet</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>id</th>
                <th>type</th>
                <th>status</th>
                <th>query</th>
                <th>progress</th>
                <th>created</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {analyses.map(a => (
                <tr key={a.id} className="clickable" onClick={() => navigate(`/analysis/${a.id}`)}>
                  <td>#{a.id}</td>
                  <td>{typeBadge(a.analysis_type)}</td>
                  <td>{statusBadge(a.status)}</td>
                  <td>{a.query || '—'}</td>
                  <td>{progressText(a)}</td>
                  <td>{new Date(a.created_at).toLocaleDateString()}</td>
                  <td>
                    <button className="danger" onClick={(e) => handleDelete(a.id, e)}>
                      delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
