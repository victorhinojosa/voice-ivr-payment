import React, { useState, useRef, useCallback, useEffect } from 'react';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

// Derive the WebSocket URL from the HTTP API URL (http→ws, https→wss).
const WS_URL = API_URL.replace(/^http/, 'ws') + '/ws/session';

// Web Speech API is vendor-prefixed in some browsers (webkit on Chrome/Edge).
const SpeechRecognition =
  typeof window !== 'undefined'
    ? window.SpeechRecognition || window.webkitSpeechRecognition
    : null;

const speechSupported =
  !!SpeechRecognition &&
  typeof window !== 'undefined' &&
  'speechSynthesis' in window;

function genSessionId() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID();
  return `web-${Date.now()}-${Math.floor(Math.random() * 1e6)}`;
}

// ---------------------------------------------------------------------------
// VoiceSession — runs a browser-based negotiation entirely client-side for
// speech (STT/TTS) and exchanges plain text with the backend over a WebSocket.
// ---------------------------------------------------------------------------
export default function VoiceSession({ onSessionComplete }) {
  // status: 'idle' | 'connecting' | 'speaking' | 'listening' | 'thinking' | 'done' | 'error'
  const [status, setStatus] = useState('idle');
  const [turns, setTurns] = useState([]); // {role: 'agent'|'customer', text}
  const [interim, setInterim] = useState('');
  const [error, setError] = useState(null);

  const wsRef = useRef(null);
  const recognitionRef = useRef(null);
  const sessionIdRef = useRef(null);
  const finishedRef = useRef(false);

  const stopRecognition = useCallback(() => {
    const rec = recognitionRef.current;
    if (rec) {
      rec.onresult = null;
      rec.onend = null;
      rec.onerror = null;
      try { rec.stop(); } catch (e) { /* already stopped */ }
      recognitionRef.current = null;
    }
    setInterim('');
  }, []);

  // Listen for one customer utterance, then send it over the WebSocket.
  const startListening = useCallback(() => {
    if (finishedRef.current) return;
    const rec = new SpeechRecognition();
    rec.lang = 'en-US';
    rec.interimResults = true;
    rec.continuous = false;
    rec.maxAlternatives = 1;

    let finalText = '';

    rec.onresult = (event) => {
      let interimText = '';
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript = event.results[i][0].transcript;
        if (event.results[i].isFinal) finalText += transcript;
        else interimText += transcript;
      }
      setInterim(interimText);
    };

    rec.onerror = (event) => {
      // 'no-speech'/'aborted' are recoverable; surface anything else.
      if (event.error !== 'no-speech' && event.error !== 'aborted') {
        console.warn('SpeechRecognition error:', event.error);
      }
    };

    rec.onend = () => {
      setInterim('');
      const text = finalText.trim();
      const ws = wsRef.current;
      if (finishedRef.current || !ws || ws.readyState !== WebSocket.OPEN) return;
      if (text) setTurns(prev => [...prev, { role: 'customer', text }]);
      setStatus('thinking');
      ws.send(JSON.stringify({ type: 'user', text }));
    };

    recognitionRef.current = rec;
    setStatus('listening');
    try {
      rec.start();
    } catch (e) {
      // start() throws if called too soon after a previous stop — retry shortly.
      setTimeout(() => { try { rec.start(); } catch (_) {} }, 250);
    }
  }, []);

  // Speak the agent's line, then either listen for the reply or finish.
  const speak = useCallback((text, isTerminal) => {
    setStatus('speaking');
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'en-US';
    utterance.onend = () => {
      if (isTerminal || finishedRef.current) return;
      startListening();
    };
    utterance.onerror = () => {
      if (isTerminal || finishedRef.current) return;
      startListening();
    };
    window.speechSynthesis.cancel(); // clear any queued speech
    window.speechSynthesis.speak(utterance);
  }, [startListening]);

  const cleanup = useCallback(() => {
    stopRecognition();
    if (typeof window !== 'undefined' && window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      try { ws.close(); } catch (e) { /* ignore */ }
    }
    wsRef.current = null;
  }, [stopRecognition]);

  const start = useCallback(() => {
    if (!speechSupported) {
      setError('This browser does not support the Web Speech API. Please use Chrome or Edge.');
      setStatus('error');
      return;
    }

    setTurns([]);
    setError(null);
    setInterim('');
    finishedRef.current = false;
    setStatus('connecting');

    const sessionId = genSessionId();
    sessionIdRef.current = sessionId;

    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      ws.send(JSON.stringify({ type: 'start', session_id: sessionId }));
    };

    ws.onmessage = (event) => {
      let msg;
      try { msg = JSON.parse(event.data); } catch (e) { return; }

      if (msg.type === 'agent') {
        setTurns(prev => [...prev, { role: 'agent', text: msg.text }]);
        speak(msg.text, !!msg.is_terminal);
      } else if (msg.type === 'complete') {
        finishedRef.current = true;
        stopRecognition();
        setStatus('done');
        if (onSessionComplete) onSessionComplete();
      } else if (msg.type === 'error') {
        finishedRef.current = true;
        setError(msg.message || 'Session error.');
        setStatus('error');
        cleanup();
      }
    };

    ws.onerror = () => {
      if (finishedRef.current) return;
      setError('Connection error. Is the backend running?');
      setStatus('error');
    };

    ws.onclose = () => {
      // If the server closed before completion, settle into a terminal state.
      if (!finishedRef.current) {
        finishedRef.current = true;
        stopRecognition();
        setStatus(prev => (prev === 'error' ? 'error' : 'done'));
      }
    };
  }, [speak, stopRecognition, cleanup, onSessionComplete]);

  // User ended the session early — tell the server and tear down.
  const handleEnd = useCallback(() => {
    finishedRef.current = true;
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'end' }));
    }
    cleanup();
    setStatus('done');
  }, [cleanup]);

  // Tear down on unmount.
  useEffect(() => () => cleanup(), [cleanup]);

  const statusLabel = {
    idle: 'Ready',
    connecting: 'Connecting…',
    speaking: 'Agent speaking…',
    listening: 'Listening…',
    thinking: 'Thinking…',
    done: 'Session complete',
    error: 'Error',
  }[status];

  const active = ['connecting', 'speaking', 'listening', 'thinking'].includes(status);

  return (
    <div className="card voice-session">
      <div className="voice-header">
        <div>
          <h2 className="voice-title">Voice Negotiation</h2>
          <span className={`voice-status voice-status-${status}`}>{statusLabel}</span>
        </div>
        <div className="voice-actions">
          {!active && (
            <button className="btn btn-call" onClick={start} disabled={!speechSupported}>
              {status === 'done' ? 'Start New Session' : 'Start Negotiation'}
            </button>
          )}
          {active && (
            <button className="btn btn-secondary" onClick={handleEnd}>End</button>
          )}
        </div>
      </div>

      {!speechSupported && (
        <p className="error-text">
          Your browser does not support voice input. Please use Chrome or Edge.
        </p>
      )}
      {error && <p className="error-text">{error}</p>}

      {(turns.length > 0 || interim) && (
        <div className="voice-transcript">
          {turns.map((t, i) => (
            <div key={i} className={`voice-bubble voice-bubble-${t.role}`}>
              <span className="voice-bubble-role">{t.role === 'agent' ? 'Agent' : 'You'}</span>
              <span className="voice-bubble-text">{t.text}</span>
            </div>
          ))}
          {interim && (
            <div className="voice-bubble voice-bubble-customer voice-bubble-interim">
              <span className="voice-bubble-role">You</span>
              <span className="voice-bubble-text">{interim}…</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
