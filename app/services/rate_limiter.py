# app/services/rate_limiter.py
import time
import threading
from functools import wraps

class RateLimiter:
    def __init__(self, rpm: int):
        self.rpm = rpm
        self.interval = 60.0 / rpm
        self.last_call = 0
        self.lock = threading.Lock()
    
    def wait_if_needed(self):
        with self.lock:
            current = time.time()
            elapsed = current - self.last_call
            if elapsed < self.interval:
                time.sleep(self.interval - elapsed)
            self.last_call = time.time()
    
    def __call__(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            self.wait_if_needed()
            return func(*args, **kwargs)
        return wrapper

gemini_rate_limiter = RateLimiter(rpm=15)
audio_rate_limiter = RateLimiter(rpm=10)