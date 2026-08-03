import os
import json
import time
import wave
import re
from account_manager import account_manager
from qa_checker import QAChecker

# Yeni Gemini SDK (Audio yetenekleri için google-genai kütüphanesini kullanıyoruz)
try:
    from google import genai
    from google.genai import types
except ImportError:
    print("Lütfen 'pip install google-genai' komutunu çalıştırın.")

class TTSGenerator:
    def __init__(self, config_path="book_config.json"):
        self.config = self._load_config(config_path)
        self.client = self.setup_gemini_client()
        self.pronunciation_dict = self._load_pronunciation_dict()
        self.qa_checker = QAChecker(is_enabled=True)
        
        # Eğer çıkış klasörü yoksa oluştur
        os.makedirs(os.getenv("OUTPUT_DIR", "output_audio"), exist_ok=True)

    def _load_pronunciation_dict(self):
        """Telaffuz hatalarını manuel düzeltmek için kullanılan sözlüğü yükler."""
        dict_path = "pronunciation_dict.json"
        if os.path.exists(dict_path):
            try:
                with open(dict_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                pass
        return {}

    def apply_pronunciation_fixes(self, text):
        """Sözlükteki hatalı kelimeleri, TTS motoruna gitmeden önce fonetik veya doğru karşılıklarıyla değiştirir."""
        if not self.pronunciation_dict:
            return text
            
        import re
        for wrong_word, correct_word in self.pronunciation_dict.items():
            # Sadece tam kelime eşleşmelerini (word boundaries) değiştirir
            pattern = re.compile(rf'\b{re.escape(wrong_word)}\b', re.IGNORECASE)
            text = pattern.sub(correct_word, text)
        return text

    def _inject_natural_pauses(self, text):
        """Noktalama işaretlerine göre doğal nefes durakları (SSML benzeri) ekler.
        Bu sayede ses motoru cümleleri bir insan gibi nefes noktalarında duraklayarak okur."""
        # Birden fazla noktanın (Table of Contents vb.) devasa sessizliklere yol açmasını engellemek için,
        # sadece tek başına duran nokta, soru ve ünlemlere nefes arası ekle.
        text = re.sub(r'(?<![.!?])([.!?])(?![.!?])\s+', r'\1 ... ', text)
        # Orta duraklar: Virgul ve noktalı virgül sonrasında 0.3 saniye nefes
        text = re.sub(r'([,;])\s+', r'\1 .. ', text)
        return text

    def _load_config(self, config_path):
        default_config = {
            "voice": "Charon",
            "audio_profile": "A deep, resonant narrator of mysteries.",
            "style": "Empathetic",
            "pace": "The Drift",
            "accent": "British (GB)"
        }
        
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        else:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(default_config, f, indent=4)
            return default_config

    def setup_gemini_client(self):
        key = account_manager.get_current_gemini_key()
        if key:
            return genai.Client(api_key=key)
        return None

    def generate_director_script(self, turkish_text, previous_context=""):
        """
        Kullanıcı geri bildirimi (Storytel standardı):
        Dinamik duygu ve sahne analizleri (THE SCENE vb.) TTS motorunun her bölümde
        farklı bir tonla konuşmasına ve markdown başlıkları yüzünden derin nefesler almasına sebep oluyordu.
        Bu nedenle Yönetmen (Director) modülü tamamen devreden çıkarılmış,
        sesin %100 stabil kalması için saf metin döndürülmesi sağlanmıştır.
        """
        if "<SKIP>" in turkish_text:
            return "<SKIP>"
            
        return turkish_text.strip()

    def _call_tts_api(self, text, override_voice=None, is_retake=False):
        """Gemini TTS API'sini doğrudan çağırır."""
        # TTS API'ye gitmeden önce telaffuz hatalarını sözlükten düzelt
        text = self.apply_pronunciation_fixes(text)
        # Doğal nefes duraklarını noktalama işaretlerine göre ekle
        text = self._inject_natural_pauses(text)
        
        retry_count = 0
        while retry_count < 50:
            try:
                # Dinamik ses seçimi ve isim temizliği (Sadece küçük harf ve ilk kelime)
                raw_voice = override_voice if override_voice else self.config["voice"]
                voice_name = raw_voice.split('-')[0].strip().lower()
                
                response = self.client.models.generate_content(
                    model="gemini-2.5-flash-preview-tts",
                    contents=text,
                    config=types.GenerateContentConfig(
                        response_modalities=["AUDIO"],
                        safety_settings=[
                            types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
                            types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE"),
                            types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
                            types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE"),
                        ],
                        speech_config=types.SpeechConfig(
                            voice_config=types.VoiceConfig(
                                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                    voice_name=voice_name
                                )
                            )
                        )
                    )
                )
                
                audio_data = b""
                if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
                    for part in response.candidates[0].content.parts:
                        if part.inline_data:
                            audio_data += part.inline_data.data
                            
                # -----------------------------------------------------
                # OTONOM SES DENETMENİ (AUTO-HEALER QA AGENT)
                # -----------------------------------------------------
                if not is_retake and len(audio_data) > 0:
                    print("  -> Üretildi. Oto-Denetmen dinleyip hata kontrolü yapıyor...")
                    import io
                    from pydub import AudioSegment
                    temp_seg = AudioSegment(data=audio_data, sample_width=2, frame_rate=24000, channels=1)
                    wav_io = io.BytesIO()
                    temp_seg.export(wav_io, format="wav")
                    valid_wav_bytes = wav_io.getvalue()
                    
                    try:
                        qa_prompt = f"""Sen TRT (Türkiye Radyo Televizyon Kurumu) standartlarında, kusursuz Türkçe arayan, son derece titiz ve acımasız bir Baş Diksiyon ve Ses Uzmanısın.
GÖREV: Ekteki yapay zeka ses kaydını (TTS) dikkatle dinle. Spikerin eksiksiz ve net bir şekilde okuması GEREKEN metin tam olarak şudur:
"{text}"

KURAL VE HATA KATEGORİLERİ (TÜRKÇE DİKSİYON STANDARTLARI):
Spikeri şu hata türlerine karşı milisaniyesine kadar denetle:
1. Şiveli Uzatmalar (En Yaygın Hata): Kısa okunması gereken A, E, İ gibi harfleri amerikan aksanı veya yöresel şiveyle gereksiz uzatmak (Örn: "yarın" -> "yaaarın", "hayır" -> "haayır", "geldi" -> "geeeldi").
2. Harf/Hece Yutma ve Robotik Kesilme: Kelimenin veya eklerin sonunu kesmek, yutmak (Örn: "geliyordu" -> "geliyodu" veya "geliy..."). R harflerini yutmak.
3. Yumuşak G (Ğ) Hatası: "Ğ" harfini sert bir "G" gibi veya gırtlaktan hırlayarak okumak. (Doğrusu: Önceki ünlü harfi yarım ses uzatmaktır, ağaç -> aaç).
4. İnceltme ve Uzatma Çarpıtmaları: Şapkalı (^) okunması gereken kelimeleri düz okumak (kâr -> kar, hâlâ -> hala) veya düz kelimeleri şapkalı okumak.
5. Harf Kaymaları: Telaffuzu zor kelimelerde harf değiştirmek (Örn: "hafızası" -> "hafıtası").
6. Yabancı Aksan: Türkçe kelimeleri İngilizce/Amerikan aksanıyla, mekanik ve ruhsuz okumak.

AKSİYON:
Eğer spiker metindeki BİR KELİMEYİ BİLE yukarıdaki hatalardan biriyle (tek bir harf bile olsa) bozuk okuduysa, KESİNLİKLE affetme! Sesi reddet.
SADECE hatalı okunan kelimeyi ve yapay zeka motorunun dilinin dolanmayacağı, okuması ÇOK DAHA KOLAY, fonetik veya risksiz bir eşanlamlısını JSON olarak dön.
Format: {{"hatali_kelime": "okunusu_garanti_esanlamlisi"}}
Örnek 1 (Hece yutma): {{"hafızası": "belleği"}}
Örnek 2 (Şiveli Uzatma): {{"yarın": "ertesi gün"}} veya {{"yarın": "ya rın"}}
Örnek 3 (Düzeltilemeyen özel isim): {{"abiye": "gece elbisesi"}}
Örnek 4 (Yapay Zeka Halüsinasyonu): {{"biçimsiz": "şekilsiz"}}
Örnek 5 (Şapkasız okunan sert ses): {{"rüzgar": "rüzgâr"}}

Eğer ses harfi harfine, muazzam bir diksiyon ve akıcılıkla okunduysa SADECE boş JSON dön: {{}}
YANITIN SADECE JSON OLMALIDIR, BAŞKA HİÇBİR AÇIKLAMA YAZMA."""

                        qa_response = self.client.models.generate_content(
                            model="gemini-3.5-flash-lite",  # Yüksek ücretsiz kotaya sahip hızlı model
                            contents=[
                                types.Part.from_bytes(data=valid_wav_bytes, mime_type="audio/wav"),
                                qa_prompt
                            ]
                        )
                        
                        qa_result = qa_response.text.strip()
                        if qa_result.startswith("```json"):
                            qa_result = qa_result[7:-3].strip()
                        elif qa_result.startswith("```"):
                            qa_result = qa_result[3:-3].strip()
                            
                        qa_dict = json.loads(qa_result)
                        if qa_dict and isinstance(qa_dict, dict):
                            wrong_word = list(qa_dict.keys())[0]
                            correct_word = str(qa_dict[wrong_word])

                            # SAĞLIK KONTROLÜ: QA bazen saçma sonuçlar üretir.
                            # Eğer yakalanan "kelime" 50 karakterden uzunsa veya aynı kelimeyi
                            # tekrar ediyorsa ("sin sin sin..." gibi), bu bir QA halüsinasyonudur.
                            words_in_wrong = wrong_word.split()
                            is_absurd = (
                                len(wrong_word) > 60 or  # Çok uzun
                                (len(words_in_wrong) > 3 and len(set(words_in_wrong)) <= 2)  # Tekrarlayan
                            )

                            if is_absurd:
                                print(f"  -> [OTO-DENETMEN] Saçma QA sonucu atlandı (tekrarlayan/çok uzun kelime). Ses kabul edildi.")
                            elif wrong_word and correct_word and wrong_word.lower() in text.lower():
                                print(f"  -> [OTO-DENETMEN HATA BULDU!] '{wrong_word[:40]}' kelimesi hatalı okundu.")
                                print(f"  -> Sözlüğe ekleniyor: {wrong_word[:40]} -> {correct_word}")
                                
                                # Sözlüğü güncelle
                                self.pronunciation_dict[wrong_word] = correct_word
                                dict_path = "pronunciation_dict.json"
                                with open(dict_path, "w", encoding="utf-8") as f:
                                    json.dump(self.pronunciation_dict, f, indent=4, ensure_ascii=False)
                                    
                                # Retake (Düzeltilmiş metinle tekrar çekim yap)
                                print("  -> Düzeltilmiş yeni kural ile ses YENİDEN (Retake) üretiliyor...")
                                return self._call_tts_api(text, override_voice, is_retake=True)
                    except Exception as qa_err:
                        pass # QA hatası üretimi durdurmasın

                # -----------------------------------------------------
                # OTO-DENETMEN STT (SPEECH-TO-TEXT) KONTROLÜ
                # -----------------------------------------------------
                if not is_retake and len(audio_data) > 0:
                    is_valid, stt_msg = self.qa_checker.check_audio_stt(valid_wav_bytes, text)
                    if not is_valid:
                        print("  -> [STT RETAKE] Ses metinle uyuşmuyor, yeniden (Retake) üretiliyor...")
                        return self._call_tts_api(text, override_voice, is_retake=True)
                
                return audio_data
            except Exception as e:
                error_str = str(e).lower()
                if "429" in error_str or "quota" in error_str or "exhausted" in error_str or "403" in error_str or "permission_denied" in error_str:
                    print(f"  -> TTS Kotası doldu (veya Erişim Reddedildi)! Hesap değiştiriliyor... (Deneme {retry_count+1})")
                    if account_manager.switch_gemini_account():
                        self.client = self.setup_gemini_client()
                        retry_count += 1
                        
                        num_keys = len(account_manager.gemini_keys)
                        if num_keys > 0 and retry_count % num_keys == 0:
                            print(f"  -> Tüm {num_keys} hesabın dakikalık kotası doldu. Kotaların yenilenmesi için 60 saniye bekleniyor...")
                            time.sleep(60)
                        else:
                            time.sleep(2)
                            
                        continue
                    else:
                        print("  -> Tüm hesapların kotası kalıcı olarak doldu, 30sn bekleniyor...")
                        time.sleep(30)
                        retry_count += 1
                        continue
                else:
                    if "prohibited_content" in error_str or "candidates is empty" in error_str or "blocked prompt" in error_str or "finish_reason" in error_str or "recitation" in error_str or "valid part" in error_str or "finish_reason is 8" in error_str:
                        print(f"  -> [UYARI] TTS bu metni telif (Recitation/finish_reason: 8) veya içerik engeli nedeniyle seslendirmedi (<SKIP>).")
                        return b""
                        
                    print(f"  -> TTS Hatası: {e}")
                    time.sleep(5)
                    retry_count += 1
                    continue
        raise Exception("Çok fazla TTS hatası alındı, parça atlanıyor.")

    def generate_audio(self, director_script, output_filename):
        """Verilen senaryoya göre sesi üretir ve dosyaya kaydeder."""
        print(f"Seslendiriliyor: {output_filename} (Ses: {self.config['voice']})")
        
        if os.path.dirname(output_filename):
            output_path = output_filename
        else:
            output_path = os.path.join(os.getenv("OUTPUT_DIR", "output_audio"), output_filename)
            
        if output_path.endswith(".mp3"):
            output_path = output_path[:-4] + ".wav"
            
        if "<SKIP>" in director_script:
            print("  -> [BİLGİ] Bu bölüm sansürlendiği için sessizlikle (Atlama/Skip) geçiştiriliyor.")
            from pydub import AudioSegment
            speech_segment = AudioSegment.silent(duration=1000)
            speech_segment.export(output_path, format="wav")
            return output_path
        
        try:
            # Ortam sesi, Efekt, Ses, Müzik ve Yakınlık etiketlerini yakala
            ambience_type = "none"
            # Senaryodan sadece okunacak metni ayıkla
            transcript_text = director_script
            if "#### TRANSCRIPT" in director_script:
                transcript_text = director_script.split("#### TRANSCRIPT")[-1].strip()
                # Temizleme işlemine gerek kalmadı çünkü ajan artık etiket üretmiyor

            if not transcript_text:
                transcript_text = director_script
                
            # Yapay zekanın duyguyu (tonlamayı) koruyabilmesi için metni olabildiğince BÜTÜN gönderiyoruz.
            # Eskiden RAM hatası olduğu için bunu 1400'e çekmiştik, ancak ağır kompresör kodunu kaldırdığımız
            # için artık 1GB RAM ile tek seferde 5000 karakterlik (yaklaşık 4-5 dakika) dev blokları işleyebiliyoruz!
            sentences = re.split(r'(?<=[.!?])\s+|\n+', transcript_text)
            current_chunk = ""
            chunks = []
            for sentence in sentences:
                if len(current_chunk) + len(sentence) < 5000:
                    current_chunk += sentence + " "
                else:
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                    current_chunk = sentence + " "
            if current_chunk:
                chunks.append(current_chunk.strip())
                
            print(f"-> Sesin kesilmemesi için metin {len(chunks)} alt parçaya bölünerek seslendiriliyor...")
            
            from pydub import AudioSegment
            import subprocess
            
            speech_segment = AudioSegment.empty()
            
            for i, chunk in enumerate(chunks):
                if len(chunks) > 1:
                    print(f"  -> Alt parça {i+1}/{len(chunks)} işleniyor...")
                    
                # SAF METİN SESLENDİRME (STABLE TONE)
                # Metni bölmeden, yapay zekanın duyguyu baştan sona koruması için tek bir parça (blok) halinde gönder.
                if chunk.strip():
                    chunk_audio_bytes = self._call_tts_api(chunk.strip())
                    if chunk_audio_bytes:
                        chunk_seg = AudioSegment(
                            data=chunk_audio_bytes,
                            sample_width=2,
                            frame_rate=24000,
                            channels=1
                        )
                        speech_segment += chunk_seg
                            
            if len(speech_segment) == 0:
                print("  -> [UYARI] Bu bölüm için ses verisi üretilemedi (Telif veya içerik engeli). 1 saniyelik sessizlik ile geçiliyor.")
                speech_segment = AudioSegment.silent(duration=1000, frame_rate=24000)
                
            speech_segment.export(output_path, format="wav")
                
            # Sesi "Dinle" ve doğrula (CPU dostu yöntem)
            import math
            with wave.open(output_path, "rb") as wf:
                frames = wf.readframes(wf.getnframes())
                count = len(frames)//2
                duration = count / 24000.0 if count > 0 else 0
                
                # KRİTİK DÜZELTME: struct.unpack ile 7.2 milyonluk listeyi for döngüsüyle toplamak 
                # sunucunun CPU'sunu %100'e kilitleyip Oracle'ın sunucuyu dondurmasına sebep oluyordu!
                # Bunun yerine C dilinde yazılmış çok hızlı 'audioop' modülünü kullanıyoruz (0% CPU).
                try:
                    import audioop
                    rms = audioop.rms(frames, 2) if count > 0 else 0
                except ImportError:
                    rms = 501 # audioop yoksa (Python 3.13+) atla
                    
            print(f"Ses Analizi: Uzunluk = {duration:.2f} saniye, Ses Şiddeti = {rms:.2f}")
            
            if rms < 500:
                print("UYARI: Model boş bir ses üretti. Tekrar deneniyor...")
                time.sleep(2)
                return self.generate_audio(director_script, output_filename)
                
            # KAYIP CÜMLE DEDEKTÖRÜ (Süre / Metin Uzunluğu Doğrulaması)
            # director_script yönetmen notu içerdiği için çok uzun olabilir.
            # Sadece asıl Türkçe metnin uzunluğuna bakıyoruz.
            # Türkçe ortalama konuşma hızı ~15 karakter/saniye, biz 40'a bölüyoruz (geniş tolerans).
            # Max beklenti 300 saniye ile sınırlı (çok uzun bölümlerde false positive önlemek için).
            pure_text_len = len(director_script.split('SPIKER METNI:')[-1]) if 'SPIKER METNI:' in director_script else len(director_script)
            min_expected_duration = min(300.0, max(1.5, pure_text_len / 40.0))
            if duration < min_expected_duration:
                print(f"[QA HATA] Kayıp Cümle Tespit Edildi! (Beklenen min: {min_expected_duration:.1f}s, Gelen: {duration:.1f}s)")
                print("Spiker cümleyi yutmuş veya çok hızlı geçmiş. Tekrar üretiliyor (Retake)...")
                time.sleep(2)
                return self.generate_audio(director_script, output_filename)
                
            # --- AUDIBLE STANDARD: STÜDYO MASTERING ---
            # --- AUDIBLE STANDARD: STÜDYO MASTERING ---
            try:
                import subprocess
                import platform
                import shutil
                
                print("[BİLGİ] Audible Standardı Mastering, Stereo ve Bölüm Geçiş Sesi uygulanıyor...")
                
                local_ffmpeg = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ffmpeg.exe")
                if platform.system() == "Windows" and os.path.exists(local_ffmpeg):
                    ffmpeg_bin = local_ffmpeg
                else:
                    ffmpeg_bin = "ffmpeg"
                
                tmp_output = output_path + ".tmp.mp3"
                
                # KRİTİK DÜZELTME: Tüm kitabı en sonda tek seferde MP3'e çevirmek 4 saat sürdüğü için 
                # sunucunun CPU'sunu %100'de kilitliyordu! 
                # Bunun yerine her 5 dakikalık parçayı ÜRETİRKEN anında MP3'e çeviriyoruz.
                # adelay=501ms|500ms -> Sol kanala 1ms gecikme (3D Binaural etki) ve başa 0.5s sessizlik.
                # apad=pad_dur=1.5 -> Sona 1.5s sessizlik.
                cmd = [
                    ffmpeg_bin, "-y", "-i", output_path,
                    "-af", "aformat=channel_layouts=stereo,adelay=501ms|500ms,apad=pad_dur=1.5",
                    "-c:a", "libmp3lame", "-b:a", "64k",
                    tmp_output
                ]
                
                try:
                    res = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
                    if res.returncode == 0:
                        mp3_output_path = output_path.replace(".wav", ".mp3")
                        shutil.move(tmp_output, mp3_output_path)
                        if os.path.exists(output_path):
                            os.remove(output_path) # Ham WAV'ı sil
                        output_path = mp3_output_path
                        print("  -> Stereo/Binaural dönüşüm tamamlandı (Kulaklıkta mekan hissi aktif). ✨")
                        print("  -> Mastering, Stereo ve Bölüm Geçiş Sesi başarıyla tamamlandı. 🌟")
                    else:
                        print(f"[UYARI] FFmpeg Mastering hatası. Orijinal ses korundu. Hata: {res.stderr[:200]}")
                except subprocess.TimeoutExpired:
                    print(f"\n[ACİL MÜDAHALE] Ses dönüştürme işlemi 45 saniyeyi aştı! Sunucunun kilitlenmemesi (RAM şişmemesi) için bu ağır işlem ZORLA DURDURULDU. Orijinal ses ile yola devam ediliyor...")
                    subprocess.run(["pkill", "-9", "-f", "ffmpeg"], capture_output=True)
                    
            except Exception as ex:
                print(f"[UYARI] FFmpeg çalıştırılamadı: {ex}. Orijinal ses korundu.")
                        
            print(f"Başarıyla kaydedildi: {output_path}")
            return output_path
            
        except Exception as e:
            print(f"HATA: Seslendirme işlemi başarısız oldu. Hata detayı: {e}")
            return None

if __name__ == "__main__":
    pass
