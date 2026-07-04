# AI Collections Operations Platform

AI voice agent that autonomously negotiates real payment commitments in a **browser-based** voice session using the Web Speech API and Claude.

## Features

- **In-browser voice session** — the agent speaks and the user replies through their microphone, entirely in the browser (no telephony provider)
- **Natural voice + automatic turn detection** — ElevenLabs TTS for realistic speech, ElevenLabs Scribe for transcription, and client-side VAD (Silero, via ONNX Runtime Web) to detect when the user starts/stops talking
- **Multi-turn AI negotiation** — Claude handles the full conversation, offers plans, and adapts to responses
- **Promise-to-Pay extraction** — after the session, Claude analyzes the transcript to extract outcome, date, and amount
- **Real-time dashboard** — monitor sessions, outcomes, and full transcripts in the browser
- **Supabase (Postgres) persistence** — all sessions and config stored durably in a hosted database, auto-provisioned on first run

## Tech Stack


| Layer            | Technology                                                                          |
| ---------------- | ------------------------------------------------------------------------------------|
| Backend          | Python FastAPI (async)                                                              |
| Voice transport  | WebSocket (`/ws/session`)                                                           |
| Speech (TTS)     | ElevenLabs (`eleven_flash_v2_5`)                                                    |
| Speech (STT)     | ElevenLabs Scribe (`scribe_v1`)                                                     |
| Turn detection   | Client-side VAD — Silero model via `@ricky0123/vad-web` + ONNX Runtime Web (WASM)   |
| AI Agent         | Claude Haiku (Anthropic)                                                            |
| Database         | Supabase (asyncpg)                                                                  |
| Frontend         | React 18                                                                            |

## How It Works

### Session Flow

```
1. User clicks "Start Negotiation" in the dashboard
        ↓
2. Browser opens a WebSocket to the backend and sends {type: "start"}
        ↓
3. Backend creates a DB record (calls table) and returns the agent's opening 
   line as text + ElevenLabs-generated audio (base64)
   → browser plays the audio
        ↓
4. Client-side VAD detects the user speaking and, once they stop, captures
   the audio, encodes it as WAV, and sends it to the backend:
   {type: "user_audio", audio: "<base64 WAV>"}
   ↓
5. Backend transcribes the audio via ElevenLabs Scribe, then Claude
   (agent_reply) generates the next response
   - If customer commits with a date → set is_terminal: true
   - If customer commits but no date → ask for a date
   - If unclear → ask a clarifying question
   Controlled multi-turn loop (bounded to ensure reliability)
        ↓
6. On terminal turn → Claude (extract_ptp) analyzes the full transcript:
   - outcome: promise_made | refused | no_commitment
   - promise_date: resolved to an absolute date
   - promise_amount: extracted or defaults to amount owed
        ↓
7. Result saved to Database, dashboard refreshes
```

### Outcome Types


| Outcome         | Meaning                                    |
| --------------- | ------------------------------------------ |
| `promise_made`  | Customer agreed to pay (has date + amount) |
| `refused`       | Customer explicitly refused                |
| `no_commitment` | Ambiguous — requires follow-up             |


## Quick Start

### 1. Clone and install dependencies

**Backend:**

```bash
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1  # Windows
source venv/bin/activate       # Mac/Linux
pip install -r requirements.txt
```

**Frontend:**

```bash
cd frontend
npm install
```

> Voice activity detection requires model/runtime files to be served from `frontend/public/` (Silero ONNX model, ONNX Runtime WASM binaries, VAD worklet). These are committed to the repo directly — see `frontend/public/`.

### 2. Configure environment

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

```env
ANTHROPIC_API_KEY=your_anthropic_api_key
ELEVENLABS_API_KEY=your_elevenlabs_api_key
ELEVENLABS_VOICE_ID=your_chosen_voice_id

DATABASE_URL=postgresql://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres?sslmode=require
```

### 3. Run locally

**Terminal 1 — Backend:**

```bash
cd backend
python main.py
```

**Terminal 2 — Frontend:**

```bash
cd frontend
npm start
```

## Dashboard

Open `http://localhost:3000`

- **Control Panel** — set the phone number (label) and the debt amount
- **Voice Negotiation** — click **Start Negotiation** to run a live session; the live transcript appears as the conversation proceeds
- **Stats Bar** — totals by outcome
- **Call Table** — click any row to expand the full transcript
- Auto-refreshes every 10 seconds

**Outcome badge colors:**

- Green — `promise_made`
- Red — `refused`
- Gray — `no_commitment`

## API Reference


| Method | Endpoint      | Description                                |
| ------ | ------------- | ------------------------------------------ |
| `GET`  | `/api/calls`  | List all session records                   |
| `GET`  | `/api/config` | Get current config (phone, amount)         |
| `PUT`  | `/api/config` | Update a config value                      |
| `WS`   | `/ws/session` | Browser voice session (see protocol below) |


### WebSocket protocol (`/ws/session`)

```
client → server:
  {"type": "start", "session_id": "<uuid>"}   # open the session
  {"type": "user",  "text": "<recognized speech>"}
  {"type": "end"}                              # user ended early

server → client:
  {"type": "agent",    "text": "...", "is_terminal": false}
  {"type": "complete", "outcome": "...", "promise_date": "...", "promise_amount": 0.0}
  {"type": "error",    "message": "..."}
```

The browser-generated `session_id` is stored in the `calls.call_sid` column.

## Database Schema

```sql
CREATE TABLE calls (
    id               SERIAL PRIMARY KEY,
    call_sid         TEXT,                        -- browser session id
    phone_number     TEXT NOT NULL,
    status           TEXT DEFAULT 'initiated',   -- initiated | completed | no_answer
    outcome          TEXT,                        -- promise_made | refused | no_commitment
    amount_owed      NUMERIC(10, 2),
    promise_date     DATE,
    promise_amount   NUMERIC(10, 2),
    transcript       TEXT,                        -- JSON array of conversation turns
    duration_seconds INTEGER,
    initiated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at     TIMESTAMP
);

CREATE TABLE config (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

## Project Structure

```
voice-ivr-payment/
├── backend/
│   ├── main.py            # FastAPI app, /ws/session voice transport, session orchestration
│   ├── claude_agent.py    # Claude AI — agent_reply() and extract_ptp()
│   ├── voice_io.py        # ElevenLabs TTS (synthesize_speech) and STT (transcribe_speech)
│   ├── db.py              # PostgreSQL operations
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── public/             # Silero VAD model, ONNX Runtime WASM, VAD worklet (static assets)
│   ├── src/
│   │   ├── App.jsx          # Dashboard UI
│   │   ├── VoiceSession.jsx # Browser voice session (VAD + WebSocket + ElevenLabs audio playback)
│   │   ├── wavEncoder.js    # Encodes raw VAD audio (Float32) into WAV for upload
│   │   └── App.css
│   └── package.json
├── .env.example
└── README.md
```

