with open('main.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if line.strip() == 'import os' and len(line) - len(line.lstrip()) > 0:
        continue # skip indented import os
    if line.strip() == 'import time as _os' and len(line) - len(line.lstrip()) > 0:
        continue # skip indented import time as _os
    new_lines.append(line)

with open('main.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
print('Fixed internal imports.')
