import json
from anthropic import Anthropic
from typing import Optional
import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

INITIAL_PROMPT = """You are a debt collection negotiation AI.
Customer owes: {amount}
Customer transcript: {transcript}

Extract intent and propose a payment plan. Then create a SHORT confirmation question.

1. Intent: "willing_to_pay" | "needs_negotiation" | "refuses"
2. Payment plan: "X dollars per month for Y months"
3. Summary: One short sentence summarizing the plan
4. Confirmation question: Ask a simple YES/NO question
5. Confidence: 0-100%

Example:
{{"intent": "needs_negotiation", "payment_plan": "$150/month for 6 months", "summary": "I can set up monthly payments of one-fifty for six months.", "confirmation_question": "Does that work for you?", "confidence": 85}}

Respond as JSON:
{{"intent": "...", "payment_plan": "...", "summary": "...", "confirmation_question": "...", "confidence": 95}}"""

CONFIRMATION_PROMPT = """Analyze this YES/NO response to determine if the customer accepted the payment plan.

Customer said: "{response}"

Determine:
1. Answer: "yes" | "no" | "unclear"
2. Confidence: 0-100%

If unclear (confidence < 70), respond with "unclear".

Respond as JSON:
{{"answer": "...", "confidence": 85}}"""

async def process_initial_intent(transcript: str, amount_owed: float = 1000.0) -> dict:
    """
    Process caller's initial transcript to extract intent and propose payment plan.

    Args:
        transcript: The caller's speech converted to text
        amount_owed: Amount customer owes (default $1000 for MVP)

    Returns:
        dict with keys: intent, payment_plan, summary, confirmation_question, confidence
    """
    try:
        prompt = INITIAL_PROMPT.format(
            amount=f"${amount_owed:.2f}",
            transcript=transcript
        )

        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1024,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        # Parse Claude's response as JSON
        response_text = message.content[0].text
        result = json.loads(response_text)

        # Validate required fields
        return {
            "intent": result.get("intent", "unknown"),
            "payment_plan": result.get("payment_plan", ""),
            "summary": result.get("summary", "Let me help you with a payment plan."),
            "confirmation_question": result.get("confirmation_question", "Does that work for you?"),
            "confidence": result.get("confidence", 0)
        }

    except Exception as e:
        # Fallback response if Claude fails
        print(f"Claude API error: {e}")
        return {
            "intent": "error",
            "payment_plan": "",
            "summary": "I'm having trouble processing your request.",
            "confirmation_question": "Can I transfer you to a specialist?",
            "confidence": 0
        }

async def process_confirmation(response: str) -> dict:
    """
    Analyze customer's YES/NO response to payment plan.

    Args:
        response: Customer's spoken response

    Returns:
        dict with keys: answer ("yes"|"no"|"unclear"), confidence
    """
    try:
        prompt = CONFIRMATION_PROMPT.format(response=response)

        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=256,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        # Parse Claude's response as JSON
        response_text = message.content[0].text
        result = json.loads(response_text)

        answer = result.get("answer", "unclear")
        confidence = result.get("confidence", 0)

        # Force unclear if confidence is too low
        if confidence < 70:
            answer = "unclear"

        return {
            "answer": answer,
            "confidence": confidence
        }

    except Exception as e:
        print(f"Claude confirmation error: {e}")
        return {
            "answer": "unclear",
            "confidence": 0
        }
