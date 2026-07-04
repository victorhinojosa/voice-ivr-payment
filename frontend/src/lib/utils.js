import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs) {
  return twMerge(clsx(inputs));
}

export const OUTCOME_META = {
  promise_made:  { label: 'Promise Made',  tone: 'success' },
  refused:       { label: 'Refused',       tone: 'destructive' },
  no_commitment: { label: 'No Commitment', tone: 'muted' },
  initiated:     { label: 'Initiated',     tone: 'primary' },
  no_answer:     { label: 'No Answer',     tone: 'warning' },
};

export function formatDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('en-US', {
    month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

export function formatDuration(seconds) {
  if (seconds == null) return '—';
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

export function formatCurrency(amount) {
  if (amount == null) return '—';
  return `$${parseFloat(amount).toFixed(2)}`;
}

export function generateRandomPhone() {
  const digits = Array.from({ length: 10 }, () => Math.floor(Math.random() * 10)).join('');
  return `+52${digits}`;
}