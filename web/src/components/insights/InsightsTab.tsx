import { useMemo } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  PieChart, Pie, Cell, Legend,
  ResponsiveContainer,
} from 'recharts';
import type { ClassifiedEmail } from '../../api/types';
import { actionDisplay } from '../../utils/actionDisplay';
import { StatCard } from './StatCard';
import './insights.css';

interface InsightsTabProps {
  emails: ClassifiedEmail[];
  isInboxScan: boolean;
  onCategoryClick: (category: string) => void;
}

const CHART_STYLE = {
  fontFamily: "'IBM Plex Mono', monospace",
  fontSize: 12,
} as const;

const COLORS = {
  text: '#1a1a1a',
  muted: '#777777',
  bg: '#f8f7f4',
  timeline: '#a8b5c8',
  sender: '#8a9bae',
  keep: '#999999',
  read: '#7a9cc6',
  moved: '#7aab7a',
  spam: '#c47a7a',
  unsub: '#c47a7a',
} as const;

const CATEGORY_PALETTE = [
  '#8a9bae', '#a8b5c8', '#7aab7a', '#c4a87a', '#c47a7a',
  '#9a8aae', '#7aabb5', '#b5a88a', '#ae8a9b', '#8aae9b',
];

const ACTION_COLORS: Record<string, string> = {
  keep: COLORS.keep,
  mark_read: COLORS.read,
  move_to_category: COLORS.moved,
  mark_spam: COLORS.spam,
  unsubscribe: COLORS.unsub,
  confidence: COLORS.sender,
};

function formatDate(dateStr: string): string {
  const d = new Date(dateStr);
  const months = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'];
  return `${months[d.getMonth()]} ${String(d.getDate()).padStart(2, '0')}`;
}

