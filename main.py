import os
import time
from book_fetcher import BookFetcher
from tts_generator import TTSGenerator
from qa_checker import QAChecker
from publisher import BookPublisher
import requests
import json

GLOBAL_START_TIME = time.time()
os.environ["GLOBAL_START_TIME"] = str(GLOBAL_START_TIME)
ORACLE_URL = "http://158.180.24.79:5000"
TELEMETRY_TOKEN = os.environ.get("TELEMETRY_TOKEN", "super_secret_kitapduy_token")

import builtins

def remote_print(*args, **kwargs):
    msg = " ".join(str(a) for a in args)
    builtins.print(msg)
    try:
        headers = {"Authorization": f"Bearer {TELEMETRY_TOKEN}", "Content-Type": "application/json"}
        requests.post(f"{ORACLE_URL}/api/telemetry/log", headers=headers, json={"message": msg}, timeout=3)
    except:
        pass

print = remote_print

def update_telemetry(book_id, book_title, current_chunk, total_chunks, voice, latest_audio_url=None):
    try:
        headers = {"Authorization": f"Bearer {TELEMETRY_TOKEN}", "Content-Type": "application/json"}
        pct = (current_chunk / total_chunks) * 100 if total_chunks > 0 else 0
        data = {
            "book_id": str(book_id),
            "book_title": str(book_title),
            "current_chunk": current_chunk,
            "total_chunks": total_chunks,
            "progress_pct": pct,
            "voice": str(voice)
        }
        if latest_audio_url:
            data["latest_audio_url"] = latest_audio_url
            
        requests.post(f"{ORACLE_URL}/api/telemetry/job", headers=headers, json=data, timeout=3)
    except Exception as e:
        pass # Ignore telemetry errors so it doesn't break the main loop

def main():
    print("====================================================")
    print("   K├âÔÇŞ├é┬░TAPDUY OTOMAT├âÔÇŞ├é┬░K SESL├âÔÇŞ├é┬░ K├âÔÇŞ├é┬░TAP ├âãÆ├àÔÇ£RET├âÔÇŞ├é┬░M S├âÔÇŞ├é┬░STEM├âÔÇŞ├é┬░")
    print("====================================================\n")
    
    print("====================================================\n")
    
    print("Sisteme bir kitap eklemek i├âãÆ├é┬ğin ├âãÆ├é┬╝├âãÆ├é┬ğ se├âãÆ├é┬ğene├âÔÇŞ├à┬©iniz var:")
    print("1) Sadece Project Gutenberg numaras├âÔÇŞ├é┬▒n├âÔÇŞ├é┬▒ yaz├âÔÇŞ├é┬▒n (├âãÆ├óÔé¼ÔÇ£rn: 11)")
    print("2) Klas├âãÆ├é┬Âr├âãÆ├é┬╝n i├âãÆ├é┬ğindeki kendi metin dosyan├âÔÇŞ├é┬▒z├âÔÇŞ├é┬▒n ad├âÔÇŞ├é┬▒n├âÔÇŞ├é┬▒ yaz├âÔÇŞ├é┬▒n (├âãÆ├óÔé¼ÔÇ£rn: benim_kitabim.txt)")
    print("3) ├âÔÇŞ├é┬░nternetten do├âÔÇŞ├à┬©rudan URL yap├âÔÇŞ├é┬▒├âÔÇĞ├à┬©t├âÔÇŞ├é┬▒r├âÔÇŞ├é┬▒n (├âãÆ├óÔé¼ÔÇ£rn: https://standardebooks.org/...) \n")
    
    book_source = os.environ.get("BOOK_SOURCE")
    if not book_source:
        book_source = input("L├âãÆ├é┬╝tfen Kitap ID'sini, Dosya Ad├âÔÇŞ├é┬▒n├âÔÇŞ├é┬▒ veya URL'yi girin: ").strip()
        
    mode = os.environ.get("BOOK_MODE")
    if not mode:
        mode = input("Sadece k├âÔÇŞ├é┬▒sa bir 'Test' (├âÔÇŞ├é┬░lk 3 paragraf) mi yapmak istersiniz, yoksa kitab├âÔÇŞ├é┬▒n 'Tamam├âÔÇŞ├é┬▒n├âÔÇŞ├é┬▒' m├âÔÇŞ├é┬▒? (Test/Tamam├âÔÇŞ├é┬▒): ").strip().lower()
    
def process_book(book_source, mode):
    import os
    ENABLE_QA = False
    print(f"\n================ YEN─░ K─░TAP ({book_source}) BA┼ŞLIYOR ====================")
    print("\nAd├âÔÇŞ├é┬▒m 1: Mod├âãÆ├é┬╝ller ba├âÔÇĞ├à┬©lat├âÔÇŞ├é┬▒l├âÔÇŞ├é┬▒yor (Bu i├âÔÇĞ├à┬©lem birka├âãÆ├é┬ğ saniye s├âãÆ├é┬╝rebilir)...")
    try:
        fetcher = BookFetcher()
        
        raw_text = ""
        if book_source.startswith("http://") or book_source.startswith("https://"):
            print(f"\nAd├âÔÇŞ├é┬▒m 2: Web sitesinden kitap ├âãÆ├é┬ğekiliyor ({book_source})...")
            raw_text = fetcher.download_from_url(book_source)
            # URL'den sabit ve okunabilir klas├âãÆ├é┬Âr ad├âÔÇŞ├é┬▒ ├âãÆ├é┬╝ret (hash de├âÔÇŞ├à┬©il, URL dosya ad├âÔÇŞ├é┬▒)
            from urllib.parse import urlparse
            url_path = urlparse(book_source).path
            url_filename = _os.path.basename(url_path)          # ├âãÆ├é┬Ârn: 0100021h.html
            url_filename = _os.path.splitext(url_filename)[0]   # ├âãÆ├é┬Ârn: 0100021h
            book_folder_name = "url_" + url_filename            # ├âãÆ├é┬Ârn: url_0100021h
        elif book_source.endswith(".txt") and os.path.exists(book_source):
            print(f"\nAd├âÔÇŞ├é┬▒m 2: Yerel dosya okunuyor ({book_source})...")
            with open(book_source, "r", encoding="utf-8") as f:
                raw_text = f.read()
            book_folder_name = book_source.replace(".txt", "")
        else:
            print(f"\nAd├âÔÇŞ├é┬▒m 2: Kitap indiriliyor (Project Gutenberg ID: {book_source})...")
            raw_text = fetcher.download_gutenberg_book(book_source)
            book_folder_name = book_source
            
        if not raw_text:
            print("HATA: Kitap metni al├âÔÇŞ├é┬▒namad├âÔÇŞ├é┬▒. Dosya ad├âÔÇŞ├é┬▒n├âÔÇŞ├é┬▒, URL'yi veya Gutenberg ID'sini kontrol edin.")
            return
        # Her kitap i├âãÆ├é┬ğin ayr├âÔÇŞ├é┬▒ bir klas├âãÆ├é┬Âr olu├âÔÇĞ├à┬©tur ve haf├âÔÇŞ├é┬▒zay├âÔÇŞ├é┬▒ oraya kaydet
        book_output_dir = os.path.join(os.getenv("OUTPUT_DIR", "output_audio"), book_folder_name)
        os.makedirs(book_output_dir, exist_ok=True)
        
        config_path = os.path.join(book_output_dir, "book_config.json")
        
        # Kitap Haf├âÔÇŞ├é┬▒zas├âÔÇŞ├é┬▒ (Voice Continuity)
        if os.path.exists(config_path):
            print(f"\n[B├âÔÇŞ├é┬░LG├âÔÇŞ├é┬░] Bu kitab├âÔÇŞ├é┬▒n eski spiker haf├âÔÇŞ├é┬▒zas├âÔÇŞ├é┬▒ bulundu. Ses tonu (Voice) de├âÔÇŞ├à┬©i├âÔÇĞ├à┬©tirilmeden orijinal spikerle devam edilecek!")
        else:
            fetcher.analyze_and_save_book_config(raw_text[:3000], config_path)
        tts = TTSGenerator(config_path=config_path)
        qa = QAChecker(is_enabled=ENABLE_QA)
    except Exception as e:
        print(f"Mod├âãÆ├é┬╝l ba├âÔÇĞ├à┬©latma hatas├âÔÇŞ├é┬▒: {e}\nL├âãÆ├é┬╝tfen .env dosyan├âÔÇŞ├é┬▒z├âÔÇŞ├é┬▒ kontrol edin.")
        return
    # Kitap bilgileri zaten fetcher taraf─▒ndan al─▒nd─▒ (ba┼şar─▒s─▒z olsa da "Bilinmeyen" ile devam edilir)
    # ─░kinci kez API ├ğa─ş─▒r─▒p hesaplar─▒ yakmamak i├ğin tekrar sorulmaz!
    if hasattr(fetcher, 'book_title') and fetcher.book_title:
        original_book_title = fetcher.book_title
        book_title = fetcher.book_title
        book_author = getattr(fetcher, 'book_author', 'Bilinmeyen Yazar')
    else:
        # Fallback: Kitap ID'sinden isim t├╝ret
        original_book_title = f"Kitap {book_source}"
        book_title = original_book_title
        book_author = "Bilinmeyen Yazar"
        
    print(f"[B├âÔÇŞ├é┬░LG├âÔÇŞ├é┬░] Eser Tespit Edildi: '{book_title}' - Yazar: {book_author}")
    
    import json
    metadata_path = os.path.join(book_output_dir, "metadata.json")
    
    # E─şer daha ├Ânce T├╝rk├ğe ba┼şl─▒k ├ğevrilip kaydedildiyse oradan oku, yoksa ├ğevir
    if os.path.exists(metadata_path):
        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                saved_meta = json.load(f)
                book_title = saved_meta.get("title", book_title)
        except Exception:
            pass
    else:
        print("[B─░LG─░] Kitap ad─▒ T├╝rk├ğeye ├ğevriliyor...")
        try:
            translated_title = fetcher.translate_to_turkish(f"The title of the book is '{book_title}'. Translate ONLY this title to Turkish. If it is already Turkish or a proper name that shouldn't be translated, keep it as is. Do not add any punctuation or extra text.", previous_context="")
            if len(translated_title) > 80 or translated_title.strip() == "":
                translated_title = book_title
            book_title = translated_title.strip()
            
            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump({"title": book_title, "author": book_author}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[UYARI] Kitap ad─▒ ├ğevrilemedi: {e}")
    fetcher.check_and_warn_copyright(raw_text, book_title, book_author, source=book_source)
    
    # --- K─░TAPDUY UYGULAMASI VER─░TABANI KONTROL├£ ---
    # E─şer kitap zaten uygulamada varsa (─░sim e┼şle┼şiyorsa) bo┼şuna ├╝retmemek i├ğin atlar─▒z
    try:
        import firebase_admin
        from firebase_admin import firestore
        from firebase_setup import get_firebase_cred
        if not firebase_admin._apps:
            cred = get_firebase_cred()
            firebase_admin.initialize_app(cred)
        db = firestore.client()
        existing = db.collection("books").where("title", "==", book_title).limit(1).get()
        if len(existing) > 0:
            print(f"\n[B─░LG─░] '{book_title}' zaten KitapDuy uygulamas─▒nda MECUT! Bu kitap atlan─▒p yenisine ge├ğilecek...")
            with open("completed_books.txt", "a", encoding="utf-8") as f:
                f.write(f"{book_source}\n")
            return True # Otonom d├Âng├╝ hata san─▒p 5 dk beklemesin, hemen yenisine ge├ğsin
    except Exception as e:
        print(f"[UYARI] Uygulama veritaban─▒ kontrol├╝ yap─▒lamad─▒: {e}")
        
    paragraphs = fetcher.split_into_paragraphs(raw_text)
    
    if "test" in mode or mode == "t":
        paragraphs = paragraphs[:3]
        print(f"\n[TEST MODU]: Kitabin sadece ilk {len(paragraphs)} parcasi islenecek.\n")
    else:
        print(f"\n[TAM SURUM]: Kitap toplam {len(paragraphs)} parcaya bolundu. Basliyoruz...\n")
        
    # Klasor zaten yukarida olusturuldu
    
    total_paragraphs = len(paragraphs)
    print(f"\n[B├ä┬░LG├ä┬░] Kitap ba├à┼©ar├ä┬▒yla {total_paragraphs} par├â┬ğaya (b├â┬Âl├â┬╝me) ayr├ä┬▒ld├ä┬▒. ├ä┬░├à┼©lem ba├à┼©l├ä┬▒yor...\n")
    # ├â┼ôCRETS├ä┬░Z S├â┼ôRG├â┼ôL├â┼ô HAFIZA (Sliding Window Buffer)
    sliding_window_buffer = []
    start_time = GLOBAL_START_TIME
    for i, p in enumerate(paragraphs):
        # 6 SAAT T├ä┬░MER KONTROL├â┼ô (G├ä┬░THUB ACT├ä┬░ONS F├ä┬░├à┬Ş ├âÔÇíEKMEDEN KA├âÔÇíI├à┬Ş)
        if time.time() - start_time > (5 * 3600 + 30 * 60):  # 5 saat 30 dakika
            print("\n!!! D├ä┬░KKAT: GitHub'├ä┬▒n 6 saatlik maksimum s├â┬╝resine yakla├à┼©├ä┬▒ld├ä┬▒! !!!")
            print("Sistem fi├à┼© ├â┬ğekilmeden ├â┬Ânce uyan├ä┬▒yor, verileri G├â┼ôVENLE kasaya kaydedip uykuya ge├â┬ğiyor.")
            print("L├â┬╝tfen g├â┬Ârevi (Run workflow) tekrar ba├à┼©latarak kald├ä┬▒├ä┼©├ä┬▒ yerden devam ediniz.")
            break
        progress_pct = (i / total_paragraphs) * 100
        print(f"--- BÖLÜM {i+1} / {total_paragraphs} (%{progress_pct:.1f} Tamamlandı) ---")
        
        # UI'a Anında Bildir
        try:
            voice_name = tts.config.get("voice", "Bilinmiyor")
            update_telemetry(book_source, book_title, i+1, total_paragraphs, voice_name)
        except:
            pass
        
        filename = f"bolum_{i+1:03d}.mp3"
        audio_path = os.path.join(book_output_dir, filename)
        
        # Kald├ä┬▒├ä┼©├ä┬▒ yerden devam etme mant├ä┬▒├ä┼©├ä┬▒
        if os.path.exists(audio_path) or os.path.exists(audio_path.replace('.mp3', '.wav')):
            print(f"[{filename}] veya WAV hali zaten mevcut. Kotay├âÔÇŞ├é┬▒ korumak i├âãÆ├é┬ğin atlan├âÔÇŞ├é┬▒yor...")
            print("------------------\n")
            continue
        
        # 1. ├âãÆ├óÔé¼┬íeviri
        print("├âãÆ├óÔé¼┬íevirisi yap├âÔÇŞ├é┬▒l├âÔÇŞ├é┬▒yor...")
        
        # Ge├âãÆ├é┬ğmi├âÔÇĞ├à┬© ba├âÔÇŞ├à┬©lam├âÔÇŞ├é┬▒ d├âãÆ├é┬╝z metne ├âãÆ├é┬ğevir (E├âÔÇŞ├à┬©er varsa)
        previous_context_str = "\n\n".join(sliding_window_buffer)
        
        try:
            # Kitapduy Tan├âÔÇŞ├é┬▒t├âÔÇŞ├é┬▒m Anonsu (Sadece 1. b├âãÆ├é┬Âl├âãÆ├é┬╝m├âãÆ├é┬╝n ba├âÔÇĞ├à┬©├âÔÇŞ├é┬▒na eklenir)
            if i == 0:
                intro = f"Eserimiz: {book_title}. Yazar: {book_author}. Arkan─▒za yaslan─▒n ve hikayenin tad─▒n─▒ ├ğ─▒kar─▒n. "
            else:
                intro = ""
            turkish_text = fetcher.translate_to_turkish(p, previous_context=previous_context_str)
            
            if i == 0:
                turkish_text = intro + turkish_text
                
            print(f"TR: {turkish_text[:60]}...")
        except Exception as e:
            print("\n!!! D├âÔÇŞ├é┬░KKAT: T├âãÆ├é┬╝m API hesaplar├âÔÇŞ├é┬▒n├âÔÇŞ├é┬▒z├âÔÇŞ├é┬▒n kotas├âÔÇŞ├é┬▒ tamamen doldu !!!")
            print("L├âãÆ├é┬╝tfen yar├âÔÇŞ├é┬▒na kadar bekleyin. Yar├âÔÇŞ├é┬▒n sistemi tekrar ba├âÔÇĞ├à┬©latt├âÔÇŞ├é┬▒├âÔÇŞ├à┬©├âÔÇŞ├é┬▒n├âÔÇŞ├é┬▒zda otomatik olarak buradan devam edecektir.")
            break
            
        # 2. Y├âãÆ├é┬Ânetmen Senaryosu (AI Studio Settings)
        print("Y├âãÆ├é┬Ânetmen Senaryosu (Scene/Context) olu├âÔÇĞ├à┬©turuluyor...")
        try:
            director_script = tts.generate_director_script(turkish_text, previous_context=previous_context_str)
        except Exception as e:
            print("\n!!! D├âÔÇŞ├é┬░KKAT: Y├âãÆ├é┬Ânetmen mod├âãÆ├é┬╝l├âãÆ├é┬╝nde kotalar tamamen doldu !!!")
            print("L├âãÆ├é┬╝tfen yar├âÔÇŞ├é┬▒na kadar bekleyin. Sistemin kald├âÔÇŞ├é┬▒├âÔÇŞ├à┬©├âÔÇŞ├é┬▒ yerden devam edebilmesi i├âãÆ├é┬ğin i├âÔÇĞ├à┬©lem durduruluyor.")
            break
            
        # 3. Seslendirme (TTS)
        # TTSGenerator'a artık tam dosya yolunu veriyoruz
        final_audio_path = tts.generate_audio(director_script, audio_path)
        
        if not final_audio_path: # Kotalar dolduğu için None döndüyse
            print("\n!!! DİKKAT: Seslendirme (TTS) tarafında kotalar tamamen doldu !!!")
            print("Yarın sistemi tekrar çalıştırırsanız, kaldığı bu bölümden otomatik olarak devam edecektir.")
            break
            
        r2_preview_url = None

        # Telemetry update
        voice_name = tts.config.get("voice", "Bilinmiyor")
        update_telemetry(book_source, book_title, i+1, total_paragraphs, voice_name, latest_audio_url=r2_preview_url)
        
        # 4. Kalite Kontrol (Opsiyonel)
        if ENABLE_QA and final_audio_path:
            success, msg = qa.check_audio_quality(final_audio_path, turkish_text)
            if not success:
                print(f"D├âÔÇŞ├é┬░KKAT: {filename} dosyas├âÔÇŞ├é┬▒nda hata olabilir. Rapor: {msg}")
            else:
                print(f"QA Onay├âÔÇŞ├é┬▒: {filename} ba├âÔÇĞ├à┬©ar├âÔÇŞ├é┬▒l├âÔÇŞ├é┬▒.")
                
        print("------------------\n")
        
        # Ge├âãÆ├é┬ğmi├âÔÇĞ├à┬© haf├âÔÇŞ├é┬▒zaya metni ekle ve sadece son 3 par├âãÆ├é┬ğay├âÔÇŞ├é┬▒ tut (Geni├âÔÇĞ├à┬©letilmi├âÔÇĞ├à┬© Context Window)
        sliding_window_buffer.append(p[:300]) # Sadece ├âãÆ├é┬Âzet tutulur
        if len(sliding_window_buffer) > 3:
            sliding_window_buffer.pop(0)
            
    print("├âÔÇŞ├é┬░├âÔÇĞ├é┼¥LEM SONLANDI. Dosyalar├âÔÇŞ├é┬▒n├âÔÇŞ├é┬▒z ├âÔÇĞ├à┬©u klas├âãÆ├é┬Ârde: ", book_output_dir)
    
    # T├âãÆ├é┬╝m b├âãÆ├é┬Âl├âãÆ├é┬╝mler bittiyse otomatik yay├âÔÇŞ├é┬▒nlama (Zero-Touch Publishing) ba├âÔÇĞ├à┬©lat
    import glob
    completed_mp3s = glob.glob(os.path.join(book_output_dir, "bolum_*.mp3"))
    completed_wavs = glob.glob(os.path.join(book_output_dir, "bolum_*.wav"))
    if (len(completed_mp3s) + len(completed_wavs)) >= len(paragraphs) and mode != "test" and not mode.startswith("t"):
        print("\n├ä┼©├à┬©├é┼¢├óÔé¼┬░ K├âÔÇŞ├é┬░TAP SESLEND├âÔÇŞ├é┬░RMES├âÔÇŞ├é┬░ %100 TAMAMLANDI!")
        print("├ä┼©├à┬©├à┬í├óÔÇÜ┬¼ KitapDuy Uygulamas├âÔÇŞ├é┬▒ ├âÔÇŞ├é┬░├âãÆ├é┬ğin Tam Otomatik Yay├âÔÇŞ├é┬▒nlama (Zero-Touch Publishing) Ba├âÔÇĞ├à┬©lat├âÔÇŞ├é┬▒l├âÔÇŞ├é┬▒yor...\n")
        try:
            pub = BookPublisher(gemini_client=fetcher.client if hasattr(fetcher, 'client') else None)
            
            # 1. MP3 olarak birle├âÔÇĞ├à┬©tir
            safe_title = "".join([c if c.isalnum() else "_" for c in book_title]).lower().strip("_")
            mp3_filename = f"{safe_title}.mp3"
            mp3_path = pub.merge_audio_to_mp3(book_output_dir, mp3_filename)
            
            if mp3_path:
                # 2. R2'ye y├âãÆ├é┬╝kle
                r2_audio_url = pub.upload_to_r2(mp3_path, mp3_filename)
                
                # 3. Kapak olu┼ştur ve R2'ye y├╝kle (Kapak aramas─▒ orijinal ─░ngilizce isimle yap─▒l─▒r ki API'ler kapa─ş─▒ bulabilsin)
                r2_cover_url = pub.generate_and_upload_cover(original_book_title, book_author, book_output_dir, safe_title)
                
                # 4. Firebase'e kaydet
                if r2_audio_url:
                    pub.publish_to_firebase(
                        title=book_title,
                        author=book_author,
                        raw_text_sample=raw_text[:2000],
                        audio_url=r2_audio_url,
                        cover_url=r2_cover_url
                    )
                    
                    # [YEN─░] Ba┼şar─▒l─▒ yay─▒ndan sonra yerel ses dosyalar─▒n─▒ silerek disk alan─▒ndan tasarruf et
                    print("\n[TEM─░ZL─░K] Kitap ba┼şar─▒yla buluta y├╝klendi. Yerel ses dosyalar─▒ diskten siliniyor...")
                    try:
                        import glob
                        for audio_file in glob.glob(os.path.join(book_output_dir, "*.wav")):
                            os.remove(audio_file)
                        for audio_file in glob.glob(os.path.join(book_output_dir, "*.mp3")):
                            os.remove(audio_file)
                        print("[TEM─░ZL─░K] Ses dosyalar─▒ ba┼şar─▒yla silindi. (Config ve loglar tutuluyor)")
                    except Exception as clean_err:
                        print(f"[UYARI] Dosyalar silinirken hata olu┼ştu: {clean_err}")
                    
                    # Otonom mod i├ğin kitap 100% bitti─şinde ID'sini kaydedelim ki bir daha okumas─▒n
                    if str(book_source).isdigit():
                        try:
                            with open("completed_books.txt", "a") as f:
                                f.write(str(book_source) + "\n")
                        except Exception:
                            pass
                        
        except Exception as e:
            print(f"[UYARI] Otomatik yay├âÔÇŞ├é┬▒nlay├âÔÇŞ├é┬▒c├âÔÇŞ├é┬▒ ├âãÆ├é┬ğal├âÔÇŞ├é┬▒├âÔÇĞ├à┬©t├âÔÇŞ├é┬▒r├âÔÇŞ├é┬▒l├âÔÇŞ├é┬▒rken bir hata olu├âÔÇĞ├à┬©tu: {e}")
    else:
        # Kitap bitmediyse (kota dolduysa vs) hata d├Ând├╝r ki otonom mod beklemeye ge├ğsin
        if mode != "test" and not mode.startswith("t"):
            return False
            
    return True
import time
import os
GLOBAL_START_TIME = time.time()
os.environ["GLOBAL_START_TIME"] = str(GLOBAL_START_TIME)
def main():
    print("====================================================")
    print("   K├âÔÇŞ├é┬░TAPDUY OTOMAT├âÔÇŞ├é┬░K SESL├âÔÇŞ├é┬░ K├âÔÇŞ├é┬░TAP ├âãÆ├àÔÇ£RET├âÔÇŞ├é┬░M S├âÔÇŞ├é┬░STEM├âÔÇŞ├é┬░")
    print("====================================================\n")
    
    book_source = os.environ.get("BOOK_SOURCE")
    if not book_source:
        print("Sisteme bir kitap eklemek i├âãÆ├é┬ğin ├âãÆ├é┬╝├âãÆ├é┬ğ se├âãÆ├é┬ğene├âÔÇŞ├à┬©iniz var:")
        print("1) Sadece Project Gutenberg numaras├âÔÇŞ├é┬▒n├âÔÇŞ├é┬▒ yaz├âÔÇŞ├é┬▒n (├âãÆ├óÔé¼ÔÇ£rn: 11)")
        print("2) 'auto' yazarak sonsuz otonom yapay zeka fabrikasini baslatin.")
        book_source = input("L├âãÆ├é┬╝tfen Kitap ID'sini, Dosya Ad├âÔÇŞ├é┬▒n├âÔÇŞ├é┬▒ veya URL'yi girin: ").strip()
        
    mode = os.environ.get("BOOK_MODE", "full")
    
    # 1. A┼şama: Manuel Kitap ─░┼şlemi (Kullan─▒c─▒ do─şrudan auto yazmad─▒ysa)
    if book_source.lower() != "auto":
        while True:
            import time
            success = process_book(book_source, mode)
            if success:
                print(f"\n[BA┼ŞARILI] {book_source} ID'li manuel kitap i┼şlemi tamamland─▒.")
                print("\n[GE├ç─░┼Ş] Sistem ┼şimdi otomatik olarak OTONOM FABR─░KA moduna ge├ği┼ş yap─▒yor...\n")
                time.sleep(5)
                book_source = "auto" # Manuel bitti, otomati─şe ge├ğ ve d├Âng├╝y├╝ k─▒r
                break
            else:
                if os.environ.get("GITHUB_ACTIONS") == "true":
                    import sys
                    import requests
                    import time
                    print("\n[GITHUB ACTIONS] Kotalar doldu! 1 saat (3600 sn) uykuya geciliyor...")
                    print("Uyku sirasinda 6 saat limiti yaklasirsa uyanip gucunu yeni sunucuya devredecek.")
                    
                    for _ in range(60):
                        if time.time() - GLOBAL_START_TIME > (5 * 3600 + 30 * 60):
                            print("\n!!! DIKKAT: Uyku sirasinda 6 saatlik limite ulasildi!")
                            print("[HAFIZA] Tum sesler GitHub Cache kasasina kilitlenecek.")
                            print("[SONSUZ DONGU] Kendi kendini yeniden tetikliyor...")
                            try:
                                token = os.environ.get("GITHUB_TOKEN")
                                if token:
                                    repo = "semtinazizi2/KitapDuy_Bulut"
                                    url = f"https://api.github.com/repos/{repo}/actions/workflows/audiobook.yml/dispatches"
                                    headers = {"Accept": "application/vnd.github+json", "Authorization": f"Bearer {token}", "X-GitHub-Api-Version": "2022-11-28"}
                                    data = {"ref": "main", "inputs": {"book_id": str(current_id if 'current_id' in locals() else book_source)}}
                                    requests.post(url, headers=headers, json=data)
                                    print(" -> Yeni GitHub robotu basariyla uyandirildi!")
                            except Exception as e:
                                print(f" -> Yeniden tetikleme basarisiz: {e}")
                            sys.exit(0)
                        time.sleep(60)
                    print("\n[UYANDI] 1 Saatlik uyku bitti, kotalar sifirlanmis olmali. Tekrar deneniyor...")
                else:
                    print(f"\n[BEKLEME] {book_source} ID'li kitap yar─▒m kald─▒ (Kotalar Doldu).")
                    print("Sistem, kotalar─▒n yenilenmesi i├ğin 60 dakika (3600 saniye) uykuya ge├ğiyor...")
                    print("S├╝re doldu─şunda kald─▒─ş─▒ kitaptan, kald─▒─ş─▒ b├Âl├╝mden aynen devam edecektir.")
                    time.sleep(3600)
                
            # RAM ┼Şi┼şmesini (Memory Leak / OOM) ├ûnlemek ─░├ğin ├ç├Âp Toplay─▒c─▒y─▒ ├çal─▒┼şt─▒r
            import gc
            gc.collect()
    # 2. A┼şama: Otonom Fabrika D├Âng├╝s├╝ (Ba┼ştan auto girildiyse veya manuel bittiyse buraya d├╝┼şer)
    if book_source.lower() == "auto":
        print("\n[OTONOM FABR─░KA] Sistem sonsuz d├Âng├╝ modunda ba┼şlat─▒ld─▒!")
        print("[OTONOM FABR─░KA] Kendi kendine kitap aray─▒p yay─▒nlamaya devam edecek...")
        from book_fetcher import BookFetcher
        fetcher_instance = BookFetcher()
        current_id = None
        while True:
            import time
            if current_id is None:
                # 1. Oracle'dan kuyruğu kontrol et
                try:
                    headers = {"Authorization": f"Bearer {TELEMETRY_TOKEN}"}
                    r = requests.post(f"{ORACLE_URL}/api/telemetry/queue/pop", headers=headers, timeout=5)
                    if r.status_code == 200 and r.json().get("book_id"):
                        current_id = r.json()["book_id"]
                        print(f"\n[KUYRUK] Kullanıcının eklediği kitap kuyruktan çekildi: {current_id}")
                except Exception as e:
                    print(f"[UYARI] Kuyruk kontrol edilemedi: {e}")
                    
                # 2. Kuyruk boşsa rastgele devam et
                if not current_id:
                    current_id = fetcher_instance.get_random_gutenberg_id()
                
            success = process_book(current_id, mode)
            
            if not success:
                if os.environ.get("GITHUB_ACTIONS") == "true":
                    import sys
                    import requests
                    import time
                    print("\n[GITHUB ACTIONS] Kotalar doldu! 1 saat (3600 sn) uykuya geciliyor...")
                    print("Uyku sirasinda 6 saat limiti yaklasirsa uyanip gucunu yeni sunucuya devredecek.")
                    
                    for _ in range(60):
                        if time.time() - GLOBAL_START_TIME > (5 * 3600 + 30 * 60):
                            print("\n!!! DIKKAT: Uyku sirasinda 6 saatlik limite ulasildi!")
                            print("[HAFIZA] Tum sesler GitHub Cache kasasina kilitlenecek.")
                            print("[SONSUZ DONGU] Kendi kendini yeniden tetikliyor...")
                            try:
                                token = os.environ.get("GITHUB_TOKEN")
                                if token:
                                    repo = "semtinazizi2/KitapDuy_Bulut"
                                    url = f"https://api.github.com/repos/{repo}/actions/workflows/audiobook.yml/dispatches"
                                    headers = {"Accept": "application/vnd.github+json", "Authorization": f"Bearer {token}", "X-GitHub-Api-Version": "2022-11-28"}
                                    data = {"ref": "main", "inputs": {"book_id": str(current_id if 'current_id' in locals() else book_source)}}
                                    requests.post(url, headers=headers, json=data)
                                    print(" -> Yeni GitHub robotu basariyla uyandirildi!")
                            except Exception as e:
                                print(f" -> Yeniden tetikleme basarisiz: {e}")
                            sys.exit(0)
                        time.sleep(60)
                    print("\n[UYANDI] 1 Saatlik uyku bitti, kotalar sifirlanmis olmali. Tekrar deneniyor...")
                else:
                    print(f"\n[OTONOM BEKLEME] {current_id} ID'li kitap yar─▒m kald─▒ (Kotalar Doldu).")
                    print("Sistem, kotalar─▒n yenilenmesi i├ğin 60 dakika (3600 saniye) uykuya ge├ğiyor...")
                    print("S├╝re doldu─şunda kald─▒─ş─▒ kitaptan, kald─▒─ş─▒ b├Âl├╝mden aynen devam edecektir.")
                    time.sleep(3600)
            else:
                print("\n[OTONOM FABR─░KA] Kitap bitti! 10 saniye sonra s─▒radaki kitaba ge├ğiliyor...\n")
                current_id = None # Eski kitap bitti, yeni kitaba ge├ğmek i├ğin s─▒f─▒rla
                time.sleep(10)
                
            # RAM ┼Şi┼şmesini (Memory Leak / OOM) ├ûnlemek ─░├ğin ├ç├Âp Toplay─▒c─▒y─▒ ├çal─▒┼şt─▒r
            import gc
            gc.collect()
if __name__ == "__main__":
    main()