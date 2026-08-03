import os
import time
from book_fetcher import BookFetcher
from tts_generator import TTSGenerator
from qa_checker import QAChecker
from publisher import BookPublisher

def main():
    print("====================================================")
    print("   KÃ„Â°TAPDUY OTOMATÃ„Â°K SESLÃ„Â° KÃ„Â°TAP ÃƒÅ“RETÃ„Â°M SÃ„Â°STEMÃ„Â°")
    print("====================================================\n")
    
    print("====================================================\n")
    
    print("Sisteme bir kitap eklemek iÃƒÂ§in ÃƒÂ¼ÃƒÂ§ seÃƒÂ§eneÃ„Å¸iniz var:")
    print("1) Sadece Project Gutenberg numarasÃ„Â±nÃ„Â± yazÃ„Â±n (Ãƒâ€“rn: 11)")
    print("2) KlasÃƒÂ¶rÃƒÂ¼n iÃƒÂ§indeki kendi metin dosyanÃ„Â±zÃ„Â±n adÃ„Â±nÃ„Â± yazÃ„Â±n (Ãƒâ€“rn: benim_kitabim.txt)")
    print("3) Ã„Â°nternetten doÃ„Å¸rudan URL yapÃ„Â±Ã…Å¸tÃ„Â±rÃ„Â±n (Ãƒâ€“rn: https://standardebooks.org/...) \n")
    
    book_source = os.environ.get("BOOK_SOURCE")
    if not book_source:
        book_source = input("LÃƒÂ¼tfen Kitap ID'sini, Dosya AdÃ„Â±nÃ„Â± veya URL'yi girin: ").strip()
        
    mode = os.environ.get("BOOK_MODE")
    if not mode:
        mode = input("Sadece kÃ„Â±sa bir 'Test' (Ã„Â°lk 3 paragraf) mi yapmak istersiniz, yoksa kitabÃ„Â±n 'TamamÃ„Â±nÃ„Â±' mÃ„Â±? (Test/TamamÃ„Â±): ").strip().lower()
    
