import React, { useState, useRef, useCallback, useEffect } from 'react';
import { MicVAD } from '@ricky0123/vad-web';
import { encodeWav } from './wavEncoder';

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
  const vadRef = useRef(null);
  const finishedRef = useRef(false);

  const ensureVAD = useCallback(async () => {
    if (vadRef.current) return vadRef.current;
    const vad = await MicVAD.new({
      baseAssetPath: "/",
      onnxWASMBasePath: "/",
      onSpeechStart: () => setStatus('listening'),
      onSpeechEnd: async (audioFloat32) => {
        vad.pause();
        const ws = wsRef.current;
        if (finishedRef.current || !ws || ws.readyState !== WebSocket.OPEN) return;
        const wavBlob = encodeWav(audioFloat32);
        const base64 = await blobToBase64(wavBlob);
        setStatus('thinking');
        ws.send(JSON.stringify({ type: 'user_audio', audio: base64 }));
      },
    });
    vadRef.current = vad;
    return vad;
  }, []);

  const startListening = useCallback(async () => {
    if (finishedRef.current) return;
    try {
      const vad = await ensureVAD();
      vad.start();
      setStatus('listening');
    } catch (e) {
      setError('Microphone access denied or unavailable.');
      setStatus('error');
    }
  }, [ensureVAD]);

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
    if (vadRef.current) { try { vadRef.current.pause(); } catch (e) {} }
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) { try { ws.close(); } catch (e) {} }
    wsRef.current = null;
  }, []);

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
        setStatus(prev => (prev === 'error' ? 'error' : 'done'));
      }
    };
  }, [speak, stopRecognition, cleanup, onSessionComplete, customerName]);

  const handleEnd = useCallback(() => {
    finishedRef.current = true;
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'end' }));
    cleanup();
    setStatus('done');
  }, [cleanup]);

  useEffect(() => () => {
    cleanup();
    if (vadRef.current) { try { vadRef.current.destroy(); } catch (e) {} vadRef.current = null; }
  }, [cleanup]);

  const statusLabel = {
    idle: 'Ready', connecting: 'Connecting…', speaking: 'Agent speaking…',
    listening: 'Listening...', thinking: 'Thinking…',
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