import React, { useState, useEffect } from 'react';
import './App.css';

function App() {
  const [calls, setCalls] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expandedRow, setExpandedRow] = useState(null);

  const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

  useEffect(() => {
    fetchCalls();
    // Poll for new calls every 10 seconds
    const interval = setInterval(fetchCalls, 10000);
    return () => clearInterval(interval);
  }, []);

  const fetchCalls = async () => {
    try {
      const response = await fetch(`${API_URL}/api/calls`);
      const data = await response.json();
      setCalls(data.calls);
      setLoading(false);
    } catch (error) {
      console.error('Error fetching calls:', error);
      setLoading(false);
    }
  };

  const formatDate = (isoString) => {
    const date = new Date(isoString);
    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const formatIntent = (intent) => {
    if (!intent) return 'Unknown';
    // Replace underscores with spaces and capitalize each word
    return intent
      .split('_')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
      .join(' ');
  };

  const getIntentBadge = (intent) => {
    const colors = {
      'willing_to_pay': '#10b981',
      'needs_negotiation': '#f59e0b',
      'refuses': '#ef4444',
      'error': '#6b7280',
      'unknown': '#6b7280',
      'unclear': '#9ca3af',
      'no_response': '#6b7280',
      'pending_clarification': '#3b82f6'
    };
    return colors[intent] || '#6b7280';
  };

  if (loading) {
    return <div className="loading">Loading calls...</div>;
  }

  return (
    <div className="App">
      <header className="header">
        <h1>Dashboard</h1>
        <p className="subtitle">Call Log & Payment Negotiation Tracker</p>
      </header>

      <div className="container">
        <div className="stats">
          <div className="stat-card">
            <div className="stat-value">{calls.length}</div>
            <div className="stat-label">Total Calls</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">
              {calls.filter(c => c.intent === 'willing_to_pay').length}
            </div>
            <div className="stat-label">Willing to Pay</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">
              {calls.filter(c => c.intent === 'needs_negotiation').length}
            </div>
            <div className="stat-label">Negotiating</div>
          </div>
        </div>

        <table className="call-table">
          <thead>
            <tr>
              <th>Date</th>
              <th>Caller</th>
              <th>Intent</th>
              <th>Payment Plan</th>
              <th>Confidence</th>
            </tr>
          </thead>
          <tbody>
            {calls.length === 0 ? (
              <tr>
                <td colSpan="5" className="no-data">No calls yet</td>
              </tr>
            ) : (
              calls.map((call) => (
                <React.Fragment key={call.id}>
                  <tr
                    onClick={() => setExpandedRow(expandedRow === call.id ? null : call.id)}
                    className={expandedRow === call.id ? 'expanded' : ''}
                  >
                    <td>{formatDate(call.timestamp)}</td>
                    <td>{call.caller_phone}</td>
                    <td>
                      <span
                        className="intent-badge"
                        style={{ backgroundColor: getIntentBadge(call.intent) }}
                      >
                        {formatIntent(call.intent)}
                      </span>
                    </td>
                    <td>{call.payment_plan || '-'}</td>
                    <td>{call.confidence ? `${call.confidence}%` : '-'}</td>
                  </tr>
                  {expandedRow === call.id && (
                    <tr className="expanded-row">
                      <td colSpan="5">
                        <div className="transcript-box">
                          <div className="transcript-section">
                            <strong>Transcript:</strong>
                            <p>{call.transcript || 'No transcript available'}</p>
                          </div>
                          <div className="transcript-section">
                            <strong>AI Response:</strong>
                            <p>{call.reply_text || '-'}</p>
                          </div>
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
    </div>
  );
}

export default App;
