/**
 * Human-readable "time left" for a due date.
 * - Past due: "Xd overdue"
 * - ≤14 days: "Xd"
 * - >14 days: "Xw"
 */
export function timeLeft(due) {
  if (!due) return '—';
  const target = new Date(`${String(due).slice(0, 10)}T00:00:00`);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const days = Math.round((target - today) / 86400000);
  if (days < 0) return `${-days}d overdue`;
  if (days === 0) return 'Today';
  if (days <= 14) return `${days}d`;
  return `${Math.ceil(days / 7)}w`;
}
