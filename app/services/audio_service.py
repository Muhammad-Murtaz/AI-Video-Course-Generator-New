# app/services/audio_service.py
from app.core.config import settings
import cloudinary
import logging
import cloudinary.uploader
import requests

import tempfile
import os


logger = logging.getLogger(__name__)


class AudioService:
    def __init__(self):
        self.phonad_lab_api_key = settings.PHONAD_LAB_API_KEY
        cloudinary.config(
            timeout=300,
            cloud_name=settings.CLOUDINARY_CLOUD_NAME,
            api_key=settings.CLOUDINARY_API_KEY,
            api_secret=settings.CLOUDINARY_API_SECRET,
        )
        self._init_fallback()

    def _init_fallback(self):
        try:
            from gtts import gTTS

            self.gtts = gTTS
            self.fallback_available = True
        except Exception:
            self.fallback_available = False

    def _split_text(self, text: str, max_chars: int = 450) -> list[str]:
        if len(text) <= max_chars:
            return [text]

        chunks = []
        sentences = (
            text.replace("? ", "?|").replace("! ", "!|").replace(". ", ".|").split("|")
        )
        current_chunk = ""

        for sentence in sentences:
            if len(current_chunk) + len(sentence) <= max_chars:
                current_chunk += sentence
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks

    def _generate_audio_fallback(self, text: str) -> bytes:
        if not self.fallback_available:
            raise Exception("Fallback TTS not available")

        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        temp_path = temp_file.name
        temp_file.close()

        try:
            tts = self.gtts(text=text, lang="en")
            tts.save(temp_path)

            with open(temp_path, "rb") as f:
                audio_data = f.read()

            return audio_data
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def _generate_audio_chunk(self, text: str) -> bytes:
        url = "https://api.fonada.ai/tts/generate-audio-large"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.phonad_lab_api_key}",
        }
        payload = {
            "input": text,
            "voice": "Vaanee",
            "language": "English",
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=120)
            response.raise_for_status()
            return response.content
        except Exception:
            return self._generate_audio_fallback(text)

    def generate_audio(self, text: str) -> bytes:
        chunks = self._split_text(text)

        if len(chunks) == 1:
            return self._generate_audio_chunk(chunks[0])

        audio_parts = [self._generate_audio_chunk(chunk) for chunk in chunks]
        return b"".join(audio_parts)

    def save_audio_to_storage(self, audio_buffer: bytes, file_name: str) -> str:
        try:
            upload_result = cloudinary.uploader.upload(
                audio_buffer,
                resource_type="video",
                public_id=f"tts/{file_name.replace('.mp3', '')}",
                format="wav",
                overwrite=True,
                invalidate=True,
                folder="tts",
            )
            return upload_result["secure_url"]
        except Exception as e:
            raise Exception(f"Cloudinary upload failed: {str(e)}")


audio_service = AudioService()
