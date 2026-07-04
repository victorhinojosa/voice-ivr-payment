import React, { useState, useEffect, useCallback } from 'react';
import './App.css';
import { CallHistoryView } from './components/call-history-view';
import { AppSidebar } from './components/app-sidebar';
import { CustomersView } from './components/customers-view';
import { CustomerDialog } from './components/customer-dialog';
import { LiveCallDialog } from './components/live-call-dialog';
import { generateRandomPhone } from './lib/utils';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

// ---------------------------------------------------------------------------
// Customers Page
// ---------------------------------------------------------------------------
function CustomersPage() {
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
      setCustomers(await r.json());
      setError(null);
    } catch {
      setError('Failed to load customers.');
    } finally {
      setLoading(false);
    }
  }, []);

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
        <header className="header">
          <h1>Dashboard</h1>
          <p className="subtitle">Promise-to-Pay Collection System</p>
        </header>

        <div className="container">
          <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
            <button
              className={`btn ${view === 'customers' ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setView('customers')}
            >
              Customers
            </button>
            <button
              className={`btn ${view === 'calls' ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setView('calls')}
            >
              Call History
            </button>
          </div>

          {view === 'customers' ? (
            <CustomersPage />
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
    </div>
  );
}

export default App;