"""
audio_service.py
- ImageKit new SDK: only private_key in __init__ (public_key & url_endpoint removed)
- TTS: gTTS only for now (Fonada commented out — re-enable when rate limits resolved)
"""

import tempfile
import os
import logging
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from app.core.config import settings

logger = logging.getLogger(__name__)

# ── Patch urllib3 pool BEFORE ImageKit imports it ────────────────────────────
import urllib3

_orig_pool_manager_init = urllib3.PoolManager.__init__


def _patched_pool_manager_init(self, *args, **kwargs):
    kwargs.setdefault("num_pools", 20)
    kwargs.setdefault("maxsize", 20)
    _orig_pool_manager_init(self, *args, **kwargs)


urllib3.PoolManager.__init__ = _patched_pool_manager_init

# ── ImageKit (new SDK v5+: only private_key accepted in __init__) ─────────────
from imagekitio import ImageKit


class AudioService:
    def __init__(self):
        # ✅ New SDK only accepts private_key — public_key & url_endpoint removed
        self._imagekit = ImageKit(
            private_key=settings.IMAGE_PRIVATE_KEY,
        )

        # ── Fonada disabled for now (429 rate limits) ─────────────────────────
        # To re-enable: uncomment the session block and _generate_chunk_fonada,
        # and swap generate_audio() back to try Fonada first.
        #
        # self.fonada_api_key = settings.PHONAD_LAB_API_KEY
        # self._session = requests.Session()
        # retry = Retry(
        #     total=3,
        #     backoff_factor=1,
        #     status_forcelist=[500, 502, 503, 504],
        #     allowed_methods=["POST", "GET"],
        # )
        # adapter = HTTPAdapter(max_retries=retry, pool_connections=20, pool_maxsize=20)
        # self._session.mount("https://", adapter)
        # self._session.mount("http://", adapter)

        try:
            from gtts import gTTS

            self._gtts = gTTS
            self._gtts_available = True
        except ImportError:
            self._gtts_available = False
            logger.warning("gTTS not installed — pip install gtts")

    # ── Text splitting ────────────────────────────────────────────────────────

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

    # ── Fonada (commented out — re-enable when ready) ─────────────────────────

    # import time
    # def _generate_chunk_fonada(self, text: str, max_attempts: int = 4) -> bytes:
    #     """Exponential backoff on 429: waits 2s → 4s → 8s before giving up."""
    #     for attempt in range(max_attempts):
    #         response = self._session.post(
    #             "https://api.fonada.ai/tts/generate-audio-large",
    #             json={"input": text, "voice": "Vaanee", "language": "English"},
    #             headers={
    #                 "Content-Type": "application/json",
    #                 "Authorization": f"Bearer {self.fonada_api_key}",
    #             },
    #             timeout=120,
    #         )
    #         if response.status_code == 429:
    #             wait = 2 ** (attempt + 1)
    #             logger.warning("Fonada 429 — waiting %ds (attempt %d/%d)", wait, attempt + 1, max_attempts)
    #             time.sleep(wait)
    #             continue
    #         response.raise_for_status()
    #         return response.content
    #     raise RuntimeError("Fonada returned 429 after all retries")

    # ── gTTS ──────────────────────────────────────────────────────────────────

    def _generate_chunk_gtts(self, text: str) -> bytes:
        if not self._gtts_available:
            raise RuntimeError("gTTS not available — pip install gtts")
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        tmp.close()
        try:
            self._gtts(text=text, lang="en").save(tmp.name)
            with open(tmp.name, "rb") as f:
                return f.read()
        finally:
            if os.path.exists(tmp.name):
                os.unlink(tmp.name)

    # ── Main generate (gTTS only) ─────────────────────────────────────────────

    def generate_audio(self, text: str) -> bytes:
        chunks = self._split_text(text)
        parts = []
        for chunk in chunks:
            # To re-enable Fonada: wrap _generate_chunk_gtts in a try/except
            # and call _generate_chunk_fonada first (see commented block above)
            parts.append(self._generate_chunk_gtts(chunk))
        return b"".join(parts)

    # ── Upload to ImageKit ────────────────────────────────────────────────────

    def save_audio_to_storage(self, audio_buffer: bytes, file_name: str) -> str:
        """
        Upload audio bytes to ImageKit.
        New SDK (v5+): imagekit.files.upload() with kwargs — no UploadFileRequestOptions.
        """
        clean_name = file_name.replace(".mp3", "")

        result = self._imagekit.files.upload(
            file=audio_buffer,
            file_name=f"{clean_name}.mp3",
            folder="/tts",
            overwrite_file=True,
            is_published=True,
        )

        url = result.url
        if not url:
            raise RuntimeError(
                f"ImageKit upload failed: {getattr(result, 'error', 'unknown error')}"
            )

        logger.info("Uploaded audio to ImageKit: %s", url)
        return url

    # ── Parallel uploads ──────────────────────────────────────────────────────

    def save_multiple_audios(self, files: list[tuple[bytes, str]]) -> list[str | None]:
        """
        Upload multiple (audio_bytes, file_name) pairs concurrently.
        ImageKit has no bulk endpoint — parallelized with ThreadPoolExecutor.
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        results: list[str | None] = [None] * len(files)
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_idx = {
                executor.submit(self.save_audio_to_storage, audio, name): idx
                for idx, (audio, name) in enumerate(files)
            }
            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    results[idx] = future.result()
                except Exception as e:
                    logger.error("Failed to upload file at index %d: %s", idx, e)
                    results[idx] = None

        return results


audio_service = AudioService()
