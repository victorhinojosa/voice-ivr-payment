import { useEffect, useState } from 'react';
import { X } from 'lucide-react';
import { Button } from './ui/button';

export function LiveCallDialog({ open, editing, onClose, onSave, error }) {
  const [draft, setDraft] = useState({ name: '', amountOwed: '' });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    setDraft(editing
      ? { name: editing.name, amountOwed: String(editing.amount_owed) }
      : { name: '', amountOwed: '' });
  }, [open, editing]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;

  const inputClass = 'w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground shadow-sm outline-none transition-colors placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/30';
  const labelClass = 'mb-1.5 block text-sm font-medium text-foreground';
  const canSave = draft.name.trim() && draft.amountOwed;

  const submit = async (e) => {
    e.preventDefault();
    if (!canSave) return;
    setSaving(true);
    await onSave({ name: draft.name.trim(), amount_owed: parseFloat(draft.amountOwed) || 0 });
    setSaving(false);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center p-0 sm:items-center sm:p-4">
      <button type="button" aria-label="Close dialog" onClick={onClose} className="absolute inset-0 bg-foreground/40 backdrop-blur-sm" />
      <div role="dialog" aria-modal="true" className="relative w-full max-w-md rounded-t-2xl border border-border bg-card shadow-xl sm:rounded-2xl">
        <div className="flex items-center justify-between border-b border-border px-5 py-4">
          <div>
            <h2 className="text-base font-semibold text-foreground">{editing ? 'Edit customer' : 'New customer'}</h2>
            <p className="text-xs text-muted-foreground">
              {editing ? 'Update the account details below.' : 'Add an account to the calling queue.'}
            </p>
          </div>
          <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close"><X className="size-4" /></Button>
        </div>

        <form onSubmit={submit} className="flex flex-col gap-4 px-5 py-5">
          <div>
            <label className={labelClass} htmlFor="cust-name">Full name</label>
            <input id="cust-name" className={inputClass} placeholder="Jane Doe"
              value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
          </div>
          <div>
            <label className={labelClass} htmlFor="cust-amount">Amount owed</label>
            <input id="cust-amount" type="number" min="0" step="0.01" className={inputClass} placeholder="0.00"
              value={draft.amountOwed} onChange={(e) => setDraft({ ...draft, amountOwed: e.target.value })} />
          </div>
          {!editing && (
            <p className="text-xs text-muted-foreground">A phone number will be assigned automatically.</p>
          )}
          {error && <p className="text-xs text-destructive">{error}</p>}

          <div className="mt-1 flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={onClose} disabled={saving}>Cancel</Button>
            <Button type="submit" disabled={!canSave || saving}>
              {saving ? 'Saving…' : editing ? 'Save changes' : 'Add customer'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}