import os
import requests
import json
import asyncio
import edge_tts
from google import genai
from groq import Groq
import subprocess
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
SHEET_ID = "15t2x8TAnvw4KgSVdpViCZmFQ0oEBZk2DDD7AOS0dwcE"
CREDS_FILE = "/opt/agency/Jarvis-Agency-Office/google_sheets_key.json"

def get_topic():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID).sheet1
    
    rows = sheet.get_all_values()
    for i, row in enumerate(rows[1:], start=2):
        if len(row) > 10 and row[10].strip() == "Pending":
            topic = row[7].strip()
            sloka = row[5].strip()
            print(f"Found Topic: {topic}")
            return topic, sloka, sheet, i
    return None, None, sheet, None

def generate_script(topic, sloka):
    prompt = f"""
    Write a YouTube Shorts script STRICTLY IN TELUGU SCRIPT (తెలుగు). Do not use English letters.
    Topic: {topic}
    Sloka/Reference: {sloka}
    
    1. Read the sloka (if provided) or state the topic.
    2. Explain the meaning simply in Telugu.
    Format as a JSON list of scenes.
    Each scene must have:
    - 'text': (Telugu script ONLY, what the narrator says)
    - 'search_query': (1-3 English words to find a generic background video on Pexels, e.g., 'temple', 'meditation', 'nature')
    Keep it under 60 seconds.
    """
    
    try:
        print("Trying Gemini...")
        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model='gemini-3.8-flash',
            contents=prompt
        )
        text = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(text)
    except Exception as e:
        print(f"Gemini failed: {e}. Falling back to Groq...")
        
    try:
        groq_client = Groq(api_key=GROQ_API_KEY)
        chat_completion = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="openai/gpt-oss-120b",
        )
        text = chat_completion.choices[0].message.content
        text = text.replace('```json', '').replace('```', '').strip()
        return json.loads(text)
    except Exception as e:
        print(f"Groq also failed: {e}")
        raise Exception("Both Gemini and Groq failed to generate script.")

async def generate_audio(text, output_file):
    communicate = edge_tts.Communicate(text, "te-IN-ShrutiNeural")
    await communicate.save(output_file)

def fetch_video(query, output_file):
    url = f"https://api.pexels.com/videos/search?query={query}&per_page=1&orientation=portrait"
    headers = {"Authorization": PEXELS_API_KEY}
    response = requests.get(url, headers=headers).json()
    
    if response.get('videos'):
        video_url = response['videos'][0]['video_files'][0]['link']
        r = requests.get(video_url)
        with open(output_file, 'wb') as f:
            f.write(r.content)
        return True
    return False

def process_scene(scene_index, text, search_query):
    audio_file = f"audio_{scene_index}.mp3"
    video_file = f"video_{scene_index}.mp4"
    out_file = f"scene_{scene_index}.mp4"

    print(f"Processing Scene {scene_index}: {text}")
    
    asyncio.run(generate_audio(text, audio_file))
    
    if not fetch_video(search_query, video_file):
        print(f"Could not find video for {search_query}")
        return None
        
    # THIS IS THE FIXED FFMPEG COMMAND
    cmd = f'ffmpeg -y -stream_loop -1 -i {video_file} -i {audio_file} -c:v libx264 -c:a aac -shortest -vf "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920" {out_file}'
    subprocess.run(cmd, shell=True, check=True)
    
    return out_file

def main():
    topic, sloka, sheet, row_num = get_topic()
    if not topic:
        print("No pending topics.")
        return

    print("Generating script with Gemini/Groq...")
    script = generate_script(topic, sloka)
    
    scene_files = []
    for i, scene in enumerate(script):
        f = process_scene(i, scene['text'], scene['search_query'])
        if f: scene_files.append(f)
        
    with open("scenes.txt", "w") as f:
        for sf in scene_files:
            f.write(f"file '{sf}'\n")
            
    print("Stitching final video...")
    subprocess.run('ffmpeg -y -f concat -safe 0 -i scenes.txt -c copy final_video.mp4', shell=True, check=True)
    print("Video Generated: final_video.mp4")
    
    try:
        sheet.update_cell(row_num, 11, "Generated")
        print("Sheet updated successfully.")
    except Exception as e:
        print(f"Could not update sheet: {e}")

if __name__ == "__main__":
    main()