# app/services/caption_service.py
import requests
from app.core.config import settings
from app.services.rate_limiter import RateLimiter

caption_rate_limiter = RateLimiter(rpm=20)

class CaptionService:
    def __init__(self):
        self.deepgram_api_key = settings.DEEPGRAM_API_KEY

    @caption_rate_limiter
    def generate_captions(self, audio_url: str) -> dict:
        url = "https://api.deepgram.com/v1/listen"
        headers = {
            "Authorization": f"Token {self.deepgram_api_key}",
            "Content-Type": "application/json"
        }
        params = {
            "punctuate": "true",
            "utterances": "true",
            "timestamps": "true"
        }
        payload = {"url": audio_url}

        try:
            response = requests.post(url, headers=headers, params=params, json=payload, timeout=60)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"Deepgram error: {str(e)}")

caption_service = CaptionService()