function toDateKey(dateStr: string): string {
  const d = new Date(dateStr);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

export function InsightsTab({ emails, isInboxScan, onCategoryClick }: InsightsTabProps) {
  const stats = useMemo(() => {
    const categories = new Set(emails.map(e => e.category).filter(Boolean));
    const domains = new Set(emails.map(e => e.sender_domain).filter(Boolean));
    const confidences = emails.map(e => e.confidence).filter((c): c is number => c != null);
    const avgConfidence = confidences.length > 0
      ? Math.round((confidences.reduce((a, b) => a + b, 0) / confidences.length) * 100)
      : 0;
    const unsubCount = emails.filter(e => e.has_unsubscribe).length;
    return {
      total: emails.length,
      categories: categories.size,
      senders: domains.size,
      avgConfidence,
      unsubCount,
    };
  }, [emails]);

  const categoryData = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const e of emails) {
      const cat = e.category || 'unknown';
      counts[cat] = (counts[cat] || 0) + 1;
    }
    return Object.entries(counts)
      .map(([name, count]) => ({ name, count }))
      .sort((a, b) => b.count - a.count);
  }, [emails]);

  const senderData = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const e of emails) {
      const domain = e.sender_domain || 'unknown';
      counts[domain] = (counts[domain] || 0) + 1;
    }
    return Object.entries(counts)
      .map(([domain, count]) => ({ domain, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 10);
  }, [emails]);

  const timelineData = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const e of emails) {
      if (!e.received_at) continue;
      const key = toDateKey(e.received_at);
      counts[key] = (counts[key] || 0) + 1;
    }
    return Object.entries(counts)
      .map(([dateKey, count]) => ({ dateKey, date: formatDate(dateKey), count }))
      .sort((a, b) => a.dateKey.localeCompare(b.dateKey))
      .slice(-14);
  }, [emails]);

  const actionData = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const e of emails) {
      if (!e.action_taken) continue;
      counts[e.action_taken] = (counts[e.action_taken] || 0) + 1;
    }
    return Object.entries(counts).map(([action, count]) => ({
      name: actionDisplay(action).label,
      count,
      color: ACTION_COLORS[action] || COLORS.muted,
    }));
  }, [emails]);

  const confidenceData = useMemo(() => {
    const buckets = [
      { range: '0–0.2', min: 0, max: 0.2, count: 0 },
      { range: '0.2–0.4', min: 0.2, max: 0.4, count: 0 },
      { range: '0.4–0.6', min: 0.4, max: 0.6, count: 0 },
      { range: '0.6–0.8', min: 0.6, max: 0.8, count: 0 },
      { range: '0.8–1.0', min: 0.8, max: 1.01, count: 0 },
    ];
    for (const e of emails) {
      if (e.confidence == null) continue;
      for (const b of buckets) {
        if (e.confidence >= b.min && e.confidence < b.max) {
          b.count++;
          break;
        }
      }
    }
    return buckets.map(({ range, count }) => ({ range, count }));
  }, [emails]);

  if (emails.length === 0) {
    return <div className="empty-state">no emails to analyze</div>;
  }

  const hasActions = actionData.length > 0;
  const hasConfidence = !isInboxScan && emails.some(e => e.confidence != null);

  return (
    <div>
      <div className="insights-stats">
        <StatCard label="total emails" value={stats.total} />
        <StatCard label="categories" value={stats.categories} />
        <StatCard label="senders" value={stats.senders} />
        {!isInboxScan && <StatCard label="avg confidence" value={`${stats.avgConfidence}%`} />}
        <StatCard label="unsub opportunities" value={stats.unsubCount} />
      </div>

      <div className="insights-chart">
        <div className="insights-chart-title">emails by category</div>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={categoryData} style={CHART_STYLE}>
            <CartesianGrid strokeDasharray="3 3" stroke={COLORS.muted} opacity={0.3} />
            <XAxis dataKey="name" tick={{ fill: COLORS.text, fontSize: 12 }} />
            <YAxis tick={{ fill: COLORS.text, fontSize: 12 }} allowDecimals={false} />
            <Tooltip
              contentStyle={{ border: `1px solid ${COLORS.text}`, borderRadius: 0, fontFamily: CHART_STYLE.fontFamily, fontSize: 12, background: COLORS.bg }}
            />
            <Bar
              dataKey="count"
              radius={0}
              cursor="pointer"
              onClick={(data: { name: string }) => onCategoryClick(data.name)}
            >
              {categoryData.map((_, i) => (
                <Cell key={i} fill={CATEGORY_PALETTE[i % CATEGORY_PALETTE.length]} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {timelineData.length > 1 && (
        <div className="insights-chart">
          <div className="insights-chart-title">email volume (last 14 days)</div>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={timelineData} style={CHART_STYLE}>
              <CartesianGrid strokeDasharray="3 3" stroke={COLORS.muted} opacity={0.3} />
              <XAxis dataKey="date" tick={{ fill: COLORS.text, fontSize: 12 }} />
              <YAxis tick={{ fill: COLORS.text, fontSize: 12 }} allowDecimals={false} />
              <Tooltip
                contentStyle={{ border: `1px solid ${COLORS.text}`, borderRadius: 0, fontFamily: CHART_STYLE.fontFamily, fontSize: 12, background: COLORS.bg }}
              />
              <Bar dataKey="count" fill={COLORS.timeline} radius={0} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      <div className="insights-chart">
        <div className="insights-chart-title">top 10 senders</div>
        <ResponsiveContainer width="100%" height={Math.max(200, senderData.length * 36)}>
          <BarChart data={senderData} layout="vertical" style={CHART_STYLE}>
            <CartesianGrid strokeDasharray="3 3" stroke={COLORS.muted} opacity={0.3} />
            <XAxis type="number" tick={{ fill: COLORS.text, fontSize: 12 }} allowDecimals={false} />
            <YAxis type="category" dataKey="domain" tick={{ fill: COLORS.text, fontSize: 12 }} width={150} />
            <Tooltip
              contentStyle={{ border: `1px solid ${COLORS.text}`, borderRadius: 0, fontFamily: CHART_STYLE.fontFamily, fontSize: 12, background: COLORS.bg }}
            />
            <Bar dataKey="count" fill={COLORS.sender} radius={0} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {(hasActions || hasConfidence) && (
        <div className="insights-columns">
          {hasActions && (
            <div className="insights-chart">
              <div className="insights-chart-title">action breakdown</div>
              <ResponsiveContainer width="100%" height={280}>
                <PieChart style={CHART_STYLE}>
                  <Pie
                    data={actionData}
                    dataKey="count"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    outerRadius={90}
                    strokeWidth={1}
                    stroke={COLORS.text}
                  >
                    {actionData.map((entry, i) => (
                      <Cell key={i} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{ border: `1px solid ${COLORS.text}`, borderRadius: 0, fontFamily: CHART_STYLE.fontFamily, fontSize: 12, background: COLORS.bg }}
                  />
                  <Legend
                    formatter={(value: string) => <span style={{ color: COLORS.text, fontSize: 12 }}>{value}</span>}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
          )}

          {hasConfidence && (
            <div className="insights-chart">
              <div className="insights-chart-title">confidence distribution</div>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={confidenceData} style={CHART_STYLE}>
                  <CartesianGrid strokeDasharray="3 3" stroke={COLORS.muted} opacity={0.3} />
                  <XAxis dataKey="range" tick={{ fill: COLORS.text, fontSize: 12 }} />
                  <YAxis tick={{ fill: COLORS.text, fontSize: 12 }} allowDecimals={false} />
                  <Tooltip
                    contentStyle={{ border: `1px solid ${COLORS.text}`, borderRadius: 0, fontFamily: CHART_STYLE.fontFamily, fontSize: 12, background: COLORS.bg }}
                  />
                  <Bar dataKey="count" fill={COLORS.sender} radius={0} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
