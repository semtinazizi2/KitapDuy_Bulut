import os
import glob
import json
import urllib.request
import re
from dotenv import load_dotenv
from book_fetcher import BookFetcher
from publisher import BookPublisher

load_dotenv()

def main():
    print("================================================================")
    print("   KİTAPDUY - MEVCUT SESLİ KİTAPLARI OTOMATİK YAYINLAMA ARACI   ")
    print("================================================================\n")
    
    output_dir = os.getenv("OUTPUT_DIR", "output_audio")
    if not os.path.exists(output_dir):
        print(f"[HATA] {output_dir} klasörü bulunamadı!")
        return

    folders = [d for d in os.listdir(output_dir) if os.path.isdir(os.path.join(output_dir, d))]
    if not folders:
        print("[HATA] Önceden seslendirilmiş hiçbir kitap klasörü bulunamadı.")
        return

    print("Mevcut Hazır Kitap Klasörleri:")
    for idx, f in enumerate(folders):
        wav_count = len(glob.glob(os.path.join(output_dir, f, "bolum_*.wav")))
        print(f"  {idx+1}) Klasör: {f} ({wav_count} adet bölüm dosyası hazır)")
        
    print("\n----------------------------------------------------------------")
    choice = input("Lütfen yayınlamak istediğiniz klasör adını (veya numarasını) yazın: ").strip()
    
    target_folder = None
    if choice.isdigit() and int(choice) <= len(folders) and int(choice) > 0:
        target_folder = folders[int(choice)-1]
    elif choice in folders:
        target_folder = choice
    else:
        print("[HATA] Geçersiz seçim yaptınız.")
        return
        
    book_dir = os.path.join(output_dir, target_folder)
    print(f"\nSeçilen Klasör: {book_dir}")
    
    # Kitap adı ve yazarını otomatik algılayalım (Zero-Touch)
    title, author = None, None
    meta_path = os.path.join(book_dir, "metadata.json")
    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                m = json.load(f)
                title, author = m.get("title"), m.get("author")
        except Exception:
            pass

    fetcher = BookFetcher()

    if (not title or not author) and target_folder.isdigit():
        print(f" -> Gutenberg ID ({target_folder}) algılandı. Kitap künyesi ve Türkçe adı yapay zeka ile çekiliyor...")
        try:
            url = f"https://www.gutenberg.org/cache/epub/{target_folder}/pg{target_folder}.txt"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as response:
                text = response.read().decode('utf-8', errors='ignore')[:4000]
                t, a = fetcher.get_book_metadata(text)
                if t and "Bilinmeyen" not in t and not title:
                    title = t
                if a and "Bilinmeyen" not in a and not author:
                    author = a
        except Exception as e:
            print(f" -> [UYARI] Gutenberg künye çekme uyarısı: {e}")

    if not title:
        title = target_folder.replace("_", " ").title()
    if not author:
        author = "Bilinmiyor"
        
    # Bulguyu kalıcı olarak kaydet ki bir daha asla sormasın veya internetten aramasın
    try:
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump({"title": title, "author": author}, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    print(f" -> [OTOMATİK ALGILANDI] Türkçe Kitap Adı: '{title}' | Yazar: '{author}'")
    print(f"\n🚀 '{title}' ({author}) için Tam Otomatik Yayınlama (Zero-Touch Publishing) Başlatılıyor...\n")
    
    try:
        pub = BookPublisher(gemini_client=fetcher.client if hasattr(fetcher, 'client') else None)
        
        # 1. MP3 olarak birleştir
        safe_title = "".join([c if c.isalnum() else "_" for c in title]).lower().strip("_")
        mp3_filename = f"{safe_title}.mp3"
        mp3_path = pub.merge_audio_to_mp3(book_dir, mp3_filename)
        
        if mp3_path:
            # 2. R2'ye yükle
            r2_audio_url = pub.upload_to_r2(mp3_path, mp3_filename)
            
            # 3. Kapak oluştur ve R2'ye yükle
            r2_cover_url = pub.generate_and_upload_cover(title, author, book_dir, safe_title)
            
            # 4. Firebase'e kaydet
            if r2_audio_url:
                # Örnek metin bulmaya çalış (ilk wav dosyasına karşılık gelen metin varsa veya genel)
                sample_text = f"{author} tarafından yazılan {title} adlı eserin sesli kitap sürümü."
                pub.publish_to_firebase(
                    title=title,
                    author=author,
                    raw_text_sample=sample_text,
                    audio_url=r2_audio_url,
                    cover_url=r2_cover_url
                )
    except Exception as e:
        print(f"[HATA] Yayınlama sırasında bir sorun oluştu: {e}")

if __name__ == "__main__":
    main()
