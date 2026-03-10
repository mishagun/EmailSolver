import { describe, it, expect } from 'vitest';
import { actionDisplay } from './actionDisplay';

describe('actionDisplay', () => {
  it('returns correct display for each action type', () => {
    // Arrange & Act & Assert
    expect(actionDisplay('keep')).toEqual({ label: 'kept', cssClass: 'keep' });
    expect(actionDisplay('mark_read')).toEqual({ label: 'read', cssClass: 'read' });
    expect(actionDisplay('move_to_category')).toEqual({ label: 'moved', cssClass: 'moved' });
    expect(actionDisplay('mark_spam')).toEqual({ label: 'spam', cssClass: 'spam' });
    expect(actionDisplay('unsubscribe')).toEqual({ label: 'unsub', cssClass: 'unsub' });
  });

  it('returns dash and empty cssClass for null', () => {
    // Arrange & Act & Assert
    expect(actionDisplay(null)).toEqual({ label: '\u2014', cssClass: '' });
  });

  it('returns dash and empty cssClass for unknown action', () => {
    // Arrange & Act & Assert
    expect(actionDisplay('unknown_action')).toEqual({ label: '\u2014', cssClass: '' });
  });
});
