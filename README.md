# Voice IVR Payment Negotiation System

A voice AI system for automated debt collection where the bank calls customers to propose payment plans and negotiate terms using Twilio, Claude AI, and speech recognition.

## Overview

This system enables banks to make outbound calls to customers with outstanding balances, propose payment plans, and intelligently process customer responses in real-time.

## Features

- **Outbound Voice Calls**: Bank-initiated calls with professional greeting
- **AI-Powered Intent Detection**: Claude analyzes customer responses in real-time
- **Smart Conversation Flow**: Handles yes/no responses, clarifications, and negotiations
- **Real-time Dashboard**: Monitor all calls, intents, and outcomes
- **Single Call Record**: Updates conversation state without creating duplicates

## Tech Stack

- **Backend**: Python FastAPI
- **Telephony**: Twilio Programmable Voice
- **AI Agent**: Claude 3.5 Sonnet (Anthropic)
- **Database**: SQLite
- **Frontend**: React
- **Deployment**: Docker

## Quick Start

### 1. Install Dependencies

**Backend:**
```bash
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1  # Windows
source venv/bin/activate      # Mac/Linux
pip install -r requirements.txt
```

**Frontend:**
```bash
cd frontend
npm install
```

### 2. Configure Environment

Create `.env` in the root directory:

```env
TWILIO_ACCOUNT_SID=your_twilio_sid
TWILIO_AUTH_TOKEN=your_twilio_token
TWILIO_PHONE_NUMBER=your_twilio_number
ANTHROPIC_API_KEY=your_anthropic_key
```

### 3. Run Locally

**Terminal 1 - Backend:**
```bash
cd backend
python main.py
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm start
```

**Terminal 3 - Expose Backend:**
```bash
ngrok http 8000
```

### 4. Configure Twilio Webhook

1. Copy your ngrok HTTPS URL
2. Go to [Twilio Console](https://console.twilio.com/) → Phone Numbers → Active Numbers
3. Click your number
4. Under "Voice & Fax" → "A CALL COMES IN":
   - URL: `https://your-ngrok-url.ngrok.io/voice`
   - Method: `HTTP POST`
5. Save

## How It Works

### Call Flow

1. **Bank Calls Customer**
   - System: "Hello, this is a courtesy call regarding your outstanding balance of $1,000. We'd like to propose a payment plan of $200 per month for 5 months. Would this arrangement work for you?"

2. **Customer Responds**
   - **"Yes" / "I agree"** → Intent: `willing_to_pay`, Status: `confirmed`
   - **"No" / "I can't afford that"** → Intent: `needs_negotiation`, Status: `needs_negotiation`
   - **"Can you repeat?"** → System repeats offer, waits for response

3. **System Acts**
   - Confirmed: "Excellent! We've confirmed your payment plan..."
   - Declined: "I understand. Let me connect you with a specialist..."
   - Unclear: Repeats offer and continues conversation

### Intent Categories

| Intent | Description | Status |
|--------|-------------|--------|
| `willing_to_pay` | Customer accepts the payment plan | `confirmed` |
| `needs_negotiation` | Customer declines or can't afford | `needs_negotiation` |
| `unclear` | Response needs clarification | `pending_clarification` |
| `no_response` | Customer doesn't respond | `no_response` |

## Project Structure

```
mvp/
├── backend/
│   ├── main.py              # FastAPI app + webhook endpoints
│   ├── claude_agent.py      # Claude AI integration
│   ├── db.py                # SQLite operations
│   ├── migrate_db.py        # Database migration script
│   ├── requirements.txt     # Python dependencies
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── App.jsx          # Dashboard component
│   │   └── App.css          # Styling
│   └── package.json
├── .env.example             # Environment template
├── .gitignore
└── README.md
```

## API Endpoints

- `GET/POST /voice` - Twilio webhook entry point
- `POST /process-response` - Handles customer responses
- `GET /api/calls` - Returns call logs for dashboard

## Database Schema

```sql
CREATE TABLE calls (
    id INTEGER PRIMARY KEY,
    timestamp TEXT,
    caller_phone TEXT,
    transcript TEXT,              -- Full conversation transcript
    intent TEXT,                  -- willing_to_pay | needs_negotiation | unclear
    payment_plan TEXT,            -- "$200/month for 5 months"
    reply_text TEXT,              -- System's response
    confidence INTEGER,           -- 0-100
    status TEXT,                  -- confirmed | needs_negotiation | pending_clarification
    confirmation_response TEXT,   -- yes | no | unclear
    retry_count INTEGER
);
```

## Testing

### Test Scenarios

1. **Acceptance Test**
   - Call your number
   - Say "Yes, I accept"
   - Dashboard shows: `willing_to_pay`, status `confirmed`

2. **Decline Test**
   - Call your number
   - Say "No, I can't afford that"
   - Dashboard shows: `needs_negotiation`

3. **Clarification Test**
   - Call your number
   - Say "Can you repeat the plan?"
   - System repeats, waits for response
   - Say "Yes"
   - Dashboard shows ONE record with both responses in transcript

### Checking Logs

Backend logs show detailed conversation flow:
```
[DEBUG] ========== PROCESSING CUSTOMER RESPONSE ==========
[DEBUG] Customer: +1234567890
[DEBUG] Response: 'Yes'
[DEBUG] Claude analysis: answer='yes', confidence=95
[DEBUG] ✓ Customer ACCEPTED offer → intent='willing_to_pay', status='confirmed'
```

## Dashboard

Access at `http://localhost:3000`

**Features:**
- Summary statistics (total calls, willing to pay, negotiating)
- Call log table with color-coded intent badges
- Click rows to expand and view full transcript
- Auto-refreshes every 10 seconds

**Intent Badge Colors:**
- 🟢 Willing To Pay (green)
- 🟡 Needs Negotiation (orange)
- 🔵 Pending Clarification (blue)
- ⚪ No Response (gray)

## Configuration

### Changing Payment Plan Offer

Edit `backend/main.py` line 88-89:
```python
offered_plan = "$200/month for 5 months"  # Change here
amount_owed = 1000.0                       # Change debt amount
```

### Adjusting Call Greeting

Edit `backend/main.py` lines 60-64:
```python
gather.say(
    "Your custom greeting here...",
    voice="Polly.Joanna"
)
```

