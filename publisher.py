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
        
        # R2 S3 ─░stemcisini Ba┼şlat
        self.s3 = boto3.client('s3',
            endpoint_url=self.r2_endpoint,
            aws_access_key_id=self.r2_access_key,
            aws_secret_access_key=self.r2_secret_key
        )
        
        # Firebase Firestore'u Ba┼şlat (E─şer hen├╝z ba┼şlat─▒lmad─▒ysa)
        self._init_firebase()

    def _init_firebase(self):
        try:
            from firebase_setup import get_firebase_cred
            if not firebase_admin._apps:
                cred = get_firebase_cred()
                firebase_admin.initialize_app(cred)
            self.db = firestore.client()
            print("[B─░LG─░] Firebase Firestore ba─şlant─▒s─▒ haz─▒r.")
        except Exception as e:
            print(f"[UYARI] Firebase ba┼şlat─▒lamad─▒: {e}")
            self.db = None

    def merge_audio_to_mp3(self, book_dir, output_filename):
        """Klas├Ârdeki t├╝m b├Âl├╝m .wav dosyalar─▒n─▒ s─▒ras─▒yla birle┼ştirip tek bir MP3 yapar."""
        print(f"\n[1/4] B├Âl├╝mler birle┼ştiriliyor ve MP3 formata d├Ân├╝┼şt├╝r├╝l├╝yor ({book_dir})...")
        import re
        import subprocess
        
        # 1. Dosyalar─▒ numara s─▒ras─▒na g├Âre kesin ve do─şru s─▒rala (bolum_1, bolum_2 ... bolum_702)
        def get_chapter_num(path):
            match = re.search(r'bolum_(\d+)\.(mp3|wav)$', os.path.basename(path), re.IGNORECASE)
            return int(match.group(1)) if match else 0
            
        audio_files = sorted(glob.glob(os.path.join(book_dir, "bolum_*.mp3")) + glob.glob(os.path.join(book_dir, "bolum_*.wav")), key=get_chapter_num)
        
        if not audio_files:
            print("[HATA] Birle┼ştirilecek b├Âl├╝m dosyas─▒ bulunamad─▒!")
            return None
            
        print(f" -> Toplam {len(audio_files)} b├Âl├╝m dosyas─▒ do─şru say─▒sal s─▒rayla bulundu.")
        
        # 4 GB WAV s─▒n─▒r─▒n─▒ ve RAM ta┼şmas─▒n─▒ ├Ânlemek i├ğin do─şrudan FFmpeg Ak─▒┼ş (Streaming Concat) Y├Ântemi:
        import platform
        local_ffmpeg = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ffmpeg.exe")
        if platform.system() == "Windows" and os.path.exists(local_ffmpeg):
            ffmpeg_bin = local_ffmpeg
        else:
            ffmpeg_bin = "ffmpeg"
        
        # 1 saniyelik sessizlik dosyas─▒ olu┼ştur (MP3 olmal─▒ ki -c copy ile birle┼ştirilebilsin)
        silence_filename = "_silence_1s.mp3"
        silence_path = os.path.join(book_dir, silence_filename)
        if not os.path.exists(silence_path):
            AudioSegment.silent(duration=1000).export(silence_path, format="mp3", bitrate="64k")
            
        # FFmpeg concat listesi olu┼ştur
        concat_list_filename = "_concat_list.txt"
        concat_list_path = os.path.join(book_dir, concat_list_filename)
        
        with open(concat_list_path, "w", encoding="utf-8") as f:
            for idx, fpath in enumerate(audio_files):
                f.write(f"file '{os.path.basename(fpath)}'\n")
                if idx < len(audio_files) - 1: # Son b├Âl├╝mden sonra sessizlik eklemeye gerek yok
                    f.write(f"file '{silence_filename}'\n")
                    
        mp3_path = os.path.join(book_dir, output_filename)
        print(" -> RAM kullan─▒lmadan do─şrudan FFmpeg ak─▒┼ş─▒ (streaming) ile MP3 d├Ân├╝┼ş├╝m├╝ ba┼şl─▒yor...")
        
        try:
            # FFmpeg komutunu ├ğal─▒┼şt─▒r (cwd olarak book_dir veriyoruz ki dosya isimlerini direkt bulsun)
            # KR─░T─░K: Dosyalar zaten MP3 oldu─şu i├ğin CPU harcatan libmp3lame yerine '-c copy' kullan─▒yoruz!
            # Saniyeler i├ğinde ve %0 CPU ile 4 saatlik sesi birle┼ştirir.
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
                print(f"[UYARI] FFmpeg ak─▒┼ş hatas─▒ ({result.stderr[:200]}), PyDub yede─şine ge├ğiliyor...")
                raise RuntimeError(f"FFmpeg failed: {result.stderr}")
                
        except Exception as e:
            print(f" -> [KR─░T─░K HATA] FFmpeg ak─▒┼ş birle┼ştirme ba┼şar─▒s─▒z oldu: {e}")
            print(" -> [B─░LG─░] RAM ta┼şmas─▒n─▒ (sunucu donmas─▒n─▒) ├Ânlemek i├ğin PyDub yede─şi iptal edilmi┼ştir. MP3 olu┼şturulamad─▒.")
            
        finally:
            # Ge├ğici dosyalar─▒ temizle
            try:
                if os.path.exists(concat_list_path): os.remove(concat_list_path)
                if os.path.exists(silence_path): os.remove(silence_path)
            except Exception:
                pass
                
        if os.path.exists(mp3_path):
            file_size_mb = os.path.getsize(mp3_path) / (1024 * 1024)
            print(f" [BA┼ŞARILI] MP3 Haz─▒r! Dosya boyutu: {file_size_mb:.2f} MB ({output_filename})")
            return mp3_path
        else:
            print("[HATA] MP3 dosyas─▒ olu┼şturulamad─▒!")
            return None

    def upload_to_r2(self, local_file_path, r2_object_name):
        """Dosyay─▒ Cloudflare R2 bucket'─▒na y├╝ksek h─▒zl─▒ par├ğal─▒ (multipart) olarak y├╝kler ve Worker URL'sini d├Âner."""
        print(f"\n[2/4] Bulut Depolamaya (Cloudflare R2) y├╝kleniyor: {r2_object_name}...")
        try:
            import threading
            from boto3.s3.transfer import TransferConfig
            
            # KR─░T─░K: Oracle Micro sunucuda max_concurrency=10 ve multi-threading kullanmak,
            # 200MB'l─▒k bir dosyay─▒ y├╝klerken ayn─▒ anda 10 farkl─▒ SSL/TLS ┼şifreleme i┼şlemi ba┼şlatt─▒─ş─▒ i├ğin
            # CPU'yu %100'de kilitleyip sunucuyu donduruyordu. Bu y├╝zden tek thread (s─▒ral─▒) y├╝kleme yap─▒yoruz.
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
                        print(f"\r   -> R2 Y├╝kleniyor (Par├ğal─▒ Y├╝ksek H─▒z): %{pct:.1f} ({mb_seen:.1f} MB / {mb_total:.1f} MB)", end="", flush=True)
            
            content_type = "audio/mpeg" if r2_object_name.lower().endswith(".mp3") else "image/png"
            
            if file_size_mb > 10:
                print(f" -> B├╝y├╝k dosya alg─▒land─▒ ({file_size_mb:.2f} MB). 10 paralel hat ile par├ğal─▒ y├╝kleme ba┼şlad─▒...")
                
            self.s3.upload_file(
                local_file_path, 
                self.r2_bucket, 
                r2_object_name,
                ExtraArgs={'ContentType': content_type},
                Config=transfer_config,
                Callback=ProgressCallback(file_size) if file_size_mb > 5 else None
            )
            
            if file_size_mb > 5:
                print() # Yeni sat─▒ra ge├ğ
                
            public_url = f"{self.r2_public_url}/{r2_object_name}"
            print(f" [BA┼ŞARILI] R2 Y├╝klemesi Tamamland─▒! Link: {public_url}")
            return public_url
        except Exception as e:
            print(f"\n[HATA] R2 Y├╝klemesi ba┼şar─▒s─▒z oldu: {e}")
            return None

    def generate_and_upload_cover(self, title, author, book_dir, r2_base_name):
        """├ûnce Apple Books, OpenLibrary ve Google Books gibi telifsiz kamu/ma─şaza API'lerinden resmi orijinal kapak arar; bulamazsa AI ile ├ğizdirir ve R2'ye y├╝kler."""
        print(f"\n[3/4] KitapDuy Ak─▒ll─▒ Kapak Motoru ├ğal─▒┼ş─▒yor ('{title}' - '{author}')...")
        from io import BytesIO
        cover_img = None
        source_used = ""
        
        # 1. ├ûNCEL─░K: Apple Books / iTunes API (1000x1000 y├╝ksek ├ğ├Âz├╝n├╝rl├╝kl├╝ resmi kapak)
        try:
            print(" -> Apple Books (iTunes API) ├╝zerinden resmi kapak aran─▒yor...")
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
            print(f"    [!] Apple Books aramas─▒ ba┼şar─▒s─▒z: {e}")
            
        # 2. ├ûNCEL─░K: OpenLibrary Kamu Katalo─şu
        if not cover_img:
            try:
                print(" -> Open Library Kamu Katalo─şunda aran─▒yor...")
                url = f"https://openlibrary.org/search.json?title={urllib.parse.quote(title)}&author={urllib.parse.quote(author)}&limit=1"
                res = requests.get(url, timeout=10).json()
                if res.get("docs") and len(res["docs"]) > 0 and res["docs"][0].get("cover_i"):
                    cid = res["docs"][0]["cover_i"]
                    art_url = f"https://covers.openlibrary.org/b/id/{cid}-L.jpg"
                    img_res = requests.get(art_url, timeout=15)
                    if img_res.status_code == 200 and len(img_res.content) > 5000: # 1x1 bo┼ş resim gelirse atla
                        cover_img = Image.open(BytesIO(img_res.content)).convert("RGB")
                        source_used = "Open Library Kamu Katalo─şu (Y├╝ksek ├ç├Âz├╝n├╝rl├╝k)"
            except Exception as e:
                print(f"    [!] Open Library aramas─▒ ba┼şar─▒s─▒z: {e}")
                
        # 3. ├ûNCEL─░K: Google Books API
        if not cover_img:
            try:
                print(" -> Google Books API ├╝zerinde aran─▒yor...")
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
                print(f"    [!] Google Books aramas─▒ ba┼şar─▒s─▒z: {e}")
                
        # 4. ├ûNCEL─░K: Hi├ğbir resmi kaynakta bulunamazsa FLUX Sinematik Yapay Zeka ile ├çizdir
        if not cover_img:
            print(" -> Resmi kataloglarda bulunamad─▒, FLUX Sinematik Yapay Zeka (0 Yaz─▒) ile ├ğizdiriliyor...")
            try:
                prompt_instruction = f"""Sen d├╝nya ├ğap─▒nda ├Âd├╝ll├╝ bir kitap kapa─ş─▒ sanat y├Ânetmeni ve sinematografs─▒n. '{title}' (Yazar: {author}) kitab─▒ i├ğin FLUX yapay zeka resim motoruna g├Ânderilecek b├╝y├╝leyici, sinematik ve atmosferik bir ─░ngilizce resim ├ğizim betimlemesi yaz.

HEDEF G├ûRSEL (├çok ├ûnemli - Tam Ekran Yaz─▒s─▒z Sanat Eseri):
G├Ârsel, kitab─▒n ruhunu ve konusunu yans─▒tan dikey formatta, sinematik ve b├╝y├╝leyici bir ya─şl─▒ boya / sanatsal ill├╝strasyon (a cinematic, atmospheric vertical dark vintage oil painting / book cover illustration) olmal─▒.

ALTIN KURAL (BOZUK HARFLER─░ ├ûNLEME):
1. Resim motorlar─▒n─▒n kapa─şa uzayl─▒ harfleri veya bozuk kelimeler (gibberish) yazmas─▒n─▒ KES─░NL─░KLE ├ûNLEMEK ─░├ç─░N, ├╝retece─şin ─░ngilizce prompt i├ğinde kitab─▒n ad─▒n─▒ (`{title}`) veya yazar─▒n ad─▒n─▒ (`{author}`) ASLA TIRNAK ─░├ç─░NDE VEYA KEL─░ME OLARAK YAZMA!
2. Sadece ve sadece kitab─▒n anlatt─▒─ş─▒ ana sahneyi, atmosferi, karakterleri, dramatik ─▒┼ş─▒kland─▒rmay─▒ ve sanatsal stili ─░ngilizce olarak betimle.
3. Promptun sonuna mutlaka ┼şu kesin yasa─ş─▒ ekle: "STRICTLY ZERO TEXT: Absolutely NO words, NO letters, NO text, NO typography, NO symbols anywhere on the painting / artwork. Clean artwork only, 8k resolution".

Sadece ─░ngilizce promptu d├Ân, ba┼şka hi├ğbir ┼şey yazma. ├ûrnek ba┼şlang─▒├ğ: "A cinematic, atmospheric vertical dark vintage oil painting depicting a mystical forest..." """
                
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
                source_used = "FLUX Sinematik Yapay Zeka (Tam Ekran ─░ll├╝strasyon)"
            except Exception as e:
                print(f"[HATA] Yapay Zeka kapak ├ğizimi ba┼şar─▒s─▒z: {e}")
                cover_img = Image.new("RGB", (768, 1152), color=(220, 205, 180))
                source_used = "Varsay─▒lan Yedek G├Ârsel"
                
        print(f" -> Kapak g├Ârseli ba┼şar─▒yla temin edildi! Kaynak: [{source_used}]")
        try:
            local_cover_path = os.path.join(book_dir, f"{r2_base_name}_cover.png")
            cover_img.save(local_cover_path, "PNG")
            r2_cover_name = f"{r2_base_name}_cover.png"
            return self.upload_to_r2(local_cover_path, r2_cover_name)
        except Exception as e:
            print(f"[HATA] Kapak g├Ârseli kaydedilemedi veya y├╝klenemedi: {e}")
            return "https://i.ibb.co/20jWPHsd/default-cover.png" # Yedek link

    def publish_to_firebase(self, title, author, raw_text_sample, audio_url, cover_url):
        """Kitap verilerini Gemini ile d├╝zenleyip Firebase Firestore 'books' koleksiyonuna kaydeder."""
        print(f"\n[4/4] KitapDuy (Firebase) canl─▒ veritaban─▒na yay─▒nlan─▒yor...")
        if not self.db:
            print("[HATA] Firebase veritaban─▒ ba─şlant─▒s─▒ yok, kay─▒t atland─▒.")
            return False
            
        try:
            valid_categories = ["T├╝rk Edebiyat─▒", "Polisiye", "D├╝nya Edebiyat─▒", "Podcast", "Ki┼şisel Geli┼şim", "├çocuk Masallar─▒"]
            valid_cats_str = ", ".join([f'"{c}"' for c in valid_categories])
            
            # Gemini'den harika bir kategori ve '... KitapDuy'da.' ile biten bir ├Âzet alal─▒m
            prompt = f"""Sen KitapDuy sesli kitap uygulamas─▒n─▒n ba┼ş edit├Âr├╝s├╝n.
G├ûREV: '{title}' (Yazar: {author}) kitab─▒ i├ğin a┼şa─ş─▒daki JSON format─▒nda muazzam bir k├╝nye haz─▒rla.
Kitaptan ├ûrnek Metin:
"{raw_text_sample[:1000]}"

KURALLAR:
1. KR─░T─░K DETAY VE UZUNLUK KURALI: 'description' (kitap hakk─▒nda a├ğ─▒klamas─▒) KES─░NL─░KLE KISA OLMAYACAK! En az 3 veya 4 detayl─▒ paragrafl─▒k (yakla┼ş─▒k 150 - 250 kelime aras─▒) ├ğok kapsaml─▒, edebi a├ğ─▒dan zengin, s├╝r├╝kleyici ve profesyonel bir arka kapak incelemesi / tan─▒t─▒m b├╝lteni yaz. Kitab─▒n konusunu, ana karakterlerini, temel felsefesini, d├Ânemin ruhunu ve neden mutlaka dinlenmesi gerekti─şini derinlemesine anlat.
2. KR─░T─░K: 'description' metninin son c├╝mlesi MUTLAKA ┼ŞU FORMATTA VEYA BENZER─░ B─░R ├çA─ŞRIYLA B─░TS─░N: "... bu e┼şsiz hikayenin t├╝m detaylar─▒na tan─▒kl─▒k etmeniz i├ğin KitapDuy'da." veya "... s├╝r├╝kleyici maceray─▒ dinlemeniz i├ğin KitapDuy'da."
3. KR─░T─░K KATEGOR─░ KURALI: 'category' k─▒sm─▒ SADECE VE SADECE ┼ŞU 6 KATEGOR─░DEN B─░R─░ OLMAK ZORUNDADIR: [{valid_cats_str}]. Kitab─▒n t├╝r├╝ne en uygun olan B─░R TANES─░N─░ se├ğ. Ba┼şka hi├ğbir kategori uydurma.
4. KR─░T─░K BA┼ŞLIK KURALI: 'title' (kitap ad─▒) MUTLAKA T├£RK├çEYE ├çEVR─░LM─░┼Ş OLMALIDIR! E─şer ─░ngilizce veya yabanc─▒ dilde bir ba┼şl─▒k geldiyse (├ûrn: "The Prince and the Pauper" -> "Prens ve Dilenci", "Crime and Punishment" -> "Su├ğ ve Ceza", "The Fire in the Flint" -> "├çakmakta┼ş─▒ndaki Ate┼ş"), bunu T├╝rkiye'de yay─▒nlanan en bilindik T├╝rk├ğe ad─▒yla yaz. Asla ─░ngilizce/yabanc─▒ ba┼şl─▒k b─▒rakma!

SADECE JSON D├ûN:
{{
  "title": "T├╝rk├ğe Kitap Ad─▒",
  "author": "Yazar Ad─▒",
  "category": "Se├ğilen Kategori",
  "description": "S├╝r├╝kleyici ├Âzet... KitapDuy'da."
}}"""

            fallback_desc = (
                f"{author} kaleminden d├╝nya edebiyat─▒n─▒n ├Âl├╝ms├╝z eserleri aras─▒nda yer alan '{title}', insan ruhunun en derin katmanlar─▒na inen varolu┼şsal ve felsefi bir ba┼şyap─▒tt─▒r. Yazar, karakterlerinin i├ğsel yolculu─şu, evrensel sorgulamalar─▒ ve hayat─▒n anlam─▒n─▒ aray─▒┼ş s├╝re├ğleri ├╝zerinden okuyucuya zamans─▒z bir ayna tutar.\n\n"
                f"Eserin s├╝r├╝kleyici kurgusu ve edebi yo─şunlu─şu, s─▒radan bir olay ├Ârg├╝s├╝n├╝n ├Âtesine ge├ğerek dinleyiciyi b├╝y├╝leyici bir felsefi aray─▒┼ş─▒n orta─ş─▒ haline getirir. D├Ânemin ruhunu ve insan do─şas─▒n─▒n ├ğeli┼şkilerini kusursuz bir g├Âzlem g├╝c├╝yle aktaran bu roman, her okunu┼şta ve dinleni┼şte yeni ke┼şifler sunan e┼şsiz bir hazinedir.\n\n"
                f"Bu klasik eserin t├╝m ayr─▒nt─▒lar─▒na, edebi derinli─şine ve unutulmaz atmosferine tan─▒kl─▒k etmeniz i├ğin '{title}', ┼şimdi sesli kitap ayr─▒cal─▒─ş─▒yla KitapDuy'da."
            )
            metadata = {
                "title": title,
                "author": author,
                "category": "D├╝nya Edebiyat─▒",
                "description": fallback_desc,
                "audioUrl": audio_url,
                "coverUrl": cover_url,
                "listenCount": 0,
                "viewCount": 0
            }

            if True:
                try:
                    import requests
                    import json
                    import time
                    from groq_account_manager import groq_account_manager
                    
                    res_text = ""
                    retry_count = 0
                    
                    while retry_count < len(groq_account_manager.groq_keys):
                        groq_key = groq_account_manager.get_current_groq_key()
                        url = "https://api.groq.com/openai/v1/chat/completions"
                        headers = {"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"}
                        data = {
                            "model": "llama-3.3-70b-versatile",
                            "messages": [{"role": "user", "content": prompt}],
                            "temperature": 0.7
                        }
                        
                        try:
                            resp = requests.post(url, headers=headers, json=data)
                            if resp.status_code == 429:
                                print("  -> [GROQ HATA] Kota doldu, hesap değiştiriliyor...")
                                groq_account_manager.switch_groq_account()
                                retry_count += 1
                                continue
                                
                            resp.raise_for_status()
                            res_text = resp.json()["choices"][0]["message"]["content"].strip()
                            break
                        except Exception as e:
                            print(f"  -> [GROQ UYARI] Groq API hatası: {e}")
                            groq_account_manager.switch_groq_account()
                            retry_count += 1
                            
                    if not res_text:
                        raise Exception("Groq API'den yanıt alınamadı.")
                        
                    if "```json" in res_text:
                        res_text = res_text.split("```json")[1].split("```")[0].strip()
                    elif "```" in res_text:
                        res_text = res_text.split("```")[1].split("```")[0].strip()
                        
                    # Kontrol karakterlerini ve unescaped newlines i├ğin strict=False kullan
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
            print(f"\n [TEBR─░KLER! ­şÄë] Kitap ba┼şar─▒yla KitapDuy uygulamas─▒nda yay─▒na girdi! Document ID: {doc_ref[1].id}")
            return True
        except Exception as e:
            print(f"[HATA] Firebase kay─▒t hatas─▒: {e}")
            return False

if __name__ == "__main__":
    # H─▒zl─▒ test
    pub = BookPublisher()
    print("BookPublisher mod├╝l├╝ haz─▒r.")
