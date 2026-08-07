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

    def _refresh_client(self):
        """Hesap döndürüldükten sonra client'ı yenile."""
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

        # STT için model rotasyonu: Her ikisi de 500 RPD/gün!
        STT_MODELS = [
            "gemini-3.1-flash-lite",  # Birincil: 500 RPD/gün ✅
            "gemini-3.5-flash-lite",  # Yedek:    500 RPD/gün ✅
        ]

        print("  -> [STT DENETMENİ] Üretilen ses kelime kelime dinleniyor (Speech-to-Text)...")
        transcription_prompt = "Bu ses kaydını TAM OLARAK ve kelimesi kelimesine Türkçe yazıya dök. Hiçbir kelimeyi değiştirme, ekleme veya çıkarma. Sadece duyduğun metni ver. Başka açıklama YAZMA."

        num_keys = len(account_manager.gemini_keys) if account_manager.gemini_keys else 1
        # Tüm API anahtarları × tüm modeller kadar deneme hakkı
        # Sıra: Model1/Hesap0 → Model2/Hesap0 → Model1/Hesap1 → Model2/Hesap1 → ...
        for attempt in range(num_keys * len(STT_MODELS)):
            model_name = STT_MODELS[attempt % len(STT_MODELS)]
            try:
                response = self.client.models.generate_content(
                    model=model_name,
                    contents=[
                        types.Part.from_bytes(data=audio_bytes, mime_type="audio/wav"),
                        transcription_prompt
                    ]
                )

                if response and response.text:
                    transcribed_text = response.text.strip()

                    norm_original = self._normalize_text(original_text)
                    norm_transcribed = self._normalize_text(transcribed_text)

                    if len(norm_transcribed) < len(norm_original) * 0.8:
                        print(f"  -> [STT HATA] Cümle yutulmuş! (Beklenen: {len(norm_original)} karakter, Okunan: {len(norm_transcribed)} karakter)")
                        return False, "Cümle atlaması / Yarım okuma"

                    matcher = difflib.SequenceMatcher(None, norm_original.split(), norm_transcribed.split())
                    similarity = matcher.ratio()

                    if similarity < 0.85:
                        print(f"  -> [STT HATA] Okunan metin orijinalle eşleşmiyor! (Benzerlik: %{similarity*100:.1f})")
                        return False, f"Düşük benzerlik (%{similarity*100:.1f})"

                    print(f"  -> [STT BAŞARILI] Ses senaryo ile %{similarity*100:.1f} eşleşti. ✅")
                    return True, "Başarılı"

                print(f"  -> [STT HATA] {model_name} boş yanıt döndü, diğer modele geçiliyor...")
                continue

            except Exception as e:
                err_str = str(e).lower()
                if "429" in err_str or "quota" in err_str or "exhausted" in err_str or "403" in err_str:
                    print(f"  -> [STT UYARI] {model_name} kotası doldu! (Deneme {attempt+1}/{num_keys * len(STT_MODELS)})")
                    # Her iki model de bu hesapta bittiyse → hesabı değiştir
                    if (attempt + 1) % len(STT_MODELS) == 0:
                        if account_manager.switch_gemini_account():
                            print(f"  -> [STT] Hesap değiştirildi. Yeni index: {account_manager.current_gemini_index}")
                            self._refresh_client()
                    continue
                else:
                    print(f"  -> [STT UYARI] {model_name} ile STT başarısız: {e}")
                    continue

        print("  -> [STT UYARI] Tüm hesaplar ve modeller tükendi. Denetleme atlanıyor.")
        return True, "STT Tüm Hesaplar/Modeller Tükendi"
