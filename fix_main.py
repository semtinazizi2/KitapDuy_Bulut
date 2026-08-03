with open('main.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

start_idx = -1
end_idx = -1
for i, line in enumerate(lines):
    if 'if "test" in mode or mode == "t":' in line:
        if start_idx == -1:
            start_idx = i
    if 'total_paragraphs = len(paragraphs)' in line:
        end_idx = i
        break

if start_idx != -1 and end_idx != -1:
    new_lines = lines[:start_idx] + [
        '    if "test" in mode or mode == "t":\n',
        '        paragraphs = paragraphs[:3]\n',
        '        print(f"\\n[TEST MODU]: Kitabin sadece ilk {len(paragraphs)} parcasi islenecek.\\n")\n',
        '    else:\n',
        '        print(f"\\n[TAM SURUM]: Kitap toplam {len(paragraphs)} parcaya bolundu. Basliyoruz...\\n")\n',
        '        \n',
        '    # Klasor zaten yukarida olusturuldu\n',
        '    \n'
    ] + lines[end_idx:]
    with open('main.py', 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    print("Fixed.")
else:
    print("Indices not found.")
