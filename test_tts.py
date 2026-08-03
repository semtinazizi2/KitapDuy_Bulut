import os
from dotenv import load_dotenv
load_dotenv('C:\\Users\\Rahmi\\Desktop\\KitapDuy_Otomasyon\\.env')
from google import genai
from google.genai import types

keys = os.getenv('GEMINI_API_KEYS').split(',')
client = genai.Client(api_key=keys[0])

script = """## THE SCENE: A dark room
### SAMPLE CONTEXT: Sad
#### TRANSCRIPT
Merhaba dünya. Bugün çok üzgünüm."""

tts_prompt = f"Please read the following transcript aloud. Use the scene and context to influence your emotional tone, but only output audio for the transcript.\n\n{script}"

response = client.models.generate_content(
    model='gemini-2.5-flash-preview-tts',
    contents=tts_prompt,
    config=types.GenerateContentConfig(response_modalities=['AUDIO'])
)

audio_data = b''
for p in response.candidates[0].content.parts:
    audio_data += p.inline_data.data

import wave
wf = wave.open('C:\\Users\\Rahmi\\Desktop\\KitapDuy_Otomasyon\\test2.wav', 'wb')
wf.setnchannels(1)
wf.setsampwidth(2)
wf.setframerate(24000)
wf.writeframes(audio_data)
wf.close()

import struct
import math
frames = audio_data
count = len(frames)//2
shorts = struct.unpack('h'*count, frames)
rms = math.sqrt(sum(s*s for s in shorts)/count) if count > 0 else 0
print(f'Duration: {count/24000:.2f}s, RMS: {rms:.2f}')
