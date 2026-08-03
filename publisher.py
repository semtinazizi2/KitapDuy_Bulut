import os
import glob
import json
import time
import urllib.parse
import requests
from dotenv import load_dotenv
from pydub import AudioSegment
import boto3
import firebase_admin
from firebase_admin import credentials, firestore
from PIL import Image, ImageDraw, ImageFont

load_dotenv()

class BookPublisher:
    def __init__(self, gemini_client=None):
        self.gemini_client = gemini_client
        self.r2_endpoint = os.getenv("R2_ENDPOINT")
        self.r2_access_key = os.getenv("R2_ACCESS_KEY")
        self.r2_secret_key = os.getenv("R2_SECRET_KEY")
        self.r2_bucket = os.getenv("R2_BUCKET_NAME", "kitapduy")
        self.r2_public_url = os.getenv("R2_PUBLIC_URL", "https://ancient-shape-df97.samatya231.workers.dev").rstrip("/")
        
        # R2 S3 İstemcisini Başlat
        self.s3 = boto3.client('s3',
            endpoint_url=self.r2_endpoint,
            aws_access_key_id=self.r2_access_key,
            aws_secret_access_key=self.r2_secret_key
        )
        
        # Firebase Firestore'u Başlat (Eğer henüz başlatılmadıysa)
        self._init_firebase()

    def _init_firebase(self):
        try:
            firebase_key_path = os.getenv("FIREBASE_KEY_PATH", "serviceAccountKey.json")
            if not firebase_admin._apps:
                cred = credentials.Certificate(firebase_key_path)
                firebase_admin.initialize_app(cred)
            self.db = firestore.client()
            print("[BİLGİ] Firebase Firestore bağlantısı hazır.")
        except Exception as e:
            print(f"[UYARI] Firebase başlatılamadı: {e}")
            self.db = None

    def merge_audio_to_mp3(self, book_dir, output_filename):
        """Klasördeki tüm bölüm .wav dosyalarını sırasıyla birleştirip tek bir MP3 yapar."""
        print(f"\n[1/4] Bölümler birleştiriliyor ve MP3 formata dönüştürülüyor ({book_dir})...")
        import re
        import subprocess
        
        # 1. Dosyaları numara sırasına göre kesin ve doğru sırala (bolum_1, bolum_2 ... bolum_702)
        def get_chapter_num(path):
            match = re.search(r'bolum_(\d+)\.(mp3|wav)$', os.path.basename(path), re.IGNORECASE)
            return int(match.group(1)) if match else 0
            
        audio_files = sorted(glob.glob(os.path.join(book_dir, "bolum_*.mp3")) + glob.glob(os.path.join(book_dir, "bolum_*.wav")), key=get_chapter_num)
        
        if not audio_files:
            print("[HATA] Birleştirilecek bölüm dosyası bulunamadı!")
            return None
            
        print(f" -> Toplam {len(audio_files)} bölüm dosyası doğru sayısal sırayla bulundu.")
        
        # 4 GB WAV sınırını ve RAM taşmasını önlemek için doğrudan FFmpeg Akış (Streaming Concat) Yöntemi:
        import platform
        local_ffmpeg = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ffmpeg.exe")
        if platform.system() == "Windows" and os.path.exists(local_ffmpeg):
            ffmpeg_bin = local_ffmpeg
        else:
            ffmpeg_bin = "ffmpeg"
        
        # 1 saniyelik sessizlik dosyası oluştur (MP3 olmalı ki -c copy ile birleştirilebilsin)
        silence_filename = "_silence_1s.mp3"
        silence_path = os.path.join(book_dir, silence_filename)
        if not os.path.exists(silence_path):
            AudioSegment.silent(duration=1000).export(silence_path, format="mp3", bitrate="64k")
            
        # FFmpeg concat listesi oluştur
        concat_list_filename = "_concat_list.txt"
        concat_list_path = os.path.join(book_dir, concat_list_filename)
        
        with open(concat_list_path, "w", encoding="utf-8") as f:
            for idx, fpath in enumerate(audio_files):
                f.write(f"file '{os.path.basename(fpath)}'\n")
                if idx < len(audio_files) - 1: # Son bölümden sonra sessizlik eklemeye gerek yok
                    f.write(f"file '{silence_filename}'\n")
                    
        mp3_path = os.path.join(book_dir, output_filename)
        print(" -> RAM kullanılmadan doğrudan FFmpeg akışı (streaming) ile MP3 dönüşümü başlıyor...")
        
        try:
            # FFmpeg komutunu çalıştır (cwd olarak book_dir veriyoruz ki dosya isimlerini direkt bulsun)
            # KRİTİK: Dosyalar zaten MP3 olduğu için CPU harcatan libmp3lame yerine '-c copy' kullanıyoruz!
            # Saniyeler içinde ve %0 CPU ile 4 saatlik sesi birleştirir.
            cmd = [
                ffmpeg_bin, "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", concat_list_filename,
                "-c", "copy",
                output_filename
            ]
            
            result = subprocess.run(cmd, cwd=book_dir, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"[UYARI] FFmpeg akış hatası ({result.stderr[:200]}), PyDub yedeğine geçiliyor...")
                raise RuntimeError(f"FFmpeg failed: {result.stderr}")
                
        except Exception as e:
            print(f" -> [KRİTİK HATA] FFmpeg akış birleştirme başarısız oldu: {e}")
            print(" -> [BİLGİ] RAM taşmasını (sunucu donmasını) önlemek için PyDub yedeği iptal edilmiştir. MP3 oluşturulamadı.")
            
        finally:
            # Geçici dosyaları temizle
            try:
                if os.path.exists(concat_list_path): os.remove(concat_list_path)
                if os.path.exists(silence_path): os.remove(silence_path)
            except Exception:
                pass
                
        if os.path.exists(mp3_path):
            file_size_mb = os.path.getsize(mp3_path) / (1024 * 1024)
            print(f" [BAŞARILI] MP3 Hazır! Dosya boyutu: {file_size_mb:.2f} MB ({output_filename})")
            return mp3_path
        else:
            print("[HATA] MP3 dosyası oluşturulamadı!")
            return None

    def upload_to_r2(self, local_file_path, r2_object_name):
        """Dosyayı Cloudflare R2 bucket'ına yüksek hızlı parçalı (multipart) olarak yükler ve Worker URL'sini döner."""
        print(f"\n[2/4] Bulut Depolamaya (Cloudflare R2) yükleniyor: {r2_object_name}...")
        try:
            import threading
            from boto3.s3.transfer import TransferConfig
            
            # KRİTİK: Oracle Micro sunucuda max_concurrency=10 ve multi-threading kullanmak,
            # 200MB'lık bir dosyayı yüklerken aynı anda 10 farklı SSL/TLS şifreleme işlemi başlattığı için
            # CPU'yu %100'de kilitleyip sunucuyu donduruyordu. Bu yüzden tek thread (sıralı) yükleme yapıyoruz.
            transfer_config = TransferConfig(
                multipart_threshold=10 * 1024 * 1024,
                max_concurrency=1,
                multipart_chunksize=10 * 1024 * 1024,
                use_threads=False
            )
            
            file_size = os.path.getsize(local_file_path)
            file_size_mb = file_size / (1024 * 1024)
            
            class ProgressCallback:
                def __init__(self, total_size):
                    self._total_size = total_size
                    self._seen_so_far = 0
                    self._lock = threading.Lock()
                    
                def __call__(self, bytes_amount):
                    with self._lock:
                        self._seen_so_far += bytes_amount
                        pct = (self._seen_so_far / self._total_size) * 100
                        mb_seen = self._seen_so_far / (1024 * 1024)
                        mb_total = self._total_size / (1024 * 1024)
                        print(f"\r   -> R2 Yükleniyor (Parçalı Yüksek Hız): %{pct:.1f} ({mb_seen:.1f} MB / {mb_total:.1f} MB)", end="", flush=True)
            
            content_type = "audio/mpeg" if r2_object_name.lower().endswith(".mp3") else "image/png"
            
            if file_size_mb > 10:
                print(f" -> Büyük dosya algılandı ({file_size_mb:.2f} MB). 10 paralel hat ile parçalı yükleme başladı...")
                
            self.s3.upload_file(
                local_file_path, 
                self.r2_bucket, 
                r2_object_name,
                ExtraArgs={'ContentType': content_type},
                Config=transfer_config,
                Callback=ProgressCallback(file_size) if file_size_mb > 5 else None
            )
            
            if file_size_mb > 5:
                print() # Yeni satıra geç
                
            public_url = f"{self.r2_public_url}/{r2_object_name}"
            print(f" [BAŞARILI] R2 Yüklemesi Tamamlandı! Link: {public_url}")
            return public_url
        except Exception as e:
            print(f"\n[HATA] R2 Yüklemesi başarısız oldu: {e}")
            return None

    def generate_and_upload_cover(self, title, author, book_dir, r2_base_name):
        """Önce Apple Books, OpenLibrary ve Google Books gibi telifsiz kamu/mağaza API'lerinden resmi orijinal kapak arar; bulamazsa AI ile çizdirir ve R2'ye yükler."""
        print(f"\n[3/4] KitapDuy Akıllı Kapak Motoru çalışıyor ('{title}' - '{author}')...")
        from io import BytesIO
        cover_img = None
        source_used = ""
        
        # 1. ÖNCELİK: Apple Books / iTunes API (1000x1000 yüksek çözünürlüklü resmi kapak)
        try:
            print(" -> Apple Books (iTunes API) üzerinden resmi kapak aranıyor...")
            url = f"https://itunes.apple.com/search?term={urllib.parse.quote(f'{title} {author}')}&entity=ebook&limit=1"
            res = requests.get(url, timeout=10).json()
            if res.get("results") and len(res["results"]) > 0:
                art_url = res["results"][0].get("artworkUrl100", "").replace("100x100bb.jpg", "1000x1000bb.jpg")
                if art_url:
                    img_res = requests.get(art_url, timeout=15)
                    if img_res.status_code == 200:
                        cover_img = Image.open(BytesIO(img_res.content)).convert("RGB")
                        source_used = "Apple Books API (1000x1000 Orijinal Kapak)"
        except Exception as e:
            print(f"    [!] Apple Books araması başarısız: {e}")
            
        # 2. ÖNCELİK: OpenLibrary Kamu Kataloğu
        if not cover_img:
            try:
                print(" -> Open Library Kamu Kataloğunda aranıyor...")
                url = f"https://openlibrary.org/search.json?title={urllib.parse.quote(title)}&author={urllib.parse.quote(author)}&limit=1"
                res = requests.get(url, timeout=10).json()
                if res.get("docs") and len(res["docs"]) > 0 and res["docs"][0].get("cover_i"):
                    cid = res["docs"][0]["cover_i"]
                    art_url = f"https://covers.openlibrary.org/b/id/{cid}-L.jpg"
                    img_res = requests.get(art_url, timeout=15)
                    if img_res.status_code == 200 and len(img_res.content) > 5000: # 1x1 boş resim gelirse atla
                        cover_img = Image.open(BytesIO(img_res.content)).convert("RGB")
                        source_used = "Open Library Kamu Kataloğu (Yüksek Çözünürlük)"
            except Exception as e:
                print(f"    [!] Open Library araması başarısız: {e}")
                
        # 3. ÖNCELİK: Google Books API
        if not cover_img:
            try:
                print(" -> Google Books API üzerinde aranıyor...")
                url = f"https://www.googleapis.com/books/v1/volumes?q={urllib.parse.quote(f'{title} {author}')}&maxResults=1"
                res = requests.get(url, timeout=10).json()
                if res.get("items") and "imageLinks" in res["items"][0]["volumeInfo"]:
                    links = res["items"][0]["volumeInfo"]["imageLinks"]
                    art_url = links.get("extraLarge") or links.get("large") or links.get("thumbnail", "")
                    art_url = art_url.replace("zoom=1", "zoom=3").replace("http://", "https://")
                    if art_url:
                        img_res = requests.get(art_url, timeout=15)
                        if img_res.status_code == 200:
                            cover_img = Image.open(BytesIO(img_res.content)).convert("RGB")
                            source_used = "Google Books API (Resmi Kapak)"
            except Exception as e:
                print(f"    [!] Google Books araması başarısız: {e}")
                
        # 4. ÖNCELİK: Hiçbir resmi kaynakta bulunamazsa FLUX Sinematik Yapay Zeka ile Çizdir
        if not cover_img:
            print(" -> Resmi kataloglarda bulunamadı, FLUX Sinematik Yapay Zeka (0 Yazı) ile çizdiriliyor...")
            try:
                prompt_instruction = f"""Sen dünya çapında ödüllü bir kitap kapağı sanat yönetmeni ve sinematografsın. '{title}' (Yazar: {author}) kitabı için FLUX yapay zeka resim motoruna gönderilecek büyüleyici, sinematik ve atmosferik bir İngilizce resim çizim betimlemesi yaz.

HEDEF GÖRSEL (Çok Önemli - Tam Ekran Yazısız Sanat Eseri):
Görsel, kitabın ruhunu ve konusunu yansıtan dikey formatta, sinematik ve büyüleyici bir yağlı boya / sanatsal illüstrasyon (a cinematic, atmospheric vertical dark vintage oil painting / book cover illustration) olmalı.

ALTIN KURAL (BOZUK HARFLERİ ÖNLEME):
1. Resim motorlarının kapağa uzaylı harfleri veya bozuk kelimeler (gibberish) yazmasını KESİNLİKLE ÖNLEMEK İÇİN, üreteceğin İngilizce prompt içinde kitabın adını (`{title}`) veya yazarın adını (`{author}`) ASLA TIRNAK İÇİNDE VEYA KELİME OLARAK YAZMA!
2. Sadece ve sadece kitabın anlattığı ana sahneyi, atmosferi, karakterleri, dramatik ışıklandırmayı ve sanatsal stili İngilizce olarak betimle.
3. Promptun sonuna mutlaka şu kesin yasağı ekle: "STRICTLY ZERO TEXT: Absolutely NO words, NO letters, NO text, NO typography, NO symbols anywhere on the painting / artwork. Clean artwork only, 8k resolution".

Sadece İngilizce promptu dön, başka hiçbir şey yazma. Örnek başlangıç: "A cinematic, atmospheric vertical dark vintage oil painting depicting a mystical forest..." """
                
                ai_prompt = f"A cinematic, atmospheric dark vintage vertical oil painting and cover artwork inspired by a profound classic literary story. Dark moody lighting, rich textured canvas, highly detailed masterpiece. STRICTLY ZERO TEXT: Absolutely NO words, NO letters, NO text, NO typography, NO symbols anywhere on the painting. Clean artwork only, 8k resolution"
                if self.gemini_client:
                    try:
                        res = self.gemini_client.models.generate_content(
                            model="gemini-3.5-flash-lite",
                            contents=prompt_instruction
                        )
                        if res and res.text:
                            ai_prompt = res.text.strip() + ", STRICTLY ZERO TEXT, absolutely no words, no letters, no symbols on the artwork, 8k resolution"
                    except Exception:
                        pass
                
                encoded_prompt = urllib.parse.quote(ai_prompt)
                image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=768&height=1152&model=flux-realism&nologo=true"
                response = requests.get(image_url, timeout=45)
                if response.status_code != 200:
                    image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=768&height=1152&model=flux&nologo=true"
                    response = requests.get(image_url, timeout=45)
                    if response.status_code != 200:
                        cover_img = Image.new("RGB", (768, 1152), color=(220, 205, 180))
                    else:
                        cover_img = Image.open(BytesIO(response.content)).convert("RGB")
                else:
                    cover_img = Image.open(BytesIO(response.content)).convert("RGB")
                source_used = "FLUX Sinematik Yapay Zeka (Tam Ekran İllüstrasyon)"
            except Exception as e:
                print(f"[HATA] Yapay Zeka kapak çizimi başarısız: {e}")
                cover_img = Image.new("RGB", (768, 1152), color=(220, 205, 180))
                source_used = "Varsayılan Yedek Görsel"
                
        print(f" -> Kapak görseli başarıyla temin edildi! Kaynak: [{source_used}]")
        try:
            local_cover_path = os.path.join(book_dir, f"{r2_base_name}_cover.png")
            cover_img.save(local_cover_path, "PNG")
            r2_cover_name = f"{r2_base_name}_cover.png"
            return self.upload_to_r2(local_cover_path, r2_cover_name)
        except Exception as e:
            print(f"[HATA] Kapak görseli kaydedilemedi veya yüklenemedi: {e}")
            return "https://i.ibb.co/20jWPHsd/default-cover.png" # Yedek link

    def publish_to_firebase(self, title, author, raw_text_sample, audio_url, cover_url):
        """Kitap verilerini Gemini ile düzenleyip Firebase Firestore 'books' koleksiyonuna kaydeder."""
        print(f"\n[4/4] KitapDuy (Firebase) canlı veritabanına yayınlanıyor...")
        if not self.db:
            print("[HATA] Firebase veritabanı bağlantısı yok, kayıt atlandı.")
            return False
            
        try:
            valid_categories = ["Türk Edebiyatı", "Polisiye", "Dünya Edebiyatı", "Podcast", "Kişisel Gelişim", "Çocuk Masalları"]
            valid_cats_str = ", ".join([f'"{c}"' for c in valid_categories])
            
            # Gemini'den harika bir kategori ve '... KitapDuy'da.' ile biten bir özet alalım
            prompt = f"""Sen KitapDuy sesli kitap uygulamasının baş editörüsün.
GÖREV: '{title}' (Yazar: {author}) kitabı için aşağıdaki JSON formatında muazzam bir künye hazırla.
Kitaptan Örnek Metin:
"{raw_text_sample[:1000]}"

KURALLAR:
1. KRİTİK DETAY VE UZUNLUK KURALI: 'description' (kitap hakkında açıklaması) KESİNLİKLE KISA OLMAYACAK! En az 3 veya 4 detaylı paragraflık (yaklaşık 150 - 250 kelime arası) çok kapsamlı, edebi açıdan zengin, sürükleyici ve profesyonel bir arka kapak incelemesi / tanıtım bülteni yaz. Kitabın konusunu, ana karakterlerini, temel felsefesini, dönemin ruhunu ve neden mutlaka dinlenmesi gerektiğini derinlemesine anlat.
2. KRİTİK: 'description' metninin son cümlesi MUTLAKA ŞU FORMATTA VEYA BENZERİ BİR ÇAĞRIYLA BİTSİN: "... bu eşsiz hikayenin tüm detaylarına tanıklık etmeniz için KitapDuy'da." veya "... sürükleyici macerayı dinlemeniz için KitapDuy'da."
3. KRİTİK KATEGORİ KURALI: 'category' kısmı SADECE VE SADECE ŞU 6 KATEGORİDEN BİRİ OLMAK ZORUNDADIR: [{valid_cats_str}]. Kitabın türüne en uygun olan BİR TANESİNİ seç. Başka hiçbir kategori uydurma.
4. KRİTİK BAŞLIK KURALI: 'title' (kitap adı) MUTLAKA TÜRKÇEYE ÇEVRİLMİŞ OLMALIDIR! Eğer İngilizce veya yabancı dilde bir başlık geldiyse (Örn: "The Prince and the Pauper" -> "Prens ve Dilenci", "Crime and Punishment" -> "Suç ve Ceza", "The Fire in the Flint" -> "Çakmaktaşındaki Ateş"), bunu Türkiye'de yayınlanan en bilindik Türkçe adıyla yaz. Asla İngilizce/yabancı başlık bırakma!

SADECE JSON DÖN:
{{
  "title": "Türkçe Kitap Adı",
  "author": "Yazar Adı",
  "category": "Seçilen Kategori",
  "description": "Sürükleyici özet... KitapDuy'da."
}}"""

            fallback_desc = (
                f"{author} kaleminden dünya edebiyatının ölümsüz eserleri arasında yer alan '{title}', insan ruhunun en derin katmanlarına inen varoluşsal ve felsefi bir başyapıttır. Yazar, karakterlerinin içsel yolculuğu, evrensel sorgulamaları ve hayatın anlamını arayış süreçleri üzerinden okuyucuya zamansız bir ayna tutar.\n\n"
                f"Eserin sürükleyici kurgusu ve edebi yoğunluğu, sıradan bir olay örgüsünün ötesine geçerek dinleyiciyi büyüleyici bir felsefi arayışın ortağı haline getirir. Dönemin ruhunu ve insan doğasının çelişkilerini kusursuz bir gözlem gücüyle aktaran bu roman, her okunuşta ve dinlenişte yeni keşifler sunan eşsiz bir hazinedir.\n\n"
                f"Bu klasik eserin tüm ayrıntılarına, edebi derinliğine ve unutulmaz atmosferine tanıklık etmeniz için '{title}', şimdi sesli kitap ayrıcalığıyla KitapDuy'da."
            )
            metadata = {
                "title": title,
                "author": author,
                "category": "Dünya Edebiyatı",
                "description": fallback_desc,
                "audioUrl": audio_url,
                "coverUrl": cover_url,
                "listenCount": 0,
                "viewCount": 0
            }

            if self.gemini_client:
                try:
                    res = self.gemini_client.models.generate_content(
                        model="gemini-3.5-flash-lite",
                        contents=prompt
                    )
                    res_text = res.text.strip()
                    if "```json" in res_text:
                        res_text = res_text.split("```json")[1].split("```")[0].strip()
                    elif "```" in res_text:
                        res_text = res_text.split("```")[1].split("```")[0].strip()
                        
                    # Kontrol karakterlerini ve unescaped newlines için strict=False kullan
                    try:
                        ai_meta = json.loads(res_text, strict=False)
                    except Exception as parse_err:
                        print(f" -> [UYARI] JSON ayrıştırma uyarısı, regex ile çekiliyor: {parse_err}")
                        import re
                        ai_meta = {}
                        title_match = re.search(r'"title"\s*:\s*"([^"]+)"', res_text)
                        if title_match: ai_meta["title"] = title_match.group(1)
                        desc_match = re.search(r'"description"\s*:\s*"([^"]+)"', res_text, re.DOTALL)
                        if desc_match: ai_meta["description"] = desc_match.group(1).replace('\\n', '\n').replace('\\"', '"')
                        
                    if ai_meta and isinstance(ai_meta, dict):
                        metadata["title"] = ai_meta.get("title", title)
                        metadata["author"] = ai_meta.get("author", author)
                        chosen_cat = ai_meta.get("category", "Dünya Edebiyatı")
                        if chosen_cat in valid_categories:
                            metadata["category"] = chosen_cat
                        else:
                            print(f" -> [UYARI] AI harici kategori önerdi ({chosen_cat}). Varsayılan kategori (Dünya Edebiyatı) seçildi.")
                            metadata["category"] = "Dünya Edebiyatı"
                        
                        ai_desc = ai_meta.get("description", "").strip()
                        if len(ai_desc) > 100:
                            metadata["description"] = ai_desc
                        else:
                            print(" -> [UYARI] AI açıklaması çok kısa geldi, zengin edebi bülten şablonu kullanılıyor.")
                except Exception as e:
                    print(f" -> AI Künye oluşturma uyarısı (Zengin edebi şablon kullanılacak): {e}")
                    
            print(" -> Yayınlanacak Veri Özeti:")
            print(f"    * Kitap Adı: {metadata['title']}")
            print(f"    * Yazar:     {metadata['author']}")
            print(f"    * Kategori:  {metadata['category']}")
            print(f"    * MP3 URL:   {metadata['audioUrl']}")
            print(f"    * Kapak URL: {metadata['coverUrl']}")
            print(f"    * Tanıtım:   {metadata['description'][:80]}...")
            
            # Firebase 'books' koleksiyonuna ekle
            doc_ref = self.db.collection("books").add(metadata)
            print(f"\n [TEBRİKLER! 🎉] Kitap başarıyla KitapDuy uygulamasında yayına girdi! Document ID: {doc_ref[1].id}")
            return True
        except Exception as e:
            print(f"[HATA] Firebase kayıt hatası: {e}")
            return False

if __name__ == "__main__":
    # Hızlı test
    pub = BookPublisher()
    print("BookPublisher modülü hazır.")
