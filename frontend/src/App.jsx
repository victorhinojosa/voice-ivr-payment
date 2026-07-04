import React, { useState, useEffect, useCallback } from 'react';
import './App.css';
import { Users, Phone } from 'lucide-react';
import { CallHistoryView } from './components/call-history-view';
import { AppSidebar } from './components/app-sidebar';
import { CustomersView } from './components/customers-view';
import { CustomerDialog } from './components/customer-dialog';
import { LiveCallDialog } from './components/live-call-dialog';
import { generateRandomPhone, cn } from './lib/utils';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

// ---------------------------------------------------------------------------
// Customers Page
// ---------------------------------------------------------------------------
function CustomersPage({ onCountChange }) {
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
        <LiveCallDialog customer={callingCustomer} onClose={() => setCallingCustomer(null)} />
      )}
    </>
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

  const fetchCalls = useCallback(async () => {
    try {
      const r = await fetch(`${API_URL}/api/calls`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = await r.json();
      setCalls(data.calls);
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
      <AppSidebar />
      <div className="flex-1 p-6 lg:p-8">

        {/* Header */}
        <div className="border-b border-border pb-4 mb-6">
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-semibold text-foreground">Collections Dashboard</h1>
            <span className="inline-flex items-center gap-1.5 rounded-full bg-success/12 px-2.5 py-0.5 text-xs font-medium text-success">
              <span className="size-1.5 rounded-full bg-success" />
              Agent online
            </span>
          </div>
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

        {view === 'customers' ? (
          <CustomersPage onCountChange={setCustomersCount} />
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
    </div>
  );
}

export default App;