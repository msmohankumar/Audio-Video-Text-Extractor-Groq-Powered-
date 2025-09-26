import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

def transcribe_audio_groq(audio_path):
    client = Groq(api_key=GROQ_API_KEY)
    with open(audio_path, "rb") as file:
        transcript = client.audio.transcriptions.create(
            file=file,
            model="whisper-large-v3-turbo",
            response_format="text",
            language="en",
            temperature=0.0
        )
        # Handle different response formats
        if hasattr(transcript, 'text'):
            return transcript.text
        if isinstance(transcript, dict) and "text" in transcript:
            return transcript["text"]
        return str(transcript)
