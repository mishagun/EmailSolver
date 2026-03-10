import { useEffect } from 'react';
import type { ActionType, ClassifiedEmail } from '../api/types';
import { actionDisplay } from '../utils/actionDisplay';

interface EmailDetailModalProps {
  email: ClassifiedEmail;
  onClose: () => void;
  onAction: (action: ActionType, emailId: number) => void;
}

export function EmailDetailModal({ email, onClose, onAction }: EmailDetailModalProps) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  const importance = email.importance ?? 0;
  const stars = '★'.repeat(importance) + '☆'.repeat(Math.max(0, 5 - importance));
  const confidence = email.confidence != null ? `${Math.round(email.confidence * 100)}%` : '—';

  return (
    <div className="overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <span style={{ fontWeight: 600, fontSize: 16 }}>email details</span>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>

        <div className="field">
          <div className="field-label">from</div>
          <div className="field-value">{email.sender || '—'}</div>
        </div>

        <div className="field">
          <div className="field-label">domain</div>
          <div className="field-value">{email.sender_domain || '—'}</div>
        </div>

        <div className="field">
          <div className="field-label">subject</div>
          <div className="field-value">{email.subject || '—'}</div>
        </div>

        <div className="field">
          <div className="field-label">category</div>
          <div className="field-value">{email.category || '—'}</div>
        </div>

        <div className="field">
          <div className="field-label">importance</div>
          <div className="field-value stars">{stars}</div>
        </div>

        <div className="field">
          <div className="field-label">sender type</div>
          <div className="field-value">{email.sender_type || '—'}</div>
        </div>

        <div className="field">
          <div className="field-label">confidence</div>
          <div className="field-value">{confidence}</div>
        </div>

        <div className="field">
          <div className="field-label">unsubscribe</div>
          <div className="field-value">{email.has_unsubscribe ? 'yes' : 'no'}</div>
        </div>

        <div className="field">
          <div className="field-label">action taken</div>
          <div className="field-value">
            {(() => {
              const ad = actionDisplay(email.action_taken);
              return ad.cssClass
                ? <span className={`badge badge-${ad.cssClass}`}>{ad.label}</span>
                : <span className="muted">none</span>;
            })()}
          </div>
        </div>

        {email.snippet && (
          <div className="field">
            <div className="field-label">snippet</div>
            <div className="field-value muted" style={{ fontSize: 12 }}>{email.snippet}</div>
          </div>
        )}

        <div className="flex gap-8" style={{ marginTop: 24, flexWrap: 'wrap' }}>
          <button onClick={() => onAction('keep', email.id)}>keep</button>
          <button onClick={() => onAction('mark_read', email.id)}>mark read</button>
          <button onClick={() => onAction('move_to_category', email.id)}>move</button>
          <button onClick={() => onAction('mark_spam', email.id)}>spam</button>
          <button onClick={() => onAction('unsubscribe', email.id)}>unsub</button>
        </div>
      </div>
    </div>
  );
}
