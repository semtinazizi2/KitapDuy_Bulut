with open('tts_generator.py', 'r', encoding='utf-8') as f:
    content = f.read()
content = content.replace('if len(current_chunk) + len(sentence) < 4000:', 'if len(current_chunk) + len(sentence) < 900:')
with open('tts_generator.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Fixed TTS sub-chunk limit.')