def process_book(book_source, mode):
    import os
    ENABLE_QA = False
    print(f"\n================ YENİ KİTAP ({book_source}) BAŞLIYOR ====================")
    print("\nAdÃ„Â±m 1: ModÃƒÂ¼ller baÃ…Å¸latÃ„Â±lÃ„Â±yor (Bu iÃ…Å¸lem birkaÃƒÂ§ saniye sÃƒÂ¼rebilir)...")
    try:
        fetcher = BookFetcher()
        
        raw_text = ""
        if book_source.startswith("http://") or book_source.startswith("https://"):
            print(f"\nAdÃ„Â±m 2: Web sitesinden kitap ÃƒÂ§ekiliyor ({book_source})...")
            raw_text = fetcher.download_from_url(book_source)
            # URL'den sabit ve okunabilir klasÃƒÂ¶r adÃ„Â± ÃƒÂ¼ret (hash deÃ„Å¸il, URL dosya adÃ„Â±)
            from urllib.parse import urlparse
            url_path = urlparse(book_source).path
            url_filename = _os.path.basename(url_path)          # ÃƒÂ¶rn: 0100021h.html
            url_filename = _os.path.splitext(url_filename)[0]   # ÃƒÂ¶rn: 0100021h
            book_folder_name = "url_" + url_filename            # ÃƒÂ¶rn: url_0100021h
        elif book_source.endswith(".txt") and os.path.exists(book_source):
            print(f"\nAdÃ„Â±m 2: Yerel dosya okunuyor ({book_source})...")
            with open(book_source, "r", encoding="utf-8") as f:
                raw_text = f.read()
            book_folder_name = book_source.replace(".txt", "")
        else:
            print(f"\nAdÃ„Â±m 2: Kitap indiriliyor (Project Gutenberg ID: {book_source})...")
            raw_text = fetcher.download_gutenberg_book(book_source)
            book_folder_name = book_source
            
        if not raw_text:
            print("HATA: Kitap metni alÃ„Â±namadÃ„Â±. Dosya adÃ„Â±nÃ„Â±, URL'yi veya Gutenberg ID'sini kontrol edin.")
            return

        # Her kitap iÃƒÂ§in ayrÃ„Â± bir klasÃƒÂ¶r oluÃ…Å¸tur ve hafÃ„Â±zayÃ„Â± oraya kaydet
        book_output_dir = os.path.join(os.getenv("OUTPUT_DIR", "output_audio"), book_folder_name)
        os.makedirs(book_output_dir, exist_ok=True)
        
        config_path = os.path.join(book_output_dir, "book_config.json")
        
        # Kitap HafÃ„Â±zasÃ„Â± (Voice Continuity)
        if os.path.exists(config_path):
            print(f"\n[BÃ„Â°LGÃ„Â°] Bu kitabÃ„Â±n eski spiker hafÃ„Â±zasÃ„Â± bulundu. Ses tonu (Voice) deÃ„Å¸iÃ…Å¸tirilmeden orijinal spikerle devam edilecek!")
        else:
            fetcher.analyze_and_save_book_config(raw_text[:3000], config_path)

        tts = TTSGenerator(config_path=config_path)
        qa = QAChecker(is_enabled=ENABLE_QA)
    except Exception as e:
        print(f"ModÃƒÂ¼l baÃ…Å¸latma hatasÃ„Â±: {e}\nLÃƒÂ¼tfen .env dosyanÃ„Â±zÃ„Â± kontrol edin.")
        return

    # Kitap bilgileri zaten fetcher tarafından alındı (başarısız olsa da "Bilinmeyen" ile devam edilir)
    # İkinci kez API çağırıp hesapları yakmamak için tekrar sorulmaz!
    if hasattr(fetcher, 'book_title') and fetcher.book_title:
        original_book_title = fetcher.book_title
        book_title = fetcher.book_title
        book_author = getattr(fetcher, 'book_author', 'Bilinmeyen Yazar')
    else:
        # Fallback: Kitap ID'sinden isim türet
        original_book_title = f"Kitap {book_source}"
        book_title = original_book_title
        book_author = "Bilinmeyen Yazar"
        
    print(f"[BÃ„Â°LGÃ„Â°] Eser Tespit Edildi: '{book_title}' - Yazar: {book_author}")
    
    import json
    metadata_path = os.path.join(book_output_dir, "metadata.json")
    
    # Eğer daha önce Türkçe başlık çevrilip kaydedildiyse oradan oku, yoksa çevir
    if os.path.exists(metadata_path):
        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                saved_meta = json.load(f)
                book_title = saved_meta.get("title", book_title)
        except Exception:
            pass
    else:
        print("[BİLGİ] Kitap adı Türkçeye çevriliyor...")
        try:
            translated_title = fetcher.translate_to_turkish(f"The title of the book is '{book_title}'. Translate ONLY this title to Turkish. If it is already Turkish or a proper name that shouldn't be translated, keep it as is. Do not add any punctuation or extra text.", previous_context="")
            if len(translated_title) > 80 or translated_title.strip() == "":
                translated_title = book_title
            book_title = translated_title.strip()
            
            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump({"title": book_title, "author": book_author}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[UYARI] Kitap adı çevrilemedi: {e}")

    fetcher.check_and_warn_copyright(raw_text, book_title, book_author, source=book_source)
    
    # --- KİTAPDUY UYGULAMASI VERİTABANI KONTROLÜ ---
    # Eğer kitap zaten uygulamada varsa (İsim eşleşiyorsa) boşuna üretmemek için atlarız
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore
        if not firebase_admin._apps:
            cred = credentials.Certificate("serviceAccountKey.json")
            firebase_admin.initialize_app(cred)
        db = firestore.client()
        existing = db.collection("books").where("title", "==", book_title).limit(1).get()
        if len(existing) > 0:
            print(f"\n[BİLGİ] '{book_title}' zaten KitapDuy uygulamasında MECUT! Bu kitap atlanıp yenisine geçilecek...")
            with open("completed_books.txt", "a", encoding="utf-8") as f:
                f.write(f"{book_source}\n")
            return True # Otonom döngü hata sanıp 5 dk beklemesin, hemen yenisine geçsin
    except Exception as e:
        print(f"[UYARI] Uygulama veritabanı kontrolü yapılamadı: {e}")
        
    paragraphs = fetcher.split_into_paragraphs(raw_text)
    
    if "test" in mode or mode == "t":
        paragraphs = paragraphs[:3]
        print(f"\n[TEST MODU]: Kitabin sadece ilk {len(paragraphs)} parcasi islenecek.\n")
    else:
        print(f"\n[TAM SURUM]: Kitap toplam {len(paragraphs)} parcaya bolundu. Basliyoruz...\n")
        
    # Klasor zaten yukarida olusturuldu
    
    total_paragraphs = len(paragraphs)
    print(f"\n[BÄ°LGÄ°] Kitap baÅŸarÄ±yla {total_paragraphs} parÃ§aya (bÃ¶lÃ¼me) ayrÄ±ldÄ±. Ä°ÅŸlem baÅŸlÄ±yor...\n")

    # ÃœCRETSÄ°Z SÃœRGÃœLÃœ HAFIZA (Sliding Window Buffer)
    sliding_window_buffer = []
    start_time = time.time()

    for i, p in enumerate(paragraphs):
        # 6 SAAT TÄ°MER KONTROLÃœ (GÄ°THUB ACTÄ°ONS FÄ°Å Ã‡EKMEDEN KAÃ‡IÅ)
        if time.time() - start_time > (5 * 3600 + 45 * 60):  # 5 saat 45 dakika
            print("\n!!! DÄ°KKAT: GitHub'Ä±n 6 saatlik maksimum sÃ¼resine yaklaÅŸÄ±ldÄ±! !!!")
            print("Sistem fiÅŸ Ã§ekilmeden Ã¶nce uyanÄ±yor, verileri GÃœVENLE kasaya kaydedip uykuya geÃ§iyor.")
            print("LÃ¼tfen gÃ¶revi (Run workflow) tekrar baÅŸlatarak kaldÄ±ÄŸÄ± yerden devam ediniz.")
            break

        progress_pct = (i / total_paragraphs) * 100
        print(f"--- BÃ–LÃœM {i+1} / {total_paragraphs} (%{progress_pct:.1f} TamamlandÄ±) ---")
        
        filename = f"bolum_{i+1:03d}.mp3"
        audio_path = os.path.join(book_output_dir, filename)
        
        # KaldÄ±ÄŸÄ± yerden devam etme mantÄ±ÄŸÄ±
        if os.path.exists(audio_path) or os.path.exists(audio_path.replace('.mp3', '.wav')):
            print(f"[{filename}] veya WAV hali zaten mevcut. KotayÃ„Â± korumak iÃƒÂ§in atlanÃ„Â±yor...")
            print("------------------\n")
            continue
        
        # 1. Ãƒâ€¡eviri
        print("Ãƒâ€¡evirisi yapÃ„Â±lÃ„Â±yor...")
        
        # GeÃƒÂ§miÃ…Å¸ baÃ„Å¸lamÃ„Â± dÃƒÂ¼z metne ÃƒÂ§evir (EÃ„Å¸er varsa)
        previous_context_str = "\n\n".join(sliding_window_buffer)
        
        try:
            # Kitapduy TanÃ„Â±tÃ„Â±m Anonsu (Sadece 1. bÃƒÂ¶lÃƒÂ¼mÃƒÂ¼n baÃ…Å¸Ã„Â±na eklenir)
            if i == 0:
                intro = f"Eserimiz: {book_title}. Yazar: {book_author}. Arkanıza yaslanın ve hikayenin tadını çıkarın. "
            else:
                intro = ""

            turkish_text = fetcher.translate_to_turkish(p, previous_context=previous_context_str)
            
            if i == 0:
                turkish_text = intro + turkish_text
                
            print(f"TR: {turkish_text[:60]}...")
        except Exception as e:
            print("\n!!! DÃ„Â°KKAT: TÃƒÂ¼m API hesaplarÃ„Â±nÃ„Â±zÃ„Â±n kotasÃ„Â± tamamen doldu !!!")
            print("LÃƒÂ¼tfen yarÃ„Â±na kadar bekleyin. YarÃ„Â±n sistemi tekrar baÃ…Å¸lattÃ„Â±Ã„Å¸Ã„Â±nÃ„Â±zda otomatik olarak buradan devam edecektir.")
            break
            
        # 2. YÃƒÂ¶netmen Senaryosu (AI Studio Settings)
        print("YÃƒÂ¶netmen Senaryosu (Scene/Context) oluÃ…Å¸turuluyor...")
        try:
            director_script = tts.generate_director_script(turkish_text, previous_context=previous_context_str)
        except Exception as e:
            print("\n!!! DÃ„Â°KKAT: YÃƒÂ¶netmen modÃƒÂ¼lÃƒÂ¼nde kotalar tamamen doldu !!!")
            print("LÃƒÂ¼tfen yarÃ„Â±na kadar bekleyin. Sistemin kaldÃ„Â±Ã„Å¸Ã„Â± yerden devam edebilmesi iÃƒÂ§in iÃ…Å¸lem durduruluyor.")
            break
            
        # 3. Seslendirme (TTS)
        # TTSGenerator'a artÃ„Â±k tam dosya yolunu veriyoruz
        final_audio_path = tts.generate_audio(director_script, audio_path)
        
        if not final_audio_path: # Kotalar dolduÃ„Å¸u iÃƒÂ§in None dÃƒÂ¶ndÃƒÂ¼yse
            print("\n!!! DÃ„Â°KKAT: Seslendirme (TTS) tarafÃ„Â±nda kotalar tamamen doldu !!!")
            print("YarÃ„Â±n sistemi tekrar ÃƒÂ§alÃ„Â±Ã…Å¸tÃ„Â±rÃ„Â±rsanÃ„Â±z, kaldÃ„Â±Ã„Å¸Ã„Â± bu bÃƒÂ¶lÃƒÂ¼mden otomatik olarak devam edecektir.")
            break
            
        # 4. Kalite Kontrol (Opsiyonel)
        if ENABLE_QA and final_audio_path:
            success, msg = qa.check_audio_quality(final_audio_path, turkish_text)
            if not success:
                print(f"DÃ„Â°KKAT: {filename} dosyasÃ„Â±nda hata olabilir. Rapor: {msg}")
            else:
                print(f"QA OnayÃ„Â±: {filename} baÃ…Å¸arÃ„Â±lÃ„Â±.")
                
        print("------------------\n")
        
        # GeÃƒÂ§miÃ…Å¸ hafÃ„Â±zaya metni ekle ve sadece son 3 parÃƒÂ§ayÃ„Â± tut (GeniÃ…Å¸letilmiÃ…Å¸ Context Window)
        sliding_window_buffer.append(p[:300]) # Sadece ÃƒÂ¶zet tutulur
        if len(sliding_window_buffer) > 3:
            sliding_window_buffer.pop(0)
            
    print("Ã„Â°Ã…ÂžLEM SONLANDI. DosyalarÃ„Â±nÃ„Â±z Ã…Å¸u klasÃƒÂ¶rde: ", book_output_dir)
    
    # TÃƒÂ¼m bÃƒÂ¶lÃƒÂ¼mler bittiyse otomatik yayÃ„Â±nlama (Zero-Touch Publishing) baÃ…Å¸lat
    import glob
    completed_mp3s = glob.glob(os.path.join(book_output_dir, "bolum_*.mp3"))
    completed_wavs = glob.glob(os.path.join(book_output_dir, "bolum_*.wav"))
    if (len(completed_mp3s) + len(completed_wavs)) >= len(paragraphs) and mode != "test" and not mode.startswith("t"):
        print("\nÄŸÅ¸ÂŽâ€° KÃ„Â°TAP SESLENDÃ„Â°RMESÃ„Â° %100 TAMAMLANDI!")
        print("ÄŸÅ¸Å¡â‚¬ KitapDuy UygulamasÃ„Â± Ã„Â°ÃƒÂ§in Tam Otomatik YayÃ„Â±nlama (Zero-Touch Publishing) BaÃ…Å¸latÃ„Â±lÃ„Â±yor...\n")
        try:
            pub = BookPublisher(gemini_client=fetcher.client if hasattr(fetcher, 'client') else None)
            
            # 1. MP3 olarak birleÃ…Å¸tir
            safe_title = "".join([c if c.isalnum() else "_" for c in book_title]).lower().strip("_")
            mp3_filename = f"{safe_title}.mp3"
            mp3_path = pub.merge_audio_to_mp3(book_output_dir, mp3_filename)
            
            if mp3_path:
                # 2. R2'ye yÃƒÂ¼kle
                r2_audio_url = pub.upload_to_r2(mp3_path, mp3_filename)
                
                # 3. Kapak oluştur ve R2'ye yükle (Kapak araması orijinal İngilizce isimle yapılır ki API'ler kapağı bulabilsin)
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
                    
                    # [YENİ] Başarılı yayından sonra yerel ses dosyalarını silerek disk alanından tasarruf et
                    print("\n[TEMİZLİK] Kitap başarıyla buluta yüklendi. Yerel ses dosyaları diskten siliniyor...")
                    try:
                        import glob
                        for audio_file in glob.glob(os.path.join(book_output_dir, "*.wav")):
                            os.remove(audio_file)
                        for audio_file in glob.glob(os.path.join(book_output_dir, "*.mp3")):
                            os.remove(audio_file)
                        print("[TEMİZLİK] Ses dosyaları başarıyla silindi. (Config ve loglar tutuluyor)")
                    except Exception as clean_err:
                        print(f"[UYARI] Dosyalar silinirken hata oluştu: {clean_err}")
                    
                    # Otonom mod için kitap 100% bittiğinde ID'sini kaydedelim ki bir daha okumasın
                    if str(book_source).isdigit():
                        try:
                            with open("completed_books.txt", "a") as f:
                                f.write(str(book_source) + "\n")
                        except Exception:
                            pass
                        
        except Exception as e:
            print(f"[UYARI] Otomatik yayÃ„Â±nlayÃ„Â±cÃ„Â± ÃƒÂ§alÃ„Â±Ã…Å¸tÃ„Â±rÃ„Â±lÃ„Â±rken bir hata oluÃ…Å¸tu: {e}")
    else:
        # Kitap bitmediyse (kota dolduysa vs) hata döndür ki otonom mod beklemeye geçsin
        if mode != "test" and not mode.startswith("t"):
            return False
            
    return True

def main():
    print("====================================================")
    print("   KÃ„Â°TAPDUY OTOMATÃ„Â°K SESLÃ„Â° KÃ„Â°TAP ÃƒÅ“RETÃ„Â°M SÃ„Â°STEMÃ„Â°")
    print("====================================================\n")
    
    book_source = os.environ.get("BOOK_SOURCE")
    if not book_source:
        print("Sisteme bir kitap eklemek iÃƒÂ§in ÃƒÂ¼ÃƒÂ§ seÃƒÂ§eneÃ„Å¸iniz var:")
        print("1) Sadece Project Gutenberg numarasÃ„Â±nÃ„Â± yazÃ„Â±n (Ãƒâ€“rn: 11)")
        print("2) 'auto' yazarak sonsuz otonom yapay zeka fabrikasini baslatin.")
        book_source = input("LÃƒÂ¼tfen Kitap ID'sini, Dosya AdÃ„Â±nÃ„Â± veya URL'yi girin: ").strip()
        
    mode = os.environ.get("BOOK_MODE", "full")
    
    # 1. Aşama: Manuel Kitap İşlemi (Kullanıcı doğrudan auto yazmadıysa)
    if book_source.lower() != "auto":
        while True:
            import time
            success = process_book(book_source, mode)
            if success:
                print(f"\n[BAŞARILI] {book_source} ID'li manuel kitap işlemi tamamlandı.")
                print("\n[GEÇİŞ] Sistem şimdi otomatik olarak OTONOM FABRİKA moduna geçiş yapıyor...\n")
                time.sleep(5)
                book_source = "auto" # Manuel bitti, otomatiğe geç ve döngüyü kır
                break
            else:
                if os.environ.get("GITHUB_ACTIONS") == "true":
                    import sys
                    import requests
                    print("\n[GITHUB ACTIONS] Sistemin fişi çekilmeden önce Güvenli Çıkış yapılıyor.")
                    print("[HAFIZA] Tüm sesler GitHub Cache kasasına kilitlenecek. Bir sonraki başlatmada buradan devam edecek.")
                    print("[SONSUZ DÖNGÜ] Kendi kendini yeniden tetikliyor...")
                    try:
                        token = os.environ.get("GITHUB_TOKEN")
                        if token:
                            repo = "semtinazizi2/KitapDuy_Bulut"
                            url = f"https://api.github.com/repos/{repo}/actions/workflows/audiobook.yml/dispatches"
                            headers = {"Accept": "application/vnd.github+json", "Authorization": f"Bearer {token}", "X-GitHub-Api-Version": "2022-11-28"}
                            data = {"ref": "main", "inputs": {"book_id": str(book_source)}}
                            requests.post(url, headers=headers, json=data)
                            print(" -> Yeni GitHub robotu başarıyla uyandırıldı!")
                    except Exception as e:
                        print(f" -> Yeniden tetikleme başarısız: {e}")
                    sys.exit(0)
                else:
                    print(f"\n[BEKLEME] {book_source} ID'li kitap yarım kaldı (Kotalar Doldu).")
                    print("Sistem, kotaların yenilenmesi için 60 dakika (3600 saniye) uykuya geçiyor...")
                    print("Süre dolduğunda kaldığı kitaptan, kaldığı bölümden aynen devam edecektir.")
                    time.sleep(3600)
                
            # RAM Şişmesini (Memory Leak / OOM) Önlemek İçin Çöp Toplayıcıyı Çalıştır
            import gc
            gc.collect()

    # 2. Aşama: Otonom Fabrika Döngüsü (Baştan auto girildiyse veya manuel bittiyse buraya düşer)
    if book_source.lower() == "auto":
        print("\n[OTONOM FABRİKA] Sistem sonsuz döngü modunda başlatıldı!")
        print("[OTONOM FABRİKA] Kendi kendine kitap arayıp yayınlamaya devam edecek...")
        from book_fetcher import BookFetcher
        fetcher_instance = BookFetcher()
        current_id = None
        while True:
            import time
            if current_id is None:
                current_id = fetcher_instance.get_random_gutenberg_id()
                
            success = process_book(current_id, mode)
            
            if not success:
                if os.environ.get("GITHUB_ACTIONS") == "true":
                    import sys
                    import requests
                    print("\n[GITHUB ACTIONS] Sistemin fişi çekilmeden önce Güvenli Çıkış yapılıyor.")
                    print("[HAFIZA] Tüm sesler GitHub Cache kasasına kilitlenecek. Bir sonraki başlatmada buradan devam edecek.")
                    print("[SONSUZ DÖNGÜ] Kendi kendini yeniden tetikliyor...")
                    try:
                        token = os.environ.get("GITHUB_TOKEN")
                        if token:
                            repo = "semtinazizi2/KitapDuy_Bulut"
                            url = f"https://api.github.com/repos/{repo}/actions/workflows/audiobook.yml/dispatches"
                            headers = {"Accept": "application/vnd.github+json", "Authorization": f"Bearer {token}", "X-GitHub-Api-Version": "2022-11-28"}
                            data = {"ref": "main", "inputs": {"book_id": str(current_id)}}
                            requests.post(url, headers=headers, json=data)
                            print(" -> Yeni GitHub robotu başarıyla uyandırıldı!")
                    except Exception as e:
                        print(f" -> Yeniden tetikleme başarısız: {e}")
                    sys.exit(0)
                else:
                    print(f"\n[OTONOM BEKLEME] {current_id} ID'li kitap yarım kaldı (Kotalar Doldu).")
                    print("Sistem, kotaların yenilenmesi için 60 dakika (3600 saniye) uykuya geçiyor...")
                    print("Süre dolduğunda kaldığı kitaptan, kaldığı bölümden aynen devam edecektir.")
                    time.sleep(3600)
            else:
                print("\n[OTONOM FABRİKA] Kitap bitti! 10 saniye sonra sıradaki kitaba geçiliyor...\n")
                current_id = None # Eski kitap bitti, yeni kitaba geçmek için sıfırla
                time.sleep(10)
                
            # RAM Şişmesini (Memory Leak / OOM) Önlemek İçin Çöp Toplayıcıyı Çalıştır
            import gc
            gc.collect()

if __name__ == "__main__":
    main()


