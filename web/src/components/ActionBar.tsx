import type { ActionType } from '../api/types';

interface ActionBarProps {
  scope: string;
  onAction: (action: ActionType) => void;
  disabled?: boolean;
  canUndo?: boolean;
}

const ACTIONS: { key: string; action: ActionType; label: string; tooltip: string }[] = [
  { key: 'k', action: 'keep', label: '[k] keep', tooltip: 'mark as reviewed, no gmail changes' },
  { key: 'm', action: 'mark_read', label: '[m] mark read', tooltip: 'remove unread label' },
  { key: 'v', action: 'move_to_category', label: '[v] move', tooltip: 'apply category label in gmail' },
  { key: 's', action: 'mark_spam', label: '[s] spam', tooltip: 'move to spam, remove from inbox' },
  { key: 'u', action: 'unsubscribe', label: '[u] unsub', tooltip: 'attempt unsubscribe via rfc 8058' },
];

export function ActionBar({ scope, onAction, disabled, canUndo }: ActionBarProps) {
  return (
    <div
      className="flex-between"
      style={{
        padding: '12px 16px',
        borderTop: 'var(--border)',
        background: 'var(--color-bg)',
        position: 'sticky',
        bottom: 0,
      }}
    >
      <span className="muted">{scope}</span>
      <div className="flex gap-8">
        {ACTIONS.map(a => (
          <button
            key={a.action}
            title={a.tooltip}
            onClick={() => onAction(a.action)}
            disabled={disabled}
          >
            {a.label}
          </button>
        ))}
        <button
          title="undo last action"
          onClick={() => onAction('undo')}
          disabled={disabled || !canUndo}
        >
          [z] undo
        </button>
      </div>
    </div>
  );
}
