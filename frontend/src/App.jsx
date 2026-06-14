import React, { useState, useEffect, useCallback } from 'react';
import './App.css';
import VoiceSession from './VoiceSession';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const OUTCOME_COLORS = {
  promise_made:  '#10b981',
  refused:       '#ef4444',
  no_commitment: '#6b7280',
  initiated:     '#3b82f6',
  no_answer:     '#f97316',
};

const OUTCOME_LABELS = {
  promise_made:  'Promise Made',
  refused:       'Refused',
  no_commitment: 'No Commitment',
  initiated:     'Initiated',
  no_answer:     'No Answer',
};

function formatDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('en-US', {
    month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

function formatDuration(seconds) {
  if (seconds == null) return '—';
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

function formatCurrency(amount) {
  if (amount == null) return '—';
  return `$${parseFloat(amount).toFixed(2)}`;
}

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
// Customer Table
// ---------------------------------------------------------------------------
function CustomerTable({ customers, onEdit, onDelete }) {
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
                  <button className="btn btn-secondary" onClick={() => onEdit(c)}>Edit</button>
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
// Customers View (container — owns state + CRUD)
// ---------------------------------------------------------------------------
function CustomersView() {
  const [customers, setCustomers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState(null);     // customer being edited, or null = create
  const [formError, setFormError] = useState(null);

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
        <CustomerTable customers={customers} onEdit={openEdit} onDelete={handleDelete} />
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
function StatsBar({ calls }) {
  const stats = [
    { label: 'Total Calls',    value: calls.length },
    { label: 'Promises Made',  value: calls.filter(c => c.outcome === 'promise_made').length },
    { label: 'Refused',        value: calls.filter(c => c.outcome === 'refused').length },
    { label: 'No Commitment',  value: calls.filter(c => c.outcome === 'no_commitment').length },
  ];
  return (
    <div className="stats-bar">
      {stats.map(s => (
        <div className="stat-tile" key={s.label}>
          <div className="stat-value">{s.value}</div>
          <div className="stat-label">{s.label}</div>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Call History Table
// ---------------------------------------------------------------------------
function CallTable({ calls }) {
  const [expandedRow, setExpandedRow] = useState(null);
  const toggle = (id) => setExpandedRow(prev => prev === id ? null : id);

  return (
    <div className="card table-card">
      <table className="call-table">
        <thead>
          <tr>
            <th>Date</th>
            <th>Phone</th>
            <th>Duration</th>
            <th>Outcome</th>
            <th>Promise Date</th>
            <th>Promise Amount</th>
          </tr>
        </thead>
        <tbody>
          {calls.length === 0 ? (
            <tr><td colSpan="6" className="no-data">No calls yet</td></tr>
          ) : (
            calls.map(call => (
              <React.Fragment key={call.id}>
                <tr
                  onClick={() => toggle(call.id)}
                  className={expandedRow === call.id ? 'row-expanded' : ''}
                >
                  <td>{formatDate(call.initiated_at)}</td>
                  <td>{call.phone_number}</td>
                  <td>{formatDuration(call.duration_seconds)}</td>
                  <td>
                    <span
                      className="outcome-badge"
                      style={{ backgroundColor: OUTCOME_COLORS[call.outcome] || OUTCOME_COLORS[call.status] || '#6b7280' }}
                    >
                      {OUTCOME_LABELS[call.outcome] || OUTCOME_LABELS[call.status] || call.outcome || call.status || '—'}
                    </span>
                  </td>
                  <td>{call.promise_date || '—'}</td>
                  <td>{formatCurrency(call.promise_amount)}</td>
                </tr>
                {expandedRow === call.id && (
                  <tr className="transcript-row">
                    <td colSpan="6">
                      <div className="transcript-box">
                        <strong>Transcript</strong>
                        <p>{call.transcript || 'No transcript recorded.'}</p>
                      </div>
                    </td>
                  </tr>
                )}
              </React.Fragment>
            ))
          )}
        </tbody>
      </table>
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
    <div className="App">
      <header className="header">
        <h1>IVR Dashboard</h1>
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
            <VoiceSession onSessionComplete={fetchCalls} />
            {callsLoading ? (
              <p className="muted center-text">Loading calls…</p>
            ) : callsError ? (
              <p className="error-text center-text">{callsError}</p>
            ) : (
              <>
                <StatsBar calls={calls} />
                <CallTable calls={calls} />
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}

export default App;