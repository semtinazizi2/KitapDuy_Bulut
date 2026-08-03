with open('tts_generator.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("r'(?<=[.!?])\s+|\n+'", "r'(?<=[.!?])\\s+|\\n+'")

with open('tts_generator.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Fixed newline in regex.')
