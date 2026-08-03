with open('tts_generator.py', 'r', encoding='utf-8') as f:
    content = f.read()

import re
content = content.replace("sentences = re.split(r'(?<=[.!?])\s+', transcript_text)", "sentences = re.split(r'(?<=[.!?])\s+|\n+', transcript_text)")

with open('tts_generator.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Regex fixed.')
