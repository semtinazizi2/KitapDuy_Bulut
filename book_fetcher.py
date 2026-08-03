import requests
import re
import warnings
warnings.filterwarnings("ignore")  # FutureWarning gizle
import google.generativeai as genai
from account_manager import account_manager
import time

class BookFetcher:
    def __init__(self):
        self.setup_gemini()
        
    def setup_gemini(self):
        key = account_manager.get_current_gemini_key()
        if key:
            genai.configure(api_key=key)
            self.model = genai.GenerativeModel('gemini-3.5-flash-lite')
        else:
            self.model = None
            
    def _generate(self, prompt, safety_off=False):
        """Eski google.generativeai SDK ile metin üretir."""
        safety_settings = None
        if safety_off:
            safety_settings = [
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ]
        return self.model.generate_content(prompt, safety_settings=safety_settings)
            
    def download_from_url(self, url):
        """Verilen herhangi bir URL'den sayfanın metin kısmını (HTML'den arındırarak) çeker."""
        print(f"URL'den metin indiriliyor: {url}")
        if "gutenberg.org" not in url.lower():
            print("\n[UYARI] Gutenberg.org dışından bir URL girdiniz (Örn: Gutenberg Australia).")
            print("[UYARI] Bu sitelerdeki bazı kitaplar ABD telif hakları nedeniyle Gemini API tarafından engellenebilir (finish_reason: 8 - RECITATION).")
            print("[UYARI] Telifli paragraflar otomatik olarak atlanıp (<SKIP>) işleme devam edilecektir...\n")
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Gereksiz script ve stil etiketlerini kaldır
                for tag in soup(["script", "style", "nav", "footer", "header"]):
                    tag.extract()

                # KRİTİK: HTML'de paragraflar <p> etiketiyle ayrılır.
                # BeautifulSoup bunları tek \n ile birleştirir, bu da split_into_paragraphs() fonksiyonunun
                # kitabı bölememesine yol açar. Çözüm: Blok elementlere çift newline ekle.
                for tag in soup.find_all(['p', 'br', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'div']):
                    tag.insert_after('\n\n')
                
                text = soup.get_text(separator='\n')
                
                # Üçten fazla boş satırı ikiye indir (aşırı boşlukları temizle)
                text = re.sub(r'\n{3,}', '\n\n', text)
                text = '\n'.join(line.strip() for line in text.splitlines())
                
                self.book_title, self.book_author = self.get_book_metadata(text)
                return self._find_story_start(text)
            else:
                print(f"HATA: URL'ye erişilemedi. (Status: {response.status_code})")
                return None
        except Exception as e:
            print(f"HATA: URL okunurken bir sorun oluştu: {e}")
            return None
    def get_random_gutenberg_id(self):
        """Gutendex API kullanarak rastgele, İngilizce ve okunmamış bir popüler kitap ID'si bulur."""
        print("[OTONOM] Yeni bir rastgele İngilizce kitap aranıyor...")
        import random
        import os
        
        completed_file = "completed_books.txt"
        completed_ids = set()
        if os.path.exists(completed_file):
            with open(completed_file, "r") as f:
                completed_ids = set(line.strip() for line in f)
                
        # Rastgele bir sayfadan (1-10) kitapları çek
        page = random.randint(1, 10)
        url = f"https://gutendex.com/books?languages=en&sort=popular&page={page}"
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                books = data.get("results", [])
                random.shuffle(books)
                
                for book in books:
                    book_id = str(book["id"])
                    if book_id not in completed_ids:
                        print(f"[OTONOM] Bulundu! Kitap ID: {book_id} - {book.get('title', 'Unknown')}")
                        return book_id
                        
            print("[OTONOM] Uygun kitap bulunamadı, varsayılan ID döndürülüyor.")
        except Exception as e:
            print(f"[OTONOM HATA] API'ye bağlanılamadı: {e}")
            print("[OTONOM] Fallback: Rastgele bir ID seçiliyor...")
            
        # Fallback: API çökerse manuel rastgele sayı üret
        while True:
            fallback_id = str(random.randint(12, 3000))
            if fallback_id not in completed_ids:
                return fallback_id
    def download_gutenberg_book(self, book_id):
        """Project Gutenberg'den verilen ID ile kitabı indirir."""
        print(f"Gutenberg'den {book_id} ID'li kitap indiriliyor...")
        # Önce modern formatı (Metadata içeren format) dene
        url = f"https://www.gutenberg.org/cache/epub/{book_id}/pg{book_id}.txt"
        response = requests.get(url)
        
        if response.status_code != 200:
            # Alternatif (eski) link formatı
            url = f"https://www.gutenberg.org/files/{book_id}/{book_id}-0.txt"
            response = requests.get(url)
            
        if response.status_code == 200:
            text = response.text
            self.book_title, self.book_author = self.get_book_metadata(text)
            return self._clean_gutenberg_text(text)
        else:
            print(f"HATA: Kitap indirilemedi. (Status: {response.status_code})")
            return None
            
    def _clean_gutenberg_text(self, text):
        """Gutenberg'in başındaki ve sonundaki yasal metinleri temizler ve görselleri/açıklamaları kaldırır."""
        start_marker = "*** START OF THE PROJECT GUTENBERG EBOOK"
        end_marker = "*** END OF THE PROJECT GUTENBERG EBOOK"
        
        start_idx = text.find(start_marker)
        end_idx = text.find(end_marker)
        
        if start_idx != -1:
            # Başlangıç satırının sonuna git
            start_idx = text.find("\n", start_idx) + 1
        else:
            start_idx = 0
            
        if end_idx != -1:
            clean_text = text[start_idx:end_idx].strip()
        else:
            clean_text = text[start_idx:].strip()
        
        # --- GÖRSEL VE AÇIKLAMA TEMİZLEME ---
        # [Illustration: ...], [Image: ...], [Photo: ...], [Figure: ...] gibi tüm köşeli parantez açıklamalarını kaldır
        clean_text = re.sub(r'\[(?:Illustration|Image|Photo|Figure|Footnote|Transcriber|Note|Sidenote|Decoration|Portrait|Map|Plate|Drawing|Caption)[^\]]*\]', '', clean_text, flags=re.IGNORECASE)
        # Birden fazla boş satır bıraktıysa temizle
        clean_text = re.sub(r'\n{3,}', '\n\n', clean_text)
            
        return self._find_story_start(clean_text)

    def _find_story_start(self, text):
        """Yapay zeka (gemini-3.5-flash-lite) kullanarak İçindekiler/Önsözü atlayıp hikayenin gerçek başlangıç noktasını bulur."""
        print("[BİLGİ] Yapay Zeka kitabın asıl başlangıç noktasını (İçindekiler ve Önsözü atlayarak) arıyor...")
        try:
            # Metnin ilk 15000 karakterini AI'ye verelim (İçindekiler vs genelde buradadır)
            sample_text = text[:15000]
            
            prompt = f"""You are an expert literary editor.
I have a book text that contains front matter like "Contents", copyright pages, prefaces, and introductions.
I need to find the EXACT moment the actual narrative/story begins.

Here is the start of the book:
---
{sample_text}
---

Find the exact sentence where the actual story/chapter 1 begins. Skip the Table of Contents, preface, translator's notes, etc.
Return ONLY the first 40 characters of the first sentence of the actual story. DO NOT return anything else. DO NOT wrap it in quotes."""
            
            response = self.model.generate_content(prompt)
            marker = response.text.strip().replace('"', '').replace("'", "")
            
            # AI'nin döndüğü metni asıl metin içinde bul
            if marker and len(marker) > 10:
                idx = text.find(marker[:20]) # İlk 20 karakteri aramak daha güvenli (boşluk uyuşmazlığı vs için)
                if idx != -1:
                    print(f"[BAŞARILI] Hikayenin başlangıcı AI tarafından bulundu: '{marker[:40]}...'")
                    # Eğer başlangıç başlık/bölüm adıysa onu da dahil etmek için biraz geriye (paragraf başına) git
                    while idx > 0 and text[idx-1] != '\n':
                        idx -= 1
                    return text[idx:]
                    
        except Exception as e:
            print(f"[UYARI] AI ile hikaye başlangıcı tespit edilemedi ({e}). Fallback regex kullanılıyor...")

        # Fallback regex
        patterns = [
            r'\n(PART\s+(?:ONE|TWO|THREE|FIRST|SECOND|THIRD|I|II|III|1|2|3))[\s\n]',
            r'\n(BOOK\s+(?:ONE|TWO|THREE|FIRST|SECOND|THIRD|I|II|III|1|2|3))[\s\n]',
            r'\n(VOLUME\s+(?:ONE|TWO|THREE|FIRST|SECOND|I|II|III|1|2|3))[\s\n]',
            r'\n(CHAPTER\s+(?:I|II|III|IV|V|ONE|TWO|THREE|FIRST|1|2|3))[\s\n.:]',
            r'\n(Chapter\s+(?:I|II|III|IV|V|One|Two|Three|First|1|2|3))[\s\n.:]',
        ]

        for pattern in patterns:
            match = re.search(pattern, text[:60000])
            if match:
                start_idx = match.start() + 1
                return text[start_idx:]

        print("[UYARI] Hikaye başlangıcı bulunamadı, metnin tamamı kullanılıyor.")
        return text

    def get_book_metadata(self, text):
        """Gutenberg başlık satırlarından regex ile kitap adını ve yazarını bulur (API çağırılmaz)."""
        # Metadata artık download aşamasında kırpılmadan hemen önce bulundu ve değişkene kaydedildi.
        # Bu fonksiyon fallback olarak duruyor.
        title = getattr(self, 'book_title', "Bilinmeyen Kitap")
        author = getattr(self, 'book_author', "Bilinmeyen Yazar")

        # Eğer hala bulunamadıysa (örneğin yerel dosyadan geldiyse) metnin başına bakarız
        if title == "Bilinmeyen Kitap":
            title_match = re.search(r'^Title:\s*(.+)$', text[:5000], re.MULTILINE | re.IGNORECASE)
            if title_match:
                title = title_match.group(1).strip()

        if author == "Bilinmeyen Yazar":
            author_match = re.search(r'^Author:\s*(.+)$', text[:5000], re.MULTILINE | re.IGNORECASE)
            if author_match:
                author = author_match.group(1).strip()

        self.book_title = title
        self.book_author = author
        return title, author


    def check_and_warn_copyright(self, text, title, author, source=""):
        """Eserin telif haklarıyla korunup korunmadığını kontrol eder ve kullanıcıyı uyarır."""
        print("[BİLGİ] Eserin telif hakkı / kamu malı (Public Domain) durumu kontrol ediliyor...")
        
        is_copyrighted = False
        reason = ""
        
        # 1. Metin içi ve kaynak kontrolü (Hızlı Kontrol)
        text_sample_lower = (text[:4000] + " " + text[-4000:]).lower()
        if "gutenberg australia" in text_sample_lower or "gutenberg.net.au" in str(source).lower() or "gutenberg.net.au" in text_sample_lower:
            is_copyrighted = True
            reason = "Gutenberg Australia kitapları Avustralya'da serbest olsa da ABD telif hukukuna göre (1929 sonrası eserler) hâlâ telifli olabilir."
        elif "all rights reserved" in text_sample_lower or "copyright ©" in text_sample_lower or "her hakkı saklıdır" in text_sample_lower or "protected by copyright" in text_sample_lower:
            is_copyrighted = True
            reason = "Metin içerisinde doğrudan telif hakkı uyarısı ('All rights reserved' / 'Copyright') tespit edildi."
            
        # 2. Yapay Zeka ile Telif Kontrolü
        if not is_copyrighted:
            try:
                prompt = f"""You are a copyright law expert specializing in US copyright and Project Gutenberg.
Analyze this book:
Title: {title}
Author: {author}
Excerpt from opening: {text[:1500]}

Is this work currently PROTECTED BY COPYRIGHT in the United States (i.e. published after 1929, modern translation, or otherwise not in the public domain in the US), or is it known to trigger AI copyright/recitation safety filters?
Respond in EXACTLY this format:
STATUS: [YES if copyrighted or likely to trigger filters, NO if public domain in US]
REASON: [1 brief sentence explaining why in Turkish]"""

                response = self._generate(prompt)
                result = response.text.strip()
                
                if "STATUS: YES" in result or "STATUS: YES".lower() in result.lower():
                    is_copyrighted = True
                    reason_match = re.search(r"REASON:\s*(.+)", result, re.IGNORECASE)
                    if reason_match:
                        reason = reason_match.group(1).strip()
                    else:
                        reason = "Yapay zeka bu eserin ABD telif yasalarına göre koruma altında olduğunu belirtti."
            except Exception as e:
                pass
                
        if is_copyrighted:
            print("\n" + "="*70)
            print(" ⚠️  DİKKAT: TELİF HAKKI (COPYRIGHT) UYARISI!")
            print("="*70)
            print(f" 📖 Kitap: {title} - {author}")
            print(f" 🛑 Tespit: Bu eser TELİFLİ veya AI telif filtrelerine takılma riski yüksek!")
            if reason:
                print(f" 💡 Açıklama: {reason}")
            print("----------------------------------------------------------------------")
            print(" • Gemini API ABD telif yasalarına (1929 sonrası eserler) tabidir.")
            print(" • Telifli paragraf geldiğinde sistem 'finish_reason: 8 (RECITATION)'")
            print("   hatası verecek ve o bölümü atlayacaktır (<SKIP>).")
            print("="*70 + "\n")
            time.sleep(3)
            return True
        else:
            print("[BİLGİ] Telif kontrolü: Eser ABD'de kamu malı (Public Domain) görünüyor. Risk düşük. ✅\n")
            return False

    def split_into_paragraphs(self, text):
        """Metni çeviri ve seslendirme için daha büyük mantıklı bloklara böler (Kota tasarrufu ve bütünlük için)."""
        raw_paragraphs = re.split(r'\n\s*\n', text)
        paragraphs = [p.strip().replace('\n', ' ') for p in raw_paragraphs if len(p.strip()) > 10]
        
        chunks = []
        current_chunk = ""
        
        for p in paragraphs:
            # Paragrafları yaklaşık 1500-1800 karakterlik bloklar halinde birleştir
            if len(current_chunk) + len(p) < 1800:
                current_chunk += p + "\n\n"
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = p + "\n\n"
                
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
            
        return chunks

    def translate_to_turkish(self, text_chunk, previous_context=""):
        """Eski google.generativeai SDK ile edebi bir Türkçe çeviri yapar."""
        
        context_prompt = ""
        if previous_context:
            context_prompt = f"""\n--- BAĞLAM (BUNU ÇEVİRME, SADECE OKU) ---
Karakterlerin kim olduğunu ve olayın nereye gittiğini anlaman (amnesia yaşamaman) için son birkaç sayfa Türkçe çevirisi şöyledir:
{previous_context}
--- BAĞLAM BİTTİ ---
"""

        prompt = f"""Sen, Orhan Pamuk, Sabahattin Ali ve Halide Edib Adivar gibi efsanevi Türk yazarlarının dilini ve üslubunu bilen, dünyada Man Booker Ödüllü bir Baş Edebi Çevirmensin.
Görevin: Aşağıdaki İngilizce paragrafı, Kitapduy sesli kitap uygulaması için profesyonel olarak Türkçeye çevirmektir.

Senden beklenen çeviri anlayışı:
- BİREBİR değil, ANLAMSAL ve EDEBİ çeviri. Türkçe okurun kulağında doğal, zengin ve büyüleyici gelsin.
- Cümlelerin ritmi ve nefes noktaları sesli okumaya uygun olsun.
- Karakterlerin duygu ve ruh hallerini Türkçe'nin içindeki o mükemmel karşılıklarıyla yansıt.

{context_prompt}

KESİN KURALLAR:
1. Çeviri dışında HER HANGİ bir kelime, not, açıklama veya markdown ekleme. SADECE Türkçe çeviriyi ver.
2. ZAMIR VE CİNSİYET: İngilizce'deki "he", "she", "his", "her" zamirlerinin kime ait olduğunu geçmiş bağlamdan tespit et.
3. FONETİK VE KUSURSUZ OKUMA (KRİTİK): Kısaltmaları ASLA olduğu gibi bırakma: "Dr." -> "Doktor", "%10" -> "yüzde on", "19. yüzyıl" -> "on dokuzuncu yüzyıl".
4. ŞAPKA KURALI (KRİTİK): rüzgâr, hâlâ, kâr, âşık, hikâye, dükkân kelimelerini DAIMA şapkalı yaz.
5. YASAKLI KELİMELER: "akarsu" -> "nehir", "biçimsiz" -> "şekilsiz", "abiye" -> "gece elbisesi".

Çevrilecek İngilizce Metin:
{text_chunk}"""
        
        retry_count = 0
        while retry_count < 50:
            try:
                response = self._generate(prompt, safety_off=True)
                
                if response and response.text:
                    time.sleep(3)  # Kota yanmasını engellemek için çeviriler arasına nefes molası
                    return response.text.strip()
                else:
                    raise ValueError("Çeviri API'si boş yanıt döndürdü.")
            except Exception as e:
                error_str = str(e).lower()
                if "429" in error_str or "quota" in error_str or "exhausted" in error_str or "403" in error_str:
                    print(f"Kota limitine ulaşıldı. Hesap değiştiriliyor... (Deneme: {retry_count+1})")
                    if account_manager.switch_gemini_account():
                        self.setup_gemini()
                        retry_count += 1
                        num_keys = len(account_manager.gemini_keys)
                        if num_keys > 0 and retry_count % num_keys == 0:
                            print(f"Tüm {num_keys} hesabın dakikalık kotası doldu. 60 saniye bekleniyor...")
                            time.sleep(60)
                        else:
                            time.sleep(2)
                        continue
                    else:
                        print("Tüm hesapların kotası kalıcı olarak doldu.")
                        raise e
                else:
                    if "prohibited_content" in error_str or "candidates is empty" in error_str or "blocked prompt" in error_str or "finish_reason" in error_str or "recitation" in error_str or "valid part" in error_str or "finish_reason is 8" in error_str:
                        print(f"UYARI: Çevirmen, telif hakkı filtresi (Recitation / finish_reason: 8) veya içerik engeli nedeniyle durduruldu. Bu kısım sessizce atlanıyor (<SKIP>).")
                        return "<SKIP>"
                    print(f"Çeviri sırasında bir hata oluştu: {e}")
                    time.sleep(5)
                    retry_count += 1
                    continue
        raise Exception("Çok fazla hata alındı, işlem durduruluyor.")

    def analyze_and_save_book_config(self, sample_text, config_path="book_config.json"):
        """Kitabın başından bir örnek alarak türünü analiz eder ve en uygun ses ayarlarını JSON olarak kaydeder."""
        print("[BİLGİ] Yapay Zeka Cast Direktörü kitabı analiz ediyor...")
        
        prompt = f"""You are an expert Audio Book Casting Director.
Analyze the following book excerpt and determine the best voice and tone for narrating it.
Available Voices:
- Puck (Energetic, engaging, great for comedy/children/action, Male)
- Charon (Deep, resonant, great for mystery/thriller/epic, Male)
- Kore (Calm, clear, great for drama/documentary/relaxing, Female)
- Fenrir (Rugged, gruff, great for gritty/action/horror, Male)
- Aoede (Warm, expressive, great for romance/fairy tales/poetry, Female)

Excerpt:
{sample_text[:3000]}

Respond ONLY with a valid JSON object in the exact format below, nothing else:
{{
    "voice": "[One of: Puck, Charon, Kore, Fenrir, Aoede]",
    "audio_profile": "[Brief description of the narrator's persona]",
    "style": "[e.g., Empathetic, Energetic, Mysterious, Calm, Dramatic]",
    "pace": "[e.g., Slow and steady, The Drift, Fast and engaging]",
    "accent": "[e.g., British (GB), American (US)]",
    "genre_analysis": "[1 sentence explaining why this voice was chosen]"
}}"""
        
        retry_count = 0
        while retry_count < 5:
            try:
                response = self._generate(prompt)
                result_text = response.text.strip()
                if result_text.startswith("```json"):
                    result_text = result_text[7:-3].strip()
                elif result_text.startswith("```"):
                    result_text = result_text[3:-3].strip()
                    
                import json
                config_data = json.loads(result_text)
                
                with open(config_path, "w", encoding="utf-8") as f:
                    json.dump(config_data, f, indent=4, ensure_ascii=False)
                    
                print(f"[BAŞARILI] Cast seçimi tamamlandı! Seçilen Ses: {config_data.get('voice')} ({config_data.get('genre_analysis')})")
                return True
                
            except Exception as e:
                error_str = str(e).lower()
                if "429" in error_str or "quota" in error_str:
                    account_manager.switch_gemini_account()
                    self.setup_gemini()
                time.sleep(2)
                retry_count += 1
                
        print("[UYARI] Otomatik cast seçimi başarısız oldu, varsayılan ayarlar kullanılacak.")
        return False

if __name__ == "__main__":
    # Test için
    fetcher = BookFetcher()
    # Örnek Alice Harikalar Diyarında'dan çok kısa bir bölüm
    # book = fetcher.download_gutenberg_book("11") 
    pass
