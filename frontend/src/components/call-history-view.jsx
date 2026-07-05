import { Fragment, useState } from 'react';
import { PhoneCall, CheckCircle2, XCircle, MinusCircle, ChevronDown } from 'lucide-react';
import { Badge } from './ui/badge';
import { StatCard } from './stat-card';
import { formatCurrency, formatDate, formatDuration, OUTCOME_META } from '../lib/utils';
import { cn } from '../lib/utils';

function parseTranscript(raw) {
    if (!raw) return null;
    try {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) return parsed;
    } catch {
      return null;
    }
    return null;
  }

export function CallHistoryView({ calls }) {
  const [expanded, setExpanded] = useState(null);

  const total = calls.length;
  const promises = calls.filter((c) => c.outcome === 'promise_made').length;
  const refused = calls.filter((c) => c.outcome === 'refused').length;
  const noCommit = calls.filter((c) => c.outcome === 'no_commitment').length;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard label="Total calls" value={total} icon={PhoneCall} tone="neutral" />
        <StatCard label="Promises made" value={promises} icon={CheckCircle2} tone="success" />
        <StatCard label="No commitment" value={noCommit} icon={MinusCircle} tone="muted" />
        <StatCard label="Refused" value={refused} icon={XCircle} tone="destructive" />
      </div>

      <div className="rounded-xl border border-border bg-card shadow-sm">
        <div className="border-b border-border p-4">
          <h2 className="text-base font-semibold text-foreground">Call history</h2>
          <p className="text-sm text-muted-foreground">Every autonomous call, with full transcripts</p>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full min-w-[820px] text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs font-semibold tracking-wide text-muted-foreground uppercase">
                <th className="px-4 py-3">Customer</th>
                <th className="px-4 py-3">Date</th>
                <th className="px-4 py-3">Duration</th>
                <th className="px-4 py-3">Outcome</th>
                <th className="px-4 py-3">Promise date</th>
                <th className="px-4 py-3">Amount</th>
                <th className="px-4 py-3 text-right">Transcript</th>
              </tr>
            </thead>
            <tbody>
              {calls.map((call) => {
                const meta = OUTCOME_META[call.outcome] || { label: call.outcome || call.status || '—', tone: 'muted' };
                const isOpen = expanded === call.id;
                return (
                  <Fragment key={call.id}>
                    <tr className={cn('border-b border-border transition-colors hover:bg-muted/40', isOpen && 'bg-muted/40')}>
                      <td className="px-4 py-3">
                        <div className="font-medium text-foreground">{call.customer_name}</div>
                        <div className="font-mono text-xs text-muted-foreground">{call.phone_number}</div>
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">{formatDate(call.initiated_at)}</td>
                      <td className="px-4 py-3 text-muted-foreground tabular-nums">{formatDuration(call.duration_seconds)}</td>
                      <td className="px-4 py-3"><Badge tone={meta.tone}>{meta.label}</Badge></td>
                      <td className="px-4 py-3 text-muted-foreground tabular-nums">{call.promise_date || '—'}</td>
                      <td className="px-4 py-3 font-medium text-foreground tabular-nums">{formatCurrency(call.promise_amount)}</td>
                      <td className="px-4 py-3">
                        <div className="flex justify-end">
                          <button
                            type="button"
                            onClick={() => setExpanded(isOpen ? null : call.id)}
                            aria-expanded={isOpen}
                            className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-primary transition-colors hover:bg-primary/10"
                          >
                            {isOpen ? 'Hide' : 'View'}
                            <ChevronDown className={cn('size-3.5 transition-transform', isOpen && 'rotate-180')} />
                          </button>
                        </div>
                      </td>
                    </tr>
                    {isOpen ? (
                        <tr>
                            <td colSpan={7} className="bg-muted/30 px-4 py-4">
                            <div className="mx-auto max-w-2xl space-y-2">
                                <p className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">Transcript</p>
                                {(() => {
                                const parsedTurns = parseTranscript(call.transcript);
                                if (parsedTurns) {
                                    return parsedTurns.map((t, i) => (
                                    <p key={i} className="text-sm text-foreground">
                                        <span className="font-medium text-muted-foreground">
                                        {t.role === 'agent' ? 'Agent: ' : 'Customer: '}
                                        </span>
                                        {t.text}
                                    </p>
                                    ));
                                }
                                return (
                                    <p className="text-sm text-foreground whitespace-pre-wrap">
                                    {call.transcript || 'No transcript recorded.'}
                                    </p>
                                );
                                })()}
                            </div>
                            </td>
                        </tr>
                        ) : null}
                  </Fragment>
                );
              })}
              {calls.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center text-sm text-muted-foreground">
                    No calls yet. Start a call from the Customers tab.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}