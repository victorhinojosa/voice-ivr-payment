# AI Collections Operations Platform

AI voice agent that autonomously negotiates real payment commitments in a **browser-based** voice session using the Web Speech API and Claude.

## Features

- **In-browser voice session** — the agent speaks and the user replies through their microphone, entirely in the browser (no telephony provider)
- **Multi-turn AI negotiation** — Claude handles the full conversation, offers plans, and adapts to responses
- **Promise-to-Pay extraction** — after the session, Claude analyzes the transcript to extract outcome, date, and amount
- **Real-time dashboard** — monitor sessions, outcomes, and full transcripts in the browser
- **Supabase (Postgres) persistence** — all sessions and config stored durably in a hosted database, auto-provisioned on first run

## Tech Stack


| Layer            | Technology                                                       |
| ---------------- | ---------------------------------------------------------------- |
| Backend          | Python FastAPI (async)                                           |
| Voice transport  | WebSocket (`/ws/session`)                                        |
| Speech (STT/TTS) | Browser Web Speech API (`SpeechRecognition` + `SpeechSynthesis`) |
| AI Agent         | Claude Haiku (Anthropic)                                         |
| Database         | Supabase (asyncpg)                                               |
| Frontend         | React 18                                                         |


> **Browser support:** the Web Speech API for speech *recognition* is currently supported in Chromium-based browsers (**Chrome** and **Edge**). Firefox and Safari do not reliably support `SpeechRecognition`. 

## How It Works

### Session Flow

```
1. User clicks "Start Negotiation" in the dashboard
        ↓
2. Browser opens a WebSocket to the backend and sends {type: "start"}
        ↓
3. Backend creates a DB record (calls table) and returns the agent's opening line
   "Hello, this is a courtesy call regarding your outstanding balance of $X.
    When would you be able to make a payment?"
   → browser speaks it via SpeechSynthesis (TTS)
        ↓
4. Browser listens via SpeechRecognition (STT) and sends the recognized
   text to the backend: {type: "user", text: "..."}
        ↓
5. Claude (agent_reply) generates the next response
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
.\venv\Scripts\Activate.ps1   # Windows
source venv/bin/activate       # Mac/Linux
pip install -r requirements.txt
```

**Frontend:**

```bash
cd frontend
npm install
```

### 2. Configure environment

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

```env
ANTHROPIC_API_KEY=your_anthropic_api_key

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
│   ├── db.py              # PostgreSQL operations
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── App.jsx          # Dashboard UI
│   │   ├── VoiceSession.jsx # Browser voice session (Web Speech API + WebSocket)
│   │   └── App.css
│   └── package.json
├── docker-compose.yml
├── .env.example
└── README.md
```

