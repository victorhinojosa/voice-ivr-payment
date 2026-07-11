import React, { useState, useEffect, useCallback } from 'react';
import './App.css';
import { Users, Phone, Info, X } from 'lucide-react';
import { CallHistoryView } from './components/call-history-view';
import { AppSidebar } from './components/app-sidebar';
import { CustomersView } from './components/customers-view';
import { CustomerDialog } from './components/customer-dialog';
import { LiveCallDialog } from './components/live-call-dialog';
import { generateRandomPhone, cn } from './lib/utils';
import { Button } from './components/ui/button';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

// ---------------------------------------------------------------------------
// Company Name Edit Modal
// ---------------------------------------------------------------------------
function CompanyNameEditModal({ open, currentName, onSave, onClose }) {
  const [input, setInput] = useState(currentName);

  useEffect(() => {
    if (open) setInput(currentName);
  }, [open, currentName]);

  const handleSave = () => {
    const trimmed = input.trim();
    if (trimmed) {
      onSave(trimmed);
      onClose();
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button className="absolute inset-0 bg-foreground/40 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full max-w-sm rounded-2xl border border-border bg-card p-6 shadow-xl">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold text-foreground">Edit Company Name</h2>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <X className="size-4" />
          </button>
        </div>

        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Enter company name"
          className="w-full px-3 py-2 mb-4 rounded-lg border border-input bg-background text-foreground placeholder-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary"
          autoFocus
          onKeyDown={(e) => e.key === 'Enter' && handleSave()}
        />

        <div className="flex gap-2 justify-end">
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={handleSave}>Save</Button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Customers Page
// ---------------------------------------------------------------------------
function CustomersPage({ onCountChange, companyName }) {
  const [customers, setCustomers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [formError, setFormError] = useState(null);
  const [callingCustomer, setCallingCustomer] = useState(null);

  const fetchCustomers = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetch(`${API_URL}/api/customers`);
      if (!r.ok) throw new Error();
      const data = await r.json();
      setCustomers(data);
      onCountChange?.(data.length);
      setError(null);
    } catch {
      setError('Failed to load customers.');
    } finally {
      setLoading(false);
    }
  }, [onCountChange]);

  useEffect(() => { fetchCustomers(); }, [fetchCustomers]);

  const handleSave = async (payload) => {
    const isEdit = editing != null;
    const body = isEdit ? payload : { ...payload, phone: generateRandomPhone() };
    const url = isEdit ? `${API_URL}/api/customers/${editing.id}` : `${API_URL}/api/customers`;
    try {
      const r = await fetch(url, {
        method: isEdit ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!r.ok) throw new Error();
      await fetchCustomers();
      setDialogOpen(false);
      setEditing(null);
    } catch {
      setFormError('Failed to save customer.');
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Delete this customer?')) return;
    try {
      const r = await fetch(`${API_URL}/api/customers/${id}`, { method: 'DELETE' });
      if (!r.ok) throw new Error();
      await fetchCustomers();
    } catch {
      setError('Failed to delete customer.');
    }
  };

  if (loading) return <p className="muted center-text">Loading customers…</p>;
  if (error) return <p className="error-text center-text">{error}</p>;

  return (
    <>
      <CustomersView
        customers={customers}
        onStartCall={setCallingCustomer}
        onNew={() => { setEditing(null); setFormError(null); setDialogOpen(true); }}
        onEdit={(c) => { setEditing(c); setFormError(null); setDialogOpen(true); }}
        onDelete={handleDelete}
      />
      <CustomerDialog
        open={dialogOpen}
        editing={editing}
        onClose={() => setDialogOpen(false)}
        onSave={handleSave}
        error={formError}
      />
      {callingCustomer && (
        <LiveCallDialog
          customer={callingCustomer}
          onClose={() => setCallingCustomer(null)}
          companyName={companyName}
        />
      )}
    </>
  );
}

function AboutDemoModal({ open, onClose }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button className="absolute inset-0 bg-foreground/40 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full max-w-md rounded-2xl border border-border bg-card p-6 shadow-xl">
        <h2 className="text-base font-semibold text-foreground mb-2">About this demo</h2>
        <p className="text-sm text-muted-foreground mb-4">
        This is a working demo of an autonomous voice collections agent. Add yourself as a customer and click "Start call" to talk to the AI live, no phone number needed, it runs right in your browser. Before starting, pick a language (English/Spanish) and debt type, the agent adapts its script, terminology, and voice accordingly.
        </p>
        <div className="flex justify-end gap-2">
          <a href="https://github.com/victorhinojosa/voice-ivr-payment" target="_blank" rel="noreferrer"
             className="text-sm text-primary hover:underline self-center">Check code</a>
          <button onClick={onClose} className="rounded-lg bg-muted px-3 py-1.5 text-sm text-foreground">Close</button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// App
// ---------------------------------------------------------------------------
function App() {
  const [calls, setCalls] = useState([]);
  const [callsLoading, setCallsLoading] = useState(true);
  const [callsError, setCallsError] = useState(null);
  const [view, setView] = useState('customers'); // 'customers' | 'calls'
  const [customersCount, setCustomersCount] = useState(0);
  const [aboutOpen, setAboutOpen] = useState(false);
  const [companyName, setCompanyName] = useState('Call Center AI');
  const [editCompanyOpen, setEditCompanyOpen] = useState(false);

  const fetchCalls = useCallback(async () => {
    try {
      const r = await fetch(`${API_URL}/api/calls`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = await r.json();
      setCalls(Array.isArray(data) ? data : []);
      setCallsError(null);
    } catch (err) {
      setCallsError('Failed to load call history.');
    } finally {
      setCallsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCalls();
    const interval = setInterval(fetchCalls, 10000);
    return () => clearInterval(interval);
  }, [fetchCalls]);

  return (
    <div className="flex min-h-screen bg-background">
      <AppSidebar
        companyName={companyName}
        onEditCompany={() => setEditCompanyOpen(true)}
      />
      <CompanyNameEditModal
        open={editCompanyOpen}
        currentName={companyName}
        onSave={setCompanyName}
        onClose={() => setEditCompanyOpen(false)}
      />
      <div className="flex-1 p-6 lg:p-8">

        {/* Header (back to original — no company name here anymore) */}
        <div className="pb-4 mb-6">
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-semibold text-foreground">Collections Dashboard</h1>
            <span className="inline-flex items-center gap-1.5 rounded-full border border-success/30 bg-success/15 px-3 py-1 text-xs font-medium text-success">
              <span className="relative flex size-1.5">
                <span className="absolute inline-flex size-full animate-ping rounded-full bg-success opacity-75" />
                <span className="relative inline-flex size-1.5 rounded-full bg-success" />
              </span>
              Agent online
            </span>
            <button
              onClick={() => setAboutOpen(true)}
              className="text-muted-foreground hover:text-foreground transition-colors"
              aria-label="About this demo"
            >
              <Info className="size-4" />
            </button>
          </div>
          <AboutDemoModal open={aboutOpen} onClose={() => setAboutOpen(false)} />
          <p className="text-sm text-muted-foreground mt-1">
            Promise-to-pay outreach, fully automated
          </p>
        </div>

        {/* Tabs */}
        <div className="flex gap-6 border-b border-border mb-6">
          <button
            onClick={() => setView('customers')}
            className={cn(
              'flex items-center gap-2 pb-3 text-sm font-medium border-b-2 -mb-px transition-colors',
              view === 'customers'
                ? 'border-primary text-foreground'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            )}
          >
            <Users className="size-4" />
            Customers
            <span className="rounded-full bg-muted px-2 py-0.5 text-xs">{customersCount}</span>
          </button>
          <button
            onClick={() => setView('calls')}
            className={cn(
              'flex items-center gap-2 pb-3 text-sm font-medium border-b-2 -mb-px transition-colors',
              view === 'calls'
                ? 'border-primary text-foreground'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            )}
          >
            <Phone className="size-4" />
            Call History
            <span className="rounded-full bg-muted px-2 py-0.5 text-xs">{calls.length}</span>
          </button>
        </div>

        <div className="mx-auto max-w-6xl">
          {view === 'customers' ? (
            <CustomersPage onCountChange={setCustomersCount} companyName={companyName} />
          ) : (
            <>
              {callsLoading ? (
                <p className="muted center-text">Loading calls…</p>
              ) : callsError ? (
                <p className="error-text center-text">{callsError}</p>
              ) : (
                <CallHistoryView calls={calls} />
              )}
            </>
          )}
        </div>
        <footer className="mt-10 border-t border-border pt-6 text-center text-xs text-muted-foreground">
          Check the code on GitHub · <a href="https://github.com/victorhinojosa/voice-ivr-payment" target="_blank" rel="noreferrer" className="text-primary hover:underline">Click here</a>
        </footer>
      </div>
    </div>
  );
}

export default App;