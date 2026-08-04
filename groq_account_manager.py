import os
from dotenv import load_dotenv

class GroqAccountManager:
    def __init__(self):
        load_dotenv()
        
        # Load Groq API Keys
        keys_str = os.getenv("GROQ_API_KEYS", "")
        self.groq_keys = [k.strip() for k in keys_str.split(",") if k.strip()]
        self.current_groq_index = 0
        
        if not self.groq_keys:
            print("UYARI: Hiç Groq API anahtarı bulunamadı (.env dosyanızı kontrol edin).")
            
    def get_current_groq_key(self):
        if not self.groq_keys:
            return None
        return self.groq_keys[self.current_groq_index]
        
    def switch_groq_account(self):
        if len(self.groq_keys) <= 1:
            print("HATA: Değiştirilecek başka Groq API anahtarı yok!")
            return False
            
        self.current_groq_index = (self.current_groq_index + 1) % len(self.groq_keys)
        print(f"BİLGİ: Groq Hesabı değiştirildi. Yeni hesap indexi: {self.current_groq_index}")
        return True

groq_account_manager = GroqAccountManager()
