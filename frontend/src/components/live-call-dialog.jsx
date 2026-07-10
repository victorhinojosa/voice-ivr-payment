import { PhoneOff, Sparkles } from 'lucide-react';
import { Button } from './ui/button';
import { useState, useEffect } from 'react';
import VoiceSession from '../VoiceSession';
import { cn } from '../lib/utils';

const LANGUAGES = ['English', 'Spanish'];
const DEBT_TYPES = ['credit_card', 'mortgage', 'insurance_premium'];

const DEBT_TYPE_LABELS = {
  credit_card: 'Credit Card',
  mortgage: 'Mortgage',
  insurance_premium: 'Insurance Premium',
};

export function LiveCallDialog({ customer, onClose, companyName = 'Call Center AI' }) {
  const [language, setLanguage] = useState(() => {
    return localStorage.getItem('selected_language') || 'English';
  });

  const [debtType, setDebtType] = useState(() => {
    return localStorage.getItem('selected_debt_type') || 'credit_card';
  });

  const [sessionActive, setSessionActive] = useState(false);

  useEffect(() => {
    localStorage.setItem('selected_language', language);
  }, [language]);

  useEffect(() => {
    localStorage.setItem('selected_debt_type', debtType);
  }, [debtType]);

  if (!customer) return null;

  const initials = customer.name
    .split(' ')
    .map((n) => n[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();

  const handleSessionStart = () => {
    setSessionActive(true);
  };

  const handleSessionComplete = () => {
    setSessionActive(false);
  };

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
          {companyName} agent is handling this call autonomously
        </div>

        {/* Session Config Panel (shown only before call starts) */}
        {!sessionActive && (
          <div className="border-b border-border bg-muted/30 px-5 py-4 space-y-3">
            <div>
              <label className="text-xs font-medium text-muted-foreground block mb-1.5">Language</label>
              <select
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-input bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              >
                {LANGUAGES.map((lang) => (
                  <option key={lang} value={lang}>{lang}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="text-xs font-medium text-muted-foreground block mb-1.5">Debt Type</label>
              <select
                value={debtType}
                onChange={(e) => setDebtType(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-input bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              >
                {DEBT_TYPES.map((type) => (
                  <option key={type} value={type}>{DEBT_TYPE_LABELS[type]}</option>
                ))}
              </select>
            </div>
          </div>
        )}

        <div className="flex-1 overflow-y-auto px-5 py-5">
          <VoiceSession
            customerId={customer.id}
            customerName={customer.name}
            language={language}
            debtType={debtType}
            companyName={companyName}
            onSessionStart={handleSessionStart}
            onSessionComplete={handleSessionComplete}
          />
        </div>

        <div className="border-t border-border px-5 py-4">
          <Button
            variant="destructive"
            className="w-full"
            onClick={onClose}
          >
            <PhoneOff className="size-4" />
            {sessionActive ? 'End Call' : 'Close'}
          </Button>
        </div>
      </div>
    </div>
  );
}