import io
import os
from pathlib import Path

from dotenv import load_dotenv
from elevenlabs.client import AsyncElevenLabs

env_path = Path(__file__).resolve().parent.parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

client = AsyncElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))

VOICE_MAPPING = {
    "English": os.getenv("ELEVENLABS_VOICE_ID_EN", "JBFqnCBsd6RMkjVDRZzb"),
    "Spanish": os.getenv("ELEVENLABS_VOICE_ID_ES", "JBFqnCBsd6RMkjVDRZzb"),
}


async def synthesize_speech(text: str, language: str = "English") -> bytes:
    """
    Turn agent reply text into audio bytes (mp3).

    Args:
        text: The agent's message
        language: "English" or "Spanish" (default: "English")

    Returns:
        MP3 audio bytes
    """
    voice_id = VOICE_MAPPING.get(language, VOICE_MAPPING["English"])
    print(f"[DEBUG] synthesize_speech: language={language}, voice_id={voice_id}, text_len={len(text)}")

    audio_stream = client.text_to_speech.convert(
        text=text,
        voice_id=voice_id,
        model_id="eleven_flash_v2_5",
        output_format="mp3_44100_128",
    )
    chunks = [chunk async for chunk in audio_stream]
    audio_bytes = b"".join(chunks)
    print(f"[DEBUG] synthesize_speech: audio_bytes={len(audio_bytes)}")
    return audio_bytes


async def transcribe_speech(audio_bytes: bytes) -> str:
    """Transcribe one customer turn (a webm/opus blob from the browser's MediaRecorder)."""
    audio_file = io.BytesIO(audio_bytes)
    result = await client.speech_to_text.convert(
        file=audio_file,
        model_id="scribe_v1",
    )
    return (result.text or "").strip()