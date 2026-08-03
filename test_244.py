import sys, os
sys.path.insert(0, '.')
from book_fetcher import BookFetcher
from tts_generator import TTSGenerator

print('=== KİTAP 244 TEST RAPORU ===')
print()

# Fetcher başlat
fetcher = BookFetcher()

# Kitabı indir
print('Kitap indiriliyor...')
raw_text = fetcher.download_gutenberg_book('244')
if not raw_text:
    print('HATA: Kitap indirilemedi!')
    sys.exit(1)

print(f'Kitap indirildi. Toplam karakter: {len(raw_text)}')

# Paragrafları al
paragraphs = fetcher.split_into_paragraphs(raw_text)
print(f'Toplam paragraf: {len(paragraphs)}')

# İlk 3 paragrafı test et
test_paragraphs = paragraphs[:3]
print()
print('--- İLK 3 PARAGRAF (İngilizce ham metin) ---')
for i, p in enumerate(test_paragraphs):
    print(f'[{i+1}] {p[:200]}')
    print()

# Çeviri testi
print('--- ÇEVİRİ KALİTE TESTİ ---')
sliding_window_buffer = []
translations = []
for i, p in enumerate(test_paragraphs):
    prev_ctx = '\n\n'.join(sliding_window_buffer)
    try:
        tr = fetcher.translate_to_turkish(p, previous_context=prev_ctx)
        translations.append(tr)
        print(f'[Paragraf {i+1}] ÇEVİRİ ✅')
        print(tr[:300])
        sliding_window_buffer.append(p[:300])
        if len(sliding_window_buffer) > 3:
            sliding_window_buffer.pop(0)
    except Exception as e:
        print(f'[Paragraf {i+1}] ÇEVİRİ HATASI ❌: {e}')
        translations.append(None)
    print()

# TTS Testi - sadece ilk paragraf
print('--- SES ÜRETİM TESTİ (Paragraf 1) ---')
if translations and translations[0]:
    book_output_dir = os.path.join('output_audio', '244_test')
    os.makedirs(book_output_dir, exist_ok=True)
    config_path = os.path.join('output_audio', '244', 'book_config.json')
    if not os.path.exists(config_path):
        config_path = 'book_config.json'
    
    tts = TTSGenerator(config_path=config_path)
    test_audio_path = os.path.join(book_output_dir, 'test_paragraf_01.wav')
    
    result = tts.generate_audio(translations[0], test_audio_path)
    if result:
        size = os.path.getsize(result)
        print(f'Ses üretildi ✅: {result} ({size//1024} KB)')
    else:
        print('Ses üretimi başarısız ❌')
else:
    print('Çeviri olmadığı için ses testi atlandı.')

print()
print('=== TEST TAMAMLANDI ===')
