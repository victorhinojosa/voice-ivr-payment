import React, { useState, useEffect, useCallback } from 'react';
import './App.css';

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
// Control Panel
// ---------------------------------------------------------------------------
function ControlPanel({ onCallInitiated }) {
  const [config, setConfig] = useState(null);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState({});
  const [configLoading, setConfigLoading] = useState(true);
  const [configError, setConfigError] = useState(null);
  const [calling, setCalling] = useState(false);
  const [callMessage, setCallMessage] = useState(null); // {type: 'success'|'error', text}

  useEffect(() => {
    fetch(`${API_URL}/api/config`)
      .then(r => r.json())
      .then(data => { setConfig(data); setConfigLoading(false); })
      .catch(() => { setConfigError('Failed to load config.'); setConfigLoading(false); });
  }, []);

  const startEdit = () => {
    setDraft({ ...config });
    setEditing(true);
    setCallMessage(null);
  };

  const cancelEdit = () => {
    setEditing(false);
    setDraft({});
  };

  const saveConfig = async () => {
    const keys = Object.keys(draft);
    try {
      await Promise.all(keys.map(key =>
        fetch(`${API_URL}/api/config`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ key, value: draft[key] }),
        }).then(r => { if (!r.ok) throw new Error(`Failed to save ${key}`); })
      ));
      setConfig({ ...draft });
      setEditing(false);
    } catch (err) {
      setCallMessage({ type: 'error', text: err.message });
    }
  };

  const initiateCall = async () => {
    setCalling(true);
    setCallMessage(null);
    try {
      const r = await fetch(`${API_URL}/api/calls/initiate`, { method: 'POST' });
      const data = await r.json();
      if (!r.ok) {
        const msg = data.detail || data.message || JSON.stringify(data);
        setCallMessage({ type: 'error', text: `Error: ${msg}` });
      } else {
        setCallMessage({ type: 'success', text: `Call placed — SID: ${data.call_sid}` });
        onCallInitiated();
      }
    } catch (err) {
      setCallMessage({ type: 'error', text: `Network error: ${err.message}` });
    } finally {
      setCalling(false);
    }
  };

  if (configLoading) return <div className="card control-panel"><p className="muted">Loading config…</p></div>;
  if (configError)  return <div className="card control-panel"><p className="error-text">{configError}</p></div>;

  return (
    <div className="card control-panel">
      <div className="control-fields">
        <div className="field-group">
          <label>Phone Number</label>
          {editing
            ? <input value={draft.debtor_phone || ''} onChange={e => setDraft(d => ({ ...d, debtor_phone: e.target.value }))} />
            : <span className="field-value">{config.debtor_phone}</span>}
        </div>
        <div className="field-group">
          <label>Amount Owed</label>
          {editing
            ? <input value={draft.amount_owed || ''} onChange={e => setDraft(d => ({ ...d, amount_owed: e.target.value }))} />
            : <span className="field-value">{formatCurrency(config.amount_owed)}</span>}
        </div>
        <div className="control-actions">
          {editing ? (
            <>
              <button className="btn btn-secondary" onClick={cancelEdit}>Cancel</button>
              <button className="btn btn-primary" onClick={saveConfig}>Save</button>
            </>
          ) : (
            <button className="btn btn-secondary" onClick={startEdit}>Edit</button>
          )}
        </div>
      </div>

      <div className="call-action">
        <button
          className="btn btn-call"
          onClick={initiateCall}
          disabled={calling || editing}
        >
          {calling ? 'Calling…' : 'Call Now'}
        </button>
        {callMessage && (
          <p className={callMessage.type === 'error' ? 'error-text' : 'success-text'}>
            {callMessage.text}
          </p>
        )}
      </div>
    </div>
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
        <ControlPanel onCallInitiated={fetchCalls} />

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
      </div>
    </div>
  );
}

export default App;
