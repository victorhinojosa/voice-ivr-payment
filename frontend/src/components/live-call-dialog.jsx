import { PhoneOff, Sparkles } from 'lucide-react';
import { Button } from './ui/button';
import VoiceSession from '../VoiceSession';

export function LiveCallDialog({ customer, onClose }) {
  if (!customer) return null;

  const initials = customer.name.split(' ').map((n) => n[0]).join('').slice(0, 2).toUpperCase();

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center p-0 sm:items-center sm:p-4">
      <div className="absolute inset-0 bg-foreground/50 backdrop-blur-sm" />
      <div role="dialog" aria-modal="true" aria-label={`Call with ${customer.name}`}
        className="relative flex h-[85vh] w-full max-w-lg flex-col overflow-hidden rounded-t-2xl border border-border bg-card shadow-2xl sm:h-[600px] sm:rounded-2xl">

        <div className="flex items-center gap-3 border-b border-border bg-sidebar px-5 py-4 text-sidebar-foreground">
          <div className="flex size-11 items-center justify-center rounded-full bg-sidebar-primary/20 text-sm font-semibold text-white">
            {initials}
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-semibold text-white">{customer.name}</p>
            <p className="font-mono text-xs text-sidebar-foreground/60">{customer.phone}</p>
          </div>
        </div>

        <div className="flex items-center gap-2 border-b border-border bg-accent px-5 py-2 text-xs font-medium text-accent-foreground">
          <Sparkles className="size-3.5" />
          Call Center AI agent is handling this call autonomously
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-5">
          <VoiceSession customerId={customer.id} customerName={customer.name} />
        </div>

        <div className="border-t border-border px-5 py-4">
          <Button variant="destructive" className="w-full" onClick={onClose}>
            <PhoneOff className="size-4" />
            Close
          </Button>
        </div>
      </div>
    </div>
  );
}