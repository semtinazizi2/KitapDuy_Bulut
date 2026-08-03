import os
from dotenv import load_dotenv

class AccountManager:
    def __init__(self):
        load_dotenv()
        
        # Load Gemini API Keys
        keys_str = os.getenv("GEMINI_API_KEYS", "")
        self.gemini_keys = [k.strip() for k in keys_str.split(",") if k.strip()]
        self.current_gemini_index = 0
        
        # Load Google Cloud Service Accounts
        sa_str = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_LIST", "")
        self.gcp_sa_list = [sa.strip() for sa in sa_str.split(",") if sa.strip()]
        self.current_gcp_index = 0
        
        if not self.gemini_keys:
            print("UYARI: Hiç Gemini API anahtarı bulunamadı (.env dosyanızı kontrol edin).")
            
    def get_current_gemini_key(self):
        if not self.gemini_keys:
            return None
        return self.gemini_keys[self.current_gemini_index]
        
    def switch_gemini_account(self):
        if len(self.gemini_keys) <= 1:
            print("HATA: Değiştirilecek başka Gemini API anahtarı yok!")
            return False
            
        self.current_gemini_index = (self.current_gemini_index + 1) % len(self.gemini_keys)
        print(f"BİLGİ: Gemini Hesabı değiştirildi. Yeni hesap indexi: {self.current_gemini_index}")
        return True
        
    def get_current_gcp_credential_path(self):
        if not self.gcp_sa_list:
            return None
        return self.gcp_sa_list[self.current_gcp_index]
        
    def switch_gcp_account(self):
        if len(self.gcp_sa_list) <= 1:
            print("HATA: Değiştirilecek başka Google Cloud Service Account bulunamadı!")
            return False
            
        self.current_gcp_index = (self.current_gcp_index + 1) % len(self.gcp_sa_list)
        new_sa = self.gcp_sa_list[self.current_gcp_index]
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = new_sa
        print(f"BİLGİ: Google Cloud Hesabı değiştirildi. Yeni dosya: {new_sa}")
        return True

# Global instance
account_manager = AccountManager()
