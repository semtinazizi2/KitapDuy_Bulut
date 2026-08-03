import os
import re
import difflib
from account_manager import account_manager
try:
    from google import genai
    from google.genai import types
except ImportError:
    pass

class QAChecker:
    def __init__(self, is_enabled=True):
        self.is_enabled = is_enabled
        self.client = None
        if self.is_enabled:
            self._init_gemini()
            
    def _init_gemini(self):
        key = account_manager.get_current_gemini_key()
        if key:
            self.client = genai.Client(api_key=key)
            
    def _normalize_text(self, text):
        text = text.lower().strip()
        replacements = {'â': 'a', 'î': 'i', 'û': 'u', 'é': 'e', 'ô': 'o'}
        for accented, plain in replacements.items():
            text = text.replace(accented, plain)
        text = re.sub(r'[^\w\s]', '', text)
        return text

    def check_audio_stt(self, audio_bytes, original_text):
        if not self.is_enabled or not self.client:
            return True, "QA Kapalı veya API Anahtarı Yok"
            
        print("  -> [STT DENETMENİ] Üretilen ses kelime kelime dinleniyor (Speech-to-Text)...")
        try:
            transcription_prompt = "Bu ses kaydını TAM OLARAK ve kelimesi kelimesine Türkçe yazıya dök. Hiçbir kelimeyi değiştirme, ekleme veya çıkarma. Sadece duyduğun metni ver. Başka açıklama YAZMA."
            
            response = self.client.models.generate_content(
                model="gemini-2.0-flash",
                contents=[
                    types.Part.from_bytes(data=audio_bytes, mime_type="audio/wav"),
                    transcription_prompt
                ]
            )
            
            if response and response.text:
                transcribed_text = response.text.strip()
                
                # Cümle eksikliği kontrolü
                norm_original = self._normalize_text(original_text)
                norm_transcribed = self._normalize_text(transcribed_text)
                
                # 1. Uzunluk kontrolü (Eğer metnin %80'inden azı okunduysa, büyük bir atlama vardır)
                if len(norm_transcribed) < len(norm_original) * 0.8:
                    print(f"  -> [STT HATA] Cümle yutulmuş veya yarım kalmış! (Beklenen: {len(norm_original)} karakter, Okunan: {len(norm_transcribed)} karakter)")
                    return False, "Cümle atlaması / Yarım okuma"
                    
                # 2. Benzerlik kontrolü
                matcher = difflib.SequenceMatcher(None, norm_original.split(), norm_transcribed.split())
                similarity = matcher.ratio()
                
                if similarity < 0.85:
                    print(f"  -> [STT HATA] Okunan metin orijinal senaryo ile eşleşmiyor! (Benzerlik: %{similarity*100:.1f})")
                    return False, f"Düşük benzerlik (%{similarity*100:.1f})"
                    
                print(f"  -> [STT BAŞARILI] Ses senaryo ile %{similarity*100:.1f} eşleşti. Mükemmel okuma! ✅")
                return True, "Başarılı"
                
            print("  -> [STT HATA] STT Modeli boş yanıt döndü. Bu muhtemelen sesin sessizlikten ibaret olduğu anlamına gelir!")
            return False, "Sessiz / Boş Yanıt"
        except Exception as e:
            err_str = str(e).lower()
            if "429" in err_str or "quota" in err_str or "exhausted" in err_str:
                print("  -> [STT UYARI] STT Kotası doldu! Denetleme atlanıyor (Üretime devam edilecek).")
            else:
                print(f"  -> [STT UYARI] STT işlemi başarısız oldu, atlanıyor: {e}")
            return True, "STT Hatası"
