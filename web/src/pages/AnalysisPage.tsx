import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { apiClient } from '../api/client';
import type { ActionType, AnalysisResponse, ClassifiedEmail, SenderGroupSummary } from '../api/types';
import { ActionBar } from '../components/ActionBar';
import { AnalysisProgress } from '../components/AnalysisProgress';
import { EmailDetailModal } from '../components/EmailDetailModal';
import { HoverActions } from '../components/HoverActions';
import { InsightsTab } from '../components/insights/InsightsTab';
import { usePolling } from '../hooks/usePolling';
import { actionDisplay } from '../utils/actionDisplay';

interface UndoEntry {
  action: ActionType;
  emailIds: number[];
}

type Tab = 'categories' | 'emails' | 'insights';

export function AnalysisPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const analysisId = Number(id);

  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [senders, setSenders] = useState<SenderGroupSummary[]>([]);
  const [activeTab, setActiveTab] = useState<Tab>('categories');
  const [filterCategory, setFilterCategory] = useState<string | null>(null);
  const [filterSender, setFilterSender] = useState<string | null>(null);
  const [groupBySender, setGroupBySender] = useState(false);
  const [detailEmail, setDetailEmail] = useState<ClassifiedEmail | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [loadingIds, setLoadingIds] = useState<Set<number | string>>(new Set());
  const [actionError, setActionError] = useState<string | null>(null);
  const [undoStack, setUndoStack] = useState<UndoEntry[]>([]);
  const [insightIndex, setInsightIndex] = useState(0);

  // Selection state
  const [selectedEmails, setSelectedEmails] = useState<Set<number>>(new Set());
  const [selectedCategories, setSelectedCategories] = useState<Set<string>>(new Set());
  const [selectedSenders, setSelectedSenders] = useState<Set<string>>(new Set());

  const isPolling = analysis != null && (analysis.status === 'pending' || analysis.status === 'processing');

  const fetchAnalysis = useCallback(async () => {
    try {
      const a = await apiClient.getAnalysis(analysisId);
      setAnalysis(a);
    } catch {
      navigate('/dashboard');
    }
  }, [analysisId, navigate]);

  const fetchSenders = useCallback(async () => {
    try {
      const s = await apiClient.getSenderGroups(analysisId, filterCategory ?? undefined);
      setSenders(s);
    } catch {
      // ignore
    }
  }, [analysisId, filterCategory]);

  useEffect(() => {
    fetchAnalysis();
  }, [fetchAnalysis]);

  useEffect(() => {
    if (activeTab === 'emails' && groupBySender) {
      fetchSenders();
    }
  }, [activeTab, groupBySender, fetchSenders]);

  usePolling(fetchAnalysis, 2000, isPolling);

  const isInboxScan = analysis?.analysis_type === 'inbox_scan';
  const emails = analysis?.classified_emails ?? [];

  const filteredEmails = useMemo(() => {
    let result = emails;
    if (filterCategory) {
      result = result.filter(e => e.category === filterCategory);
    }
    if (filterSender) {
      result = result.filter(e => e.sender_domain === filterSender);
    }
    return result;
  }, [emails, filterCategory, filterSender]);

  // Clear selection when tab/filter changes
  useEffect(() => {
    setSelectedEmails(new Set());
    setSelectedCategories(new Set());
    setSelectedSenders(new Set());
  }, [activeTab, filterCategory, filterSender, groupBySender]);

  const handleTabClick = (tab: Tab) => {
    setActiveTab(tab);
    setInsightIndex(prev => prev + 1);
    if (tab === 'categories') {
      setFilterCategory(null);
      setFilterSender(null);
      setGroupBySender(false);
    }
  };

  const handleCategoryClick = (category: string) => {
    setFilterCategory(category);
    setFilterSender(null);
    setGroupBySender(false);
    setActiveTab('emails');
    setInsightIndex(prev => prev + 1);
  };

  const handleSenderClick = (domain: string) => {
    setFilterSender(domain);
    setGroupBySender(false);
    setInsightIndex(prev => prev + 1);
  };

  const handleToggleGroupBySender = () => {
    setInsightIndex(prev => prev + 1);
    if (groupBySender) {
      setGroupBySender(false);
    } else {
      setFilterSender(null);
      setGroupBySender(true);
    }
  };

  const resolveEmailIds = useCallback((
    emailIds?: number[],
    overrides?: { category?: string; sender_domain?: string },
  ): number[] => {
    if (emailIds) return emailIds;
    const cat = overrides?.category ?? filterCategory;
    const sender = overrides?.sender_domain ?? filterSender;
    let result = emails;
    if (cat) result = result.filter(e => e.category === cat);
    if (sender) result = result.filter(e => e.sender_domain === sender);
    return result.map(e => e.id);
  }, [emails, filterCategory, filterSender]);

  const handleAction = useCallback(async (
    action: ActionType,
    emailIds?: number[],
    overrides?: { category?: string; sender_domain?: string },
  ) => {
    setActionLoading(true);
    setActionError(null);
    try {
      if (action === 'undo') {
        setUndoStack(prev => {
          const entry = prev[prev.length - 1];
          if (entry) {
            setLoadingIds(new Set(entry.emailIds));

            apiClient.applyActions(analysisId, {
              action: 'undo',
              email_ids: entry.emailIds,
            }).then(() => { fetchAnalysis(); setLoadingIds(new Set()); });
          }
          return prev.slice(0, -1);
        });
        return;
      }

      // Resolve which rows are affected — use category/sender strings or email IDs
      const affectedRowIds: (number | string)[] = [];
      if (overrides?.category) {
        affectedRowIds.push(overrides.category);
      } else if (overrides?.sender_domain) {
        affectedRowIds.push(overrides.sender_domain);
      } else if (emailIds) {
        affectedRowIds.push(...emailIds);
      } else if (activeTab === 'categories' && selectedCategories.size > 0) {
        affectedRowIds.push(...selectedCategories);
      } else if (activeTab === 'emails' && groupBySender && selectedSenders.size > 0) {
        affectedRowIds.push(...selectedSenders);
      } else if (activeTab === 'emails' && selectedEmails.size > 0) {
        affectedRowIds.push(...selectedEmails);
      } else if (filterCategory) {
        affectedRowIds.push(filterCategory);
      }
      setLoadingIds(new Set(affectedRowIds));

      const resolvedIds = resolveEmailIds(emailIds, overrides);

      await apiClient.applyActions(analysisId, {
        action,
        category: overrides?.category ?? (!emailIds && filterCategory ? filterCategory : undefined),
        sender_domain: overrides?.sender_domain ?? (!emailIds && filterSender ? filterSender : undefined),
        email_ids: emailIds,
      });

      if (resolvedIds.length > 0) {
        setUndoStack(prev => [...prev, { action, emailIds: resolvedIds }]);
      }

      // Clear selection after action
      setSelectedEmails(new Set());
      setSelectedCategories(new Set());
      setSelectedSenders(new Set());

      await fetchAnalysis();
      if (groupBySender) {
        await fetchSenders();
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'action failed';
      setActionError(message);
    } finally {
      setActionLoading(false);
      setLoadingIds(new Set());
    }
  }, [analysisId, resolveEmailIds, filterCategory, filterSender, groupBySender, fetchAnalysis, fetchSenders]);

  const handleSelectionAction = useCallback(async (action: ActionType) => {
    if (action === 'undo') {
      handleAction('undo');
      return;
    }

    if (activeTab === 'categories' && selectedCategories.size > 0) {
      // Apply to all selected categories sequentially
      for (const cat of selectedCategories) {
        await handleAction(action, undefined, { category: cat });
      }
    } else if (activeTab === 'emails' && groupBySender && selectedSenders.size > 0) {
      for (const sender of selectedSenders) {
        await handleAction(action, undefined, { sender_domain: sender });
      }
    } else if (activeTab === 'emails' && selectedEmails.size > 0) {
      await handleAction(action, [...selectedEmails]);
    } else {
      await handleAction(action);
    }
  }, [activeTab, selectedCategories, selectedSenders, selectedEmails, groupBySender, handleAction]);

  const handleModalAction = async (action: ActionType, emailId: number) => {
    await handleAction(action, [emailId]);
    const updated = await apiClient.getAnalysis(analysisId);
    setAnalysis(updated);
    const updatedEmail = updated.classified_emails?.find(e => e.id === emailId);
    if (updatedEmail) {
      setDetailEmail(updatedEmail);
    }
  };

  // Stable ref for keyboard handler to avoid stale closures
  const handleSelectionActionRef = useRef(handleSelectionAction);
  handleSelectionActionRef.current = handleSelectionAction;
  const handleToggleRef = useRef(handleToggleGroupBySender);
  handleToggleRef.current = handleToggleGroupBySender;
  const fetchAnalysisRef = useRef(fetchAnalysis);
  fetchAnalysisRef.current = fetchAnalysis;

  useEffect(() => {
    if (detailEmail) return;
    const handler = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement).tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
      const actionMap: Record<string, ActionType> = {
        k: 'keep', m: 'mark_read', v: 'move_to_category', s: 'mark_spam', u: 'unsubscribe', z: 'undo',
      };
      if (actionMap[e.key]) {
        handleSelectionActionRef.current(actionMap[e.key]);
      } else if (e.key === 'Escape') {
        if (filterSender) {
          setFilterSender(null);
        } else if (groupBySender) {
          setGroupBySender(false);
        } else if (filterCategory) {
          setFilterCategory(null);
          setActiveTab('categories');
        } else {
          navigate('/dashboard');
        }
      } else if (e.key === 'r') {
        fetchAnalysisRef.current();
      } else if (e.key === 'g' && activeTab === 'emails') {
        handleToggleRef.current();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [detailEmail, filterSender, filterCategory, groupBySender, activeTab, navigate]);

  if (!analysis) {
    return <div className="empty-state">loading...</div>;
  }

  const hasSelection = selectedEmails.size > 0 || selectedCategories.size > 0 || selectedSenders.size > 0;
  const selectionCount = selectedEmails.size || selectedCategories.size || selectedSenders.size;

  const activeFilters: string[] = [];
  if (filterCategory) activeFilters.push(`category: ${filterCategory}`);
  if (filterSender) activeFilters.push(`sender: ${filterSender}`);

  const actionScope = hasSelection
    ? `${selectionCount} selected`
    : activeFilters.length > 0
      ? activeFilters.join(' + ')
      : 'all emails';

  return (
    <div>
      <div className="animate-in stagger-1 flex-between mb-24">
        <div className="flex gap-16" style={{ alignItems: 'center' }}>
          <span style={{ fontWeight: 600, fontSize: 18 }}>#{analysis.id}</span>
          <span className="badge">{isInboxScan ? 'scan' : 'ai'}</span>
          <span className={`badge ${analysis.status === 'completed' ? 'completed' : analysis.status === 'error' ? 'error' : 'processing'}`}>
            {analysis.status}
          </span>
          <span className="muted">{analysis.unread_only ? 'unread' : 'all'}</span>
        </div>
        <button onClick={() => navigate('/dashboard')}>← dashboard</button>
      </div>

      {isPolling && (
        <div className="animate-in stagger-2">
          <AnalysisProgress
            processed={analysis.processed_emails ?? 0}
            total={analysis.total_emails ?? 0}
          />
          {analysis.use_batch && (
            <div className="muted" style={{ fontSize: 12, marginTop: 8, lineHeight: 1.5, padding: '8px 12px', border: '1px solid rgba(0,0,0,0.15)', background: 'rgba(0,0,0,0.03)' }}>
              using background batch processing for {(analysis.total_emails ?? 0).toLocaleString()} emails.
              this is 50% cheaper but takes longer (typically under 1 hour). results will appear when the batch completes.
            </div>
          )}
        </div>
      )}

      {analysis.status === 'error' && (
        <div className="section error-text animate-in stagger-2">
          {analysis.error_message || 'analysis failed'}
        </div>
      )}

      {analysis.ai_insights && analysis.ai_insights.length > 0 && (
        <div className="insight-bar" key={insightIndex}>
          {analysis.ai_insights[insightIndex % analysis.ai_insights.length]}
        </div>
      )}

      <div className="animate-in stagger-3">
        <div className="tab-bar">
          {(['categories', 'emails', 'insights'] as Tab[]).map(tab => (
            <div
              key={tab}
              className={`tab ${activeTab === tab ? 'active' : ''}`}
              onClick={() => handleTabClick(tab)}
            >
              {tab}
            </div>
          ))}
        </div>

        <div>
          {activeTab === 'categories' && (
            <SummaryTab
              summary={analysis.summary ?? []}
              emails={emails}
              isInboxScan={isInboxScan}
              selected={selectedCategories}
              onToggleSelect={(cat) => setSelectedCategories(prev => {
                const next = new Set(prev);
                next.has(cat) ? next.delete(cat) : next.add(cat);
                return next;
              })}
              onToggleAll={(all) => setSelectedCategories(all ? new Set((analysis.summary ?? []).map(s => s.category)) : new Set())}

              loadingIds={loadingIds}
              onCategoryClick={handleCategoryClick}
              onRowAction={(action, category) => handleAction(action, undefined, { category })}
            />
          )}

          {activeTab === 'insights' && (
            <InsightsTab emails={emails} isInboxScan={isInboxScan} onCategoryClick={handleCategoryClick} />
          )}

          {activeTab === 'emails' && (
            <>
              <div className="flex-between mb-16">
                <div className="flex gap-8" style={{ flexWrap: 'wrap', alignItems: 'center' }}>
                  {(filterCategory || filterSender || groupBySender) && (
                    <button
                      style={{ fontSize: 12, padding: '4px 12px' }}
                      onClick={() => {
                        if (filterSender) {
                          setFilterSender(null);
                        } else if (groupBySender) {
                          setGroupBySender(false);
                        } else if (filterCategory) {
                          setFilterCategory(null);
                          setActiveTab('categories');
                        }
                      }}
                    >
                      ← back
                    </button>
                  )}
                  {filterCategory && (
                    <span className="badge" style={{ cursor: 'pointer' }} onClick={() => setFilterCategory(null)}>
                      {filterCategory} ×
                    </span>
                  )}
                  {filterSender && (
                    <span className="badge" style={{ cursor: 'pointer' }} onClick={() => setFilterSender(null)}>
                      {filterSender} ×
                    </span>
                  )}
                </div>
                <button
                  className={groupBySender ? 'primary' : ''}
                  onClick={handleToggleGroupBySender}
                  style={{ fontSize: 12, padding: '4px 12px' }}
                >
                  {groupBySender ? 'show all' : 'group by sender'}
                </button>
              </div>

              {groupBySender ? (
                <SendersView
                  senders={senders}
                  emails={filteredEmails}
                  selected={selectedSenders}
                  onToggleSelect={(domain) => setSelectedSenders(prev => {
                    const next = new Set(prev);
                    next.has(domain) ? next.delete(domain) : next.add(domain);
                    return next;
                  })}
                  onToggleAll={(all) => setSelectedSenders(all ? new Set(senders.map(s => s.sender_domain)) : new Set())}
    
                  loadingIds={loadingIds}
                  onSenderClick={handleSenderClick}
                  onRowAction={(action, senderDomain) => handleAction(action, undefined, { sender_domain: senderDomain })}
                />
              ) : (
                <EmailsTable
                  emails={filteredEmails}
                  showPriority={!isInboxScan}
                  selected={selectedEmails}
                  onToggleSelect={(emailId) => setSelectedEmails(prev => {
                    const next = new Set(prev);
                    next.has(emailId) ? next.delete(emailId) : next.add(emailId);
                    return next;
                  })}
                  onToggleAll={(all) => setSelectedEmails(all ? new Set(filteredEmails.map(e => e.id)) : new Set())}
    
                  loadingIds={loadingIds}
                  onEmailClick={setDetailEmail}
                  onRowAction={(action, emailId) => handleAction(action, [emailId])}
                />
              )}
            </>
          )}
        </div>

        {(activeTab === 'categories' || activeTab === 'emails') && (
          <>
            {actionError && <div className="error-text mb-8">{actionError}</div>}
            <ActionBar scope={actionScope} onAction={handleSelectionAction} disabled={actionLoading} canUndo={undoStack.length > 0} />
          </>
        )}
      </div>

      {detailEmail && (
        <EmailDetailModal
          email={detailEmail}
          onClose={() => setDetailEmail(null)}
          onAction={handleModalAction}
        />
      )}
    </div>
  );
}

function SummaryTab({
  summary,
  emails,
  isInboxScan,
  selected,
  onToggleSelect,
  onToggleAll,

  loadingIds,
  onCategoryClick,
  onRowAction,
}: {
  summary: { category: string; count: number; recommended_actions: string[] }[];
  emails: ClassifiedEmail[];
  isInboxScan: boolean;
  selected: Set<string>;
  onToggleSelect: (category: string) => void;
  onToggleAll: (all: boolean) => void;

  loadingIds: Set<number | string>;
  onCategoryClick: (category: string) => void;
  onRowAction: (action: ActionType, category: string) => void;
}) {
  if (summary.length === 0) {
    return <div className="empty-state">no summary available</div>;
  }

  const actionCountsByCategory = useMemo(() => {
    const counts: Record<string, Record<string, number>> = {};
    for (const email of emails) {
      const cat = email.category || 'primary';
      if (email.action_taken) {
        if (!counts[cat]) counts[cat] = {};
        counts[cat][email.action_taken] = (counts[cat][email.action_taken] || 0) + 1;
      }
    }
    return counts;
  }, [emails]);

  const allSelected = summary.length > 0 && summary.every(s => selected.has(s.category));

  return (
    <table>
      <thead>
        <tr>
          <th className="col-checkbox">
            <input type="checkbox" checked={allSelected} onChange={() => onToggleAll(!allSelected)} />
          </th>
          <th>category</th>
          <th>count</th>
          <th>recommended actions</th>
          <th>actions applied</th>
        </tr>
      </thead>
      <tbody>
        {summary.map(s => {
          const actions = actionCountsByCategory[s.category];
          const isLoading = loadingIds.has(s.category);
          const rowClass = [
            'clickable',
            selected.has(s.category) ? 'row-selected' : '',
            isLoading ? 'row-loading' : '',
          ].filter(Boolean).join(' ');
          return (
            <tr key={s.category} className={rowClass}>
              <td className="col-checkbox" onClick={e => e.stopPropagation()}>
                <input type="checkbox" checked={selected.has(s.category)} onChange={() => onToggleSelect(s.category)} />
              </td>
              <td onClick={() => onCategoryClick(s.category)}>{s.category}</td>
              <td onClick={() => onCategoryClick(s.category)}>{s.count}</td>
              <td onClick={() => onCategoryClick(s.category)}>{isInboxScan ? '\u2014' : (s.recommended_actions.join(', ') || '\u2014')}</td>
              <td className="actions-inline" onClick={() => onCategoryClick(s.category)}>
                {actions
                  ? Object.entries(actions).map(([action, count]) => {
                      const ad = actionDisplay(action);
                      return (
                        <span key={action} className={`badge badge-${ad.cssClass}`}>
                          {ad.label}: {count}
                        </span>
                      );
                    })
                  : <span className="muted">{'\u2014'}</span>
                }
              </td>
              <td className="hover-actions-cell">
                <HoverActions onAction={action => onRowAction(action, s.category)} />
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function EmailsTable({
  emails,
  showPriority = true,
  selected,
  onToggleSelect,
  onToggleAll,

  loadingIds,
  onEmailClick,
  onRowAction,
}: {
  emails: ClassifiedEmail[];
  showPriority?: boolean;
  selected: Set<number>;
  onToggleSelect: (emailId: number) => void;
  onToggleAll: (all: boolean) => void;

  loadingIds: Set<number | string>;
  onEmailClick: (email: ClassifiedEmail) => void;
  onRowAction: (action: ActionType, emailId: number) => void;
}) {
  if (emails.length === 0) {
    return <div className="empty-state">no emails</div>;
  }

  const allSelected = emails.length > 0 && emails.every(e => selected.has(e.id));

  return (
    <table>
      <thead>
        <tr>
          <th className="col-checkbox">
            <input type="checkbox" checked={allSelected} onChange={() => onToggleAll(!allSelected)} />
          </th>
          <th>sender</th>
          <th>subject</th>
          <th>category</th>
          {showPriority && <th>priority</th>}
          <th>action</th>
        </tr>
      </thead>
      <tbody>
        {emails.map(email => {
          const ad = actionDisplay(email.action_taken);
          const isLoading = loadingIds.has(email.id);
          const rowClasses = [
            'clickable',
            ad.cssClass ? `row-acted row-action-${ad.cssClass}` : '',
            selected.has(email.id) ? 'row-selected' : '',
            isLoading ? 'row-loading' : '',
          ].filter(Boolean).join(' ');
          return (
            <tr key={email.id} className={rowClasses}>
              <td className="col-checkbox" onClick={e => e.stopPropagation()}>
                <input type="checkbox" checked={selected.has(email.id)} onChange={() => onToggleSelect(email.id)} />
              </td>
              <td onClick={() => onEmailClick(email)}>{email.sender_domain || email.sender || '\u2014'}</td>
              <td className="col-subject" onClick={() => onEmailClick(email)} style={{ maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {email.subject || '\u2014'}
              </td>
              <td onClick={() => onEmailClick(email)}>{email.category || '\u2014'}</td>
              {showPriority && <td onClick={() => onEmailClick(email)}>{'★'.repeat(email.importance ?? 0)}</td>}
              <td onClick={() => onEmailClick(email)}>
                {ad.cssClass
                  ? <span className={`badge badge-${ad.cssClass}`}>{ad.label}</span>
                  : ad.label}
              </td>
              <td className="hover-actions-cell">
                <HoverActions onAction={action => onRowAction(action, email.id)} />
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function SendersView({
  senders,
  emails,
  selected,
  onToggleSelect,
  onToggleAll,

  loadingIds,
  onSenderClick,
  onRowAction,
}: {
  senders: SenderGroupSummary[];
  emails: ClassifiedEmail[];
  selected: Set<string>;
  onToggleSelect: (domain: string) => void;
  onToggleAll: (all: boolean) => void;

  loadingIds: Set<number | string>;
  onSenderClick: (domain: string) => void;
  onRowAction: (action: ActionType, senderDomain: string) => void;
}) {
  if (senders.length === 0) {
    return <div className="empty-state">no senders</div>;
  }

  const actionCountsBySender = useMemo(() => {
    const counts: Record<string, Record<string, number>> = {};
    for (const email of emails) {
      const domain = email.sender_domain || '';
      if (email.action_taken) {
        if (!counts[domain]) counts[domain] = {};
        counts[domain][email.action_taken] = (counts[domain][email.action_taken] || 0) + 1;
      }
    }
    return counts;
  }, [emails]);

  const allSelected = senders.length > 0 && senders.every(s => selected.has(s.sender_domain));

  return (
    <table>
      <thead>
        <tr>
          <th className="col-checkbox">
            <input type="checkbox" checked={allSelected} onChange={() => onToggleAll(!allSelected)} />
          </th>
          <th>domain</th>
          <th>display name</th>
          <th>count</th>
          <th>unsubscribe</th>
          <th>actions applied</th>
        </tr>
      </thead>
      <tbody>
        {senders.map(s => {
          const actions = actionCountsBySender[s.sender_domain];
          const isLoading = loadingIds.has(s.sender_domain);
          const rowClass = [
            'clickable',
            selected.has(s.sender_domain) ? 'row-selected' : '',
            isLoading ? 'row-loading' : '',
          ].filter(Boolean).join(' ');
          return (
            <tr key={s.sender_domain} className={rowClass}>
              <td className="col-checkbox" onClick={e => e.stopPropagation()}>
                <input type="checkbox" checked={selected.has(s.sender_domain)} onChange={() => onToggleSelect(s.sender_domain)} />
              </td>
              <td onClick={() => onSenderClick(s.sender_domain)}>{s.sender_domain}</td>
              <td onClick={() => onSenderClick(s.sender_domain)}>{s.sender_display}</td>
              <td onClick={() => onSenderClick(s.sender_domain)}>{s.count}</td>
              <td onClick={() => onSenderClick(s.sender_domain)}>{s.has_unsubscribe ? 'yes' : 'no'}</td>
              <td className="actions-inline" onClick={() => onSenderClick(s.sender_domain)}>
                {actions
                  ? Object.entries(actions).map(([action, count]) => {
                      const ad = actionDisplay(action);
                      return (
                        <span key={action} className={`badge badge-${ad.cssClass}`}>
                          {ad.label}: {count}
                        </span>
                      );
                    })
                  : <span className="muted">{'\u2014'}</span>
                }
              </td>
              <td className="hover-actions-cell">
                <HoverActions onAction={action => onRowAction(action, s.sender_domain)} />
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
