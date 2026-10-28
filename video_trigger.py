import requests
import json
import os

def generate_video(topic):
    url = "http://127.0.0.1:8080/api/v1/videos"
    payload = {
        "video_subject": topic,
        "video_language": "te",
        "video_aspect": "9:16",
        "voice_name": "te-IN-ShrutiNeural"
    }
    headers = {"Content-Type": "application/json"}
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        if response.status_code == 200:
            print(f"✅ Video task started for: {topic}")
            return response.json()
        else:
            print(f"❌ Failed: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Error connecting to MoneyPrinterTurbo: {e}")
        return None

if __name__ == "__main__":
    generate_video("Puruṣārthas")