# debug_audio_format.py
"""
Debug script to test what audio format the TTS API returns
Run this to diagnose the audio format issue
"""

import requests
import os
from dotenv import load_dotenv

load_dotenv()

def test_tts_api():
    """Test the TTS API and save the audio file for inspection"""
    
    api_key = os.getenv("PHONAD_LAB_API_KEY")
    
    if not api_key:
        print("❌ PHONAD_LAB_API_KEY not found in environment")
        return
    
    url = "https://api.fonada.ai/tts/generate-audio-large"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    payload = {
        "input": "Hello world, this is a test.",
        "voice": "Vaanee",
        "language": "English",
    }

    print("🔄 Testing TTS API...")
    print(f"URL: {url}")
    print(f"Payload: {payload}")
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=120)
        response.raise_for_status()
        
        audio_bytes = response.content
        
        print(f"\n✓ Request successful!")
        print(f"  Response status: {response.status_code}")
        print(f"  Content-Type: {response.headers.get('Content-Type')}")
        print(f"  Content-Length: {len(audio_bytes)} bytes")
        
        # Check file signature (magic bytes)
        if len(audio_bytes) > 12:
            first_bytes = audio_bytes[:12]
            print(f"  First 12 bytes: {first_bytes.hex()}")
            
            # Detect format by magic bytes
            if first_bytes[:4] == b'RIFF':
                print(f"  ➜ Format detected: WAV")
                ext = "wav"
            elif first_bytes[:3] == b'ID3' or first_bytes[:2] == b'\xff\xfb':
                print(f"  ➜ Format detected: MP3")
                ext = "mp3"
            elif first_bytes[:4] == b'OggS':
                print(f"  ➜ Format detected: OGG")
                ext = "ogg"
            elif first_bytes[:4] == b'fLaC':
                print(f"  ➜ Format detected: FLAC")
                ext = "flac"
            else:
                print(f"  ⚠️ Format unknown")
                ext = "bin"
        
        # Save to file for manual inspection
        output_file = f"test_audio.{ext}"
        with open(output_file, 'wb') as f:
            f.write(audio_bytes)
        
        print(f"\n✓ Audio saved to: {output_file}")
        print(f"  You can open this file to verify it plays correctly")
        
        return True
        
    except requests.exceptions.HTTPError as e:
        print(f"\n❌ HTTP Error: {e}")
        print(f"   Response: {e.response.text}")
        return False
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False

if __name__ == "__main__":
    test_tts_api()