import { useMemo, useState } from 'react';
import { Search, Plus, Phone, Wallet, Users } from 'lucide-react';
import { Button } from './ui/button';
import { StatCard } from './stat-card';
import { formatCurrency } from '../lib/utils';
import { ActionsMenu } from './actions-menu';

export function CustomersView({ customers, onStartCall, onNew, onEdit, onDelete }) {
  const [query, setQuery] = useState('');

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return customers;
    return customers.filter((c) => c.name.toLowerCase().includes(q) || c.phone.toLowerCase().includes(q));
  }, [customers, query]);

  const totalOwed = customers.reduce((sum, c) => sum + parseFloat(c.amount_owed || 0), 0);

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <StatCard label="Portfolio outstanding" value={formatCurrency(totalOwed)}
          hint={`Across ${customers.length} accounts`} icon={Wallet} tone="primary" />
        <StatCard label="Accounts in queue" value={customers.length}
          hint="Ready for outreach" icon={Users} tone="success" />
      </div>

      <div className="rounded-xl border border-border bg-card shadow-sm">
        <div className="flex flex-col gap-3 border-b border-border p-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-base font-semibold text-foreground">Calling queue</h2>
            <p className="text-sm text-muted-foreground">Accounts ready for autonomous outreach</p>
          </div>
          <div className="flex items-center gap-2">
            <div className="relative flex-1 sm:w-64 sm:flex-none">
              <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
              <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search name or phone"
                className="w-full rounded-lg border border-input bg-background py-2 pr-3 pl-9 text-sm text-foreground outline-none transition-colors placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/30" />
            </div>
            <Button onClick={onNew}><Plus className="size-4" />New customer</Button>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full min-w-[560px] text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs font-semibold tracking-wide text-muted-foreground uppercase">
                <th className="px-4 py-3">Customer</th>
                <th className="px-4 py-3">Phone</th>
                <th className="px-4 py-3">Amount owed</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((c) => (
                <tr key={c.id} className="border-b border-border last:border-0 transition-colors hover:bg-muted/40">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <div className="flex size-9 items-center justify-center rounded-full bg-muted text-xs font-semibold text-muted-foreground">
                        {c.name.split(' ').map((n) => n[0]).join('').slice(0, 2).toUpperCase()}
                      </div>
                      <span className="font-medium text-foreground">{c.name}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3 font-mono text-muted-foreground">{c.phone}</td>
                  <td className="px-4 py-3 font-medium text-foreground tabular-nums">{formatCurrency(c.amount_owed)}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-1.5">
                      <Button size="sm" onClick={() => onStartCall(c)}><Phone className="size-3.5" />Start call</Button>
                      <ActionsMenu customer={c} onEdit={onEdit} onDelete={onDelete} />
                    </div>
                  </td>
                </tr>
              ))}
              {filtered.length === 0 ? (
                <tr><td colSpan={4} className="px-4 py-12 text-center text-sm text-muted-foreground">No customers match "{query}".</td></tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}