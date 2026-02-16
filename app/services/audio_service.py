import tempfile
import os
import logging
import requests
import urllib3
import cloudinary
import cloudinary.uploader
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib3._collections import HTTPHeaderDict
from app.core.config import settings

logger = logging.getLogger(__name__)

# Patch Cloudinary's internal urllib3 pool size globally
urllib3.PoolManager.__init__.__defaults__  # just to confirm it's available
_original_pool_manager = urllib3.PoolManager

class _PatchedPoolManager(_original_pool_manager):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("num_pools", 20)
        kwargs.setdefault("maxsize", 20)
        super().__init__(*args, **kwargs)

urllib3.PoolManager = _PatchedPoolManager


class AudioService:
    def __init__(self):
        self.api_key = settings.PHONAD_LAB_API_KEY

        cloudinary.config(
            cloud_name=settings.CLOUDINARY_CLOUD_NAME,
            api_key=settings.CLOUDINARY_API_KEY,
            api_secret=settings.CLOUDINARY_API_SECRET,
            timeout=300,
        )

        self._session = requests.Session()
        retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retry, pool_connections=20, pool_maxsize=20)
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)

        try:
            from gtts import gTTS
            self._gtts = gTTS
            self._gtts_available = True
        except ImportError:
            self._gtts_available = False

    def _split_text(self, text: str, max_chars: int = 450) -> list[str]:
        if len(text) <= max_chars:
            return [text]
        chunks, current = [], ""
        sentences = (
            text.replace("? ", "?|").replace("! ", "!|").replace(". ", ".|").split("|")
        )
        for s in sentences:
            if len(current) + len(s) <= max_chars:
                current += s
            else:
                if current:
                    chunks.append(current.strip())
                current = s
        if current:
            chunks.append(current.strip())
        return chunks

    def _generate_chunk_fonada(self, text: str) -> bytes:
        response = self._session.post(
            "https://api.fonada.ai/tts/generate-audio-large",
            json={"input": text, "voice": "Vaanee", "language": "English"},
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            timeout=120,
        )
        response.raise_for_status()
        return response.content

    def _generate_chunk_gtts(self, text: str) -> bytes:
        if not self._gtts_available:
            raise RuntimeError("No TTS provider available")
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        tmp.close()
        try:
            self._gtts(text=text, lang="en").save(tmp.name)
            with open(tmp.name, "rb") as f:
                return f.read()
        finally:
            if os.path.exists(tmp.name):
                os.unlink(tmp.name)

    def generate_audio(self, text: str) -> bytes:
        chunks = self._split_text(text)
        parts = []
        for chunk in chunks:
            try:
                parts.append(self._generate_chunk_fonada(chunk))
            except Exception as e:
                logger.warning("Fonada failed for chunk, falling back to gTTS: %s", e)
                parts.append(self._generate_chunk_gtts(chunk))
        return b"".join(parts)

    def save_audio_to_storage(self, audio_buffer: bytes, file_name: str) -> str:
        result = cloudinary.uploader.upload(
            audio_buffer,
            resource_type="video",
            public_id=f"tts/{file_name.replace('.mp3', '')}",
            format="wav",
            overwrite=True,
            invalidate=True,
            folder="tts",
        )
        return result["secure_url"]


audio_service = AudioService()