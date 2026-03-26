# Voice IVR Payment Negotiation System

An automated outbound call system that uses Twilio and Claude AI to negotiate payment commitments with customers, extract Promise-to-Pay (PTP) data, and log outcomes to a real-time dashboard.

## Features

- **Outbound voice calls** via Twilio with a professional IVR greeting
- **Multi-turn AI negotiation** — Claude handles the full conversation, offers plans, and adapts to responses
- **Promise-to-Pay extraction** — after the call, Claude analyzes the transcript to extract outcome, date, and amount
- **Real-time dashboard** — monitor calls, outcomes, and full transcripts in the browser
- **PostgreSQL persistence** — all calls and config stored durably

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python FastAPI (async) |
| Telephony | Twilio Programmable Voice |
| AI Agent | Claude Haiku (Anthropic) |
| Database | PostgreSQL (asyncpg) |
| Frontend | React 18 |

## How It Works

### Call Flow

```
1. User clicks "Call Now" in dashboard
        ↓
2. Backend creates DB record, fires outbound call via Twilio
        ↓
3. Customer answers → IVR greeting played
   "Hello, this is a courtesy call regarding your outstanding balance of $X.
    When would you be able to make a payment?"
        ↓
4. Customer speaks → Twilio sends speech-to-text to /process-response
        ↓
5. Claude (agent_reply) generates next response
   - If customer commits with a date → set is_terminal: true
   - If customer commits but no date → ask for a date
   - If customer refuses → offer partial payment or plan
   - If unclear → ask clarifying question
   Loop up to 4 customer turns
        ↓
6. On terminal turn → Claude (extract_ptp) analyzes full transcript:
   - outcome: promise_made | refused | no_commitment
   - promise_date: resolved to absolute date (e.g. "tomorrow" → 2026-03-27)
   - promise_amount: extracted or defaults to amount owed
        ↓
7. Result saved to PostgreSQL, dashboard refreshes
```

### Outcome Types

| Outcome | Meaning |
|---------|---------|
| `promise_made` | Customer agreed to pay (has date + amount) |
| `refused` | Customer explicitly refused |
| `no_commitment` | Ambiguous — requires follow-up |

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
TWILIO_ACCOUNT_SID=your_twilio_account_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_PHONE_NUMBER=your_twilio_phone_number   # E.164 format: +1xxxxxxxxxx

ANTHROPIC_API_KEY=your_anthropic_api_key

DATABASE_URL=postgresql://user:password@localhost:5432/dbname

# Public URL where Twilio can reach your backend.
# Use your ngrok HTTPS URL (e.g. https://abc123.ngrok.io)
BASE_URL=https://your-ngrok-url
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

**Terminal 3 — Expose backend to Twilio:**
```bash
ngrok http 8000
```

Copy the ngrok HTTPS URL, set it as `BASE_URL` in your `.env`, then restart the backend.

### 4. Configure Twilio webhook

1. Go to [Twilio Console](https://console.twilio.com/) → Phone Numbers → Active Numbers
2. Click your number
3. Under **Voice & Fax → A Call Comes In**:
   - URL: `https://your-ngrok-url/voice`
   - Method: `HTTP POST`
4. Save

## Dashboard

Open `http://localhost:3000`

- **Control Panel** — set the phone number to call and the debt amount
- **Stats Bar** — totals by outcome
- **Call Table** — click any row to expand the full transcript
- Auto-refreshes every 10 seconds

**Outcome badge colors:**
- Green — `promise_made`
- Red — `refused`
- Gray — `no_commitment`

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/calls` | List all call records |
| `POST` | `/api/calls/initiate` | Trigger an outbound call |
| `GET` | `/api/config` | Get current config (phone, amount) |
| `PUT` | `/api/config` | Update a config value |
| `POST` | `/voice` | Twilio webhook — call entry point |
| `POST` | `/process-response` | Twilio webhook — customer speech |
| `POST` | `/call-status` | Twilio status callback |

## Database Schema

```sql
CREATE TABLE calls (
    id               SERIAL PRIMARY KEY,
    call_sid         TEXT,
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
│   ├── main.py            # FastAPI app, Twilio webhooks, call orchestration
│   ├── claude_agent.py    # Claude AI — agent_reply() and extract_ptp()
│   ├── db.py              # PostgreSQL operations
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── App.jsx        # Dashboard UI
│   │   └── App.css
│   └── package.json
├── docker-compose.yml
├── .env.example
└── README.md
```
