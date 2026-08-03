with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the broken indentation and bad imports
content = content.replace('            import os\nimport time', '            import os\n            import time')
content = content.replace('            import os\nimport time as _os', '            import os\n            import time as _os')

# Wait, let's just use Python to format it properly.
lines = content.split('\n')
for i in range(len(lines)):
    if lines[i] == 'import time' and i > 0 and lines[i-1].startswith('            import os'):
        lines[i] = '            import time'
    elif lines[i] == 'import time as _os' and i > 0 and lines[i-1].startswith('            import os'):
        lines[i] = '            import time as _os'

with open('main.py', 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))
print('Fixed indentation.')
