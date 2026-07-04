import React, { useState, useRef, useCallback, useEffect } from 'react';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

// Derive the WebSocket URL from the HTTP API URL (http→ws, https→wss).
const WS_URL = API_URL.replace(/^http/, 'ws') + '/ws/session';

const mediaSupported =
  typeof navigator !== 'undefined' &&
  !!navigator.mediaDevices &&
  typeof MediaRecorder !== 'undefined';

function genSessionId() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID();
  return `web-${Date.now()}-${Math.floor(Math.random() * 1e6)}`;
}

function blobToBase64(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => resolve(reader.result.split(',')[1]);
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}

export default function VoiceSession({ onSessionComplete, customerId, customerName }) {

  const [status, setStatus] = useState('idle'); // status: 'idle' | 'connecting' | 'speaking' | 'listening' | 'thinking' | 'done' | 'error'
  const [turns, setTurns] = useState([]); // {role: 'agent'|'customer', text}
  const [error, setError] = useState(null);

  const wsRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const finishedRef = useRef(false);

  const stopListening = useCallback(() => {
    const rec = mediaRecorderRef.current;
    if (rec && rec.state !== 'inactive') rec.stop();
  }, []);

  const startListening = useCallback(async () => {
    if (finishedRef.current) return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
      audioChunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data);
      };

      recorder.onstop = async () => {
        stream.getTracks().forEach(t => t.stop());
        const ws = wsRef.current;
        if (finishedRef.current || !ws || ws.readyState !== WebSocket.OPEN) return;
        const blob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        const base64 = await blobToBase64(blob);
        setStatus('thinking');
        ws.send(JSON.stringify({ type: 'user_audio', audio: base64 }));
      };

      mediaRecorderRef.current = recorder;
      recorder.start();
      setStatus('listening');
    } catch (e) {
      setError('Microphone access denied or unavailable.');
      setStatus('error');
    }
  }, []);

  const speak = useCallback((text, audioB64, isTerminal) => {
    setStatus('speaking');
    const audio = new Audio(`data:audio/mpeg;base64,${audioB64}`);
    const advance = () => { if (!isTerminal && !finishedRef.current) startListening(); };
    audio.onended = advance;
    audio.onerror = (e) => {
      console.error('Audio playback error:', e, audio.error);
      advance();
    };
    audio.play().catch((err) => {
      console.error('Audio play() rejected:', err.name, err.message);
      advance();
    });
  }, [startListening]);

  const cleanup = useCallback(() => {
    stopListening();
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) { try { ws.close(); } catch (e) {} }
    wsRef.current = null;
  }, [stopListening]);

  const start = useCallback(() => {
    if (!mediaSupported) {
      setError('This browser does not support microphone recording.');
      setStatus('error');
      return;
    }
    setTurns([]);
    setError(null);
    finishedRef.current = false;
    setStatus('connecting');

    const sessionId = genSessionId();
    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      ws.send(JSON.stringify({ type: 'start', session_id: sessionId, customer_id: customerId, customer_name: customerName }));
    };

    ws.onmessage = (event) => {
      let msg;
      try { msg = JSON.parse(event.data); } catch (e) { return; }

      if (msg.type === 'agent') {
        console.log('[DEBUG] agent msg audio length:', msg.audio ? msg.audio.length : 'MISSING/EMPTY');
        setTurns(prev => [...prev, { role: 'agent', text: msg.text }]);
        speak(msg.text, msg.audio, !!msg.is_terminal);
      } else if (msg.type === 'user') {
        setTurns(prev => [...prev, { role: 'customer', text: msg.text }]);
      } else if (msg.type === 'complete') {
        finishedRef.current = true;
        stopListening();
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
      if (!finishedRef.current) {
        finishedRef.current = true;
        stopListening();
        setStatus(prev => (prev === 'error' ? 'error' : 'done'));
      }
    };
  }, [speak, stopListening, cleanup, onSessionComplete, customerId, customerName]);


  const handleEnd = useCallback(() => {
    finishedRef.current = true;
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'end' }));
    cleanup();
    setStatus('done');
  }, [cleanup]);

  useEffect(() => () => cleanup(), [cleanup]);

  const statusLabel = {
    idle: 'Ready', connecting: 'Connecting…', speaking: 'Agent speaking…',
    listening: 'Listening — tap Done when finished', thinking: 'Thinking…',
    done: 'Session complete', error: 'Error',
  }[status];

  const active = ['connecting', 'speaking', 'listening', 'thinking'].includes(status);

  return (
    <div className="card voice-session">
      <div className="voice-header">
        <div>
          <h2 className="voice-title">{customerName ? `Negotiation — ${customerName}` : 'Voice Negotiation'}</h2>
          <span className={`voice-status voice-status-${status}`}>{statusLabel}</span>
        </div>
        <div className="voice-actions">
          {!active && (
            <button className="btn btn-call" onClick={start} disabled={!mediaSupported}>
              {status === 'done' ? 'Start New Session' : 'Start Negotiation'}
            </button>
          )}
          {status === 'listening' && (
            <button className="btn btn-call" onClick={stopListening}>Done Speaking</button>
          )}
          {active && (
            <button className="btn btn-secondary" onClick={handleEnd}>End</button>
          )}
        </div>
      </div>

      {!mediaSupported && (
        <p className="error-text">Your browser does not support microphone recording.</p>
      )}
      {error && <p className="error-text">{error}</p>}

      {turns.length > 0 && (
        <div className="voice-transcript">
          {turns.map((t, i) => (
            <div key={i} className={`voice-bubble voice-bubble-${t.role}`}>
              <span className="voice-bubble-role">{t.role === 'agent' ? 'Agent' : 'You'}</span>
              <span className="voice-bubble-text">{t.text}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}