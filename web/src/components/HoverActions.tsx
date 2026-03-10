import type { ActionType } from '../api/types';

const ACTIONS: { action: ActionType; label: string; tooltip: string }[] = [
  { action: 'keep', label: 'k', tooltip: 'keep — mark as reviewed' },
  { action: 'mark_read', label: 'm', tooltip: 'mark read — remove unread' },
  { action: 'move_to_category', label: 'v', tooltip: 'move — apply category label' },
  { action: 'mark_spam', label: 's', tooltip: 'spam — move to spam' },
  { action: 'unsubscribe', label: 'u', tooltip: 'unsubscribe — attempt unsubscribe' },
];

interface HoverActionsProps {
  onAction: (action: ActionType) => void;
}

export function HoverActions({ onAction }: HoverActionsProps) {
  return (
    <div className="hover-actions">
      {ACTIONS.map(a => (
        <button
          key={a.action}
          title={a.tooltip}
          onClick={e => { e.stopPropagation(); onAction(a.action); }}
        >
          {a.label}
        </button>
      ))}
    </div>
  );
}
