export function formatCurrency(amount: string | number, currency = 'INR'): string {
  const numeric = typeof amount === 'string' ? Number(amount) : amount;
  if (Number.isNaN(numeric)) return `${currency} ${amount}`;
  try {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency,
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(numeric);
  } catch {
    return `${currency} ${numeric.toFixed(2)}`;
  }
}

export function formatDateTime(iso?: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString('en-US', {
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });
}

export function formatDurationMs(ms?: number | null): string {
  if (ms === undefined || ms === null) return '—';
  if (ms < 1000) return `${Math.round(ms)} ms`;
  return `${(ms / 1000).toFixed(2)} s`;
}

export function generateIdempotencyKey(prefix = 'idem'): string {
  const rand = Math.random().toString(36).substring(2, 10);
  return `${prefix}-${Date.now().toString(36)}-${rand}`;
}

export function generateOrderId(): string {
  const rand = Math.floor(100000 + Math.random() * 900000);
  return `ORD-${rand}`;
}

