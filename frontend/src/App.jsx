import React, { useState, useEffect, useCallback } from 'react';
import './App.css';
import VoiceSession from './VoiceSession';
import { CallHistoryView } from './components/call-history-view';
import { formatDate, formatDuration, formatCurrency } from './lib/utils';
import { AppSidebar } from './components/app-sidebar';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

// ---------------------------------------------------------------------------
// Customer Form (modal — used for both create and edit)
// ---------------------------------------------------------------------------
function CustomerForm({ initial, onSave, onCancel, error }) {
  const [name, setName] = useState(initial?.name || '');
  const [phone, setPhone] = useState(initial?.phone || '');
  const [amountOwed, setAmountOwed] = useState(initial?.amount_owed ?? '');
  const [saving, setSaving] = useState(false);

  const isEdit = initial != null;

  const submit = async () => {
    if (!name.trim() || !phone.trim()) return;
    setSaving(true);
    await onSave({
      name: name.trim(),
      phone: phone.trim(),
      amount_owed: parseFloat(amountOwed) || 0
    });
    setSaving(false);
  };

  const overlay = {
    position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
    display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
  };

  return (
    <div style={overlay} onClick={onCancel}>
      <div className="card" style={{ width: 400, maxWidth: '90%' }} onClick={e => e.stopPropagation()}>
        <h3 style={{ marginTop: 0 }}>{isEdit ? 'Edit Customer' : 'New Customer'}</h3>

        <div className="field-group">
          <label>Name</label>
          <input value={name} onChange={e => setName(e.target.value)} />
        </div>
        <div className="field-group">
          <label>Phone</label>
          <input value={phone} onChange={e => setPhone(e.target.value)} />
        </div>
        <div className="field-group">
          <label>Amount Owed</label>
          <input type="number" step="0.01" value={amountOwed} onChange={e => setAmountOwed(e.target.value)} />
        </div>

        {error && <p className="error-text">{error}</p>}

        <div className="control-actions">
          <button className="btn btn-secondary" onClick={onCancel} disabled={saving}>Cancel</button>
          <button className="btn btn-primary" onClick={submit} disabled={saving}>
            {saving ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Call Modal — wraps VoiceSession for a specific customer
// ---------------------------------------------------------------------------
function CallModal({ customer, onClose }) {
  const overlay = {
    position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
    display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
  };
  return (
    <div style={overlay}>
      <div style={{ width: 560, maxWidth: '95%' }}>
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 8 }}>
          <button className="btn btn-secondary" onClick={onClose}>Close</button>
        </div>
        <VoiceSession customerId={customer.id} customerName={customer.name} />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Customer Table
// ---------------------------------------------------------------------------
function CustomerTable({ customers, onEdit, onDelete , onStartCall}) {
  return (
    <div className="card table-card">
      <table className="call-table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Phone</th>
            <th>Amount Owed</th>
            <th>Status</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {customers.length === 0 ? (
            <tr><td colSpan="5" className="no-data">No customers yet</td></tr>
          ) : (
            customers.map(c => (
              <tr key={c.id}>
                <td>{c.name}</td>
                <td>{c.phone}</td>
                <td>{formatCurrency(c.amount_owed)}</td>
                <td>
                  <span
                    className="outcome-badge"
                    style={{ backgroundColor: c.status === 'active' ? '#10b981' : '#6b7280' }}
                  >
                    {c.status}
                  </span>
                </td>
                <td>
                  <button className="btn btn-call" onClick={() => onStartCall(c)}>Start call</button>
                  <button className="btn btn-secondary" style={{ marginLeft: 8 }} onClick={() => onEdit(c)}>Edit</button>
                  <button className="btn btn-secondary" style={{ marginLeft: 8 }} onClick={() => onDelete(c.id)}>Delete</button>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Customers View
// ---------------------------------------------------------------------------
function CustomersView() {
  const [customers, setCustomers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState(null);     // customer being edited, or null = create
  const [formError, setFormError] = useState(null);
  const [callingCustomer, setCallingCustomer] = useState(null);

  const fetchCustomers = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetch(`${API_URL}/api/customers`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = await r.json();   // bare array, not { customers: [...] }
      setCustomers(data);
      setError(null);
    } catch {
      setError('Failed to load customers.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchCustomers(); }, [fetchCustomers]);

  const openCreate = () => { setEditing(null); setFormError(null); setFormOpen(true); };
  const openEdit = (customer) => { setEditing(customer); setFormError(null); setFormOpen(true); };
  const closeForm = () => { setFormOpen(false); setEditing(null); setFormError(null); };

  const handleSave = async (payload) => {
    const isEdit = editing != null;
    const url = isEdit ? `${API_URL}/api/customers/${editing.id}` : `${API_URL}/api/customers`;
    try {
      const r = await fetch(url, {
        method: isEdit ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      await fetchCustomers();
      closeForm();
    } catch {
      setFormError('Failed to save customer.');
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Delete this customer?')) return;
    try {
      const r = await fetch(`${API_URL}/api/customers/${id}`, { method: 'DELETE' });
      if (!r.ok) throw new Error();   // 204, no body — don't parse
      await fetchCustomers();
    } catch {
      setError('Failed to delete customer.');
    }
  };

  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '1rem' }}>
        <button className="btn btn-primary" onClick={openCreate}>+ New Customer</button>
      </div>

      {loading ? (
        <p className="muted center-text">Loading customers…</p>
      ) : error ? (
        <p className="error-text center-text">{error}</p>
      ) : (
        <CustomerTable
          customers={customers}
          onEdit={openEdit}
          onDelete={handleDelete}
          onStartCall={setCallingCustomer}
        />
      )}

      {callingCustomer && (
        <CallModal customer={callingCustomer} onClose={() => setCallingCustomer(null)} />
      )}

      {formOpen && (
        <CustomerForm
          initial={editing}
          onSave={handleSave}
          onCancel={closeForm}
          error={formError}
        />
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// Stats Bar
// ---------------------------------------------------------------------------


// ---------------------------------------------------------------------------
// Call History Table
// ---------------------------------------------------------------------------

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
            <CustomersView />
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