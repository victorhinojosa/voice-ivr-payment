import io
import os
from pathlib import Path
from dotenv import load_dotenv
from elevenlabs.client import AsyncElevenLabs

env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

client = AsyncElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))

VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb")


async def synthesize_speech(text: str) -> bytes:
    """Turn agent reply text into audio bytes (mp3)."""
    audio_stream = client.text_to_speech.convert(
        text=text,
        voice_id=VOICE_ID,
        model_id="eleven_flash_v2_5",  
        output_format="mp3_44100_128",
    )
    chunks = [chunk async for chunk in audio_stream]
    return b"".join(chunks)


async def transcribe_speech(audio_bytes: bytes) -> str:
    """Transcribe one customer turn (a webm/opus blob from the browser's MediaRecorder)."""
    audio_file = io.BytesIO(audio_bytes)
    result = await client.speech_to_text.convert(
        file=audio_file,
        model_id="scribe_v1",
    )
    return (result.text or "").strip()