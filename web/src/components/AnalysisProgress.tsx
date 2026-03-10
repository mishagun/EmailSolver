interface AnalysisProgressProps {
  processed: number;
  total: number;
}

export function AnalysisProgress({ processed, total }: AnalysisProgressProps) {
  const pct = total > 0 ? Math.round((processed / total) * 100) : 0;

  return (
    <div style={{ marginBottom: 24 }}>
      <div className="flex-between mb-8">
        <span className="muted">processing emails...</span>
        <span>{processed} / {total} ({pct}%)</span>
      </div>
      <div className="progress-bar">
        <div className="progress-fill" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
