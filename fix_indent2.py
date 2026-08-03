with open('main.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i in range(len(lines)):
    if lines[i] == 'import time\n' and i > 0 and lines[i-1] == '    import glob\n':
        lines[i] = '    import time\n'

with open('main.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)
