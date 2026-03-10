export function actionDisplay(actionTaken: string | null): { label: string; cssClass: string } {
  switch (actionTaken) {
    case 'keep': return { label: 'kept', cssClass: 'keep' };
    case 'mark_read': return { label: 'read', cssClass: 'read' };
    case 'move_to_category': return { label: 'moved', cssClass: 'moved' };
    case 'mark_spam': return { label: 'spam', cssClass: 'spam' };
    case 'unsubscribe': return { label: 'unsub', cssClass: 'unsub' };
    default: return { label: '\u2014', cssClass: '' };
  }
}
