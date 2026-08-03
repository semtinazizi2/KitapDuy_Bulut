import os
import json
from firebase_admin import credentials

def get_firebase_cred():
    creds_str = os.environ.get("FIREBASE_CREDS")
    if creds_str:
        try:
            creds = json.loads(creds_str)
            if "private_key" in creds:
                # Eger bash/github string'i bozduysa \n harfleri literal '\\n' haline gelebiliyor.
                creds["private_key"] = creds["private_key"].replace('\\n', '\n')
                
                # Eger \n hic yoksa ve tek satirda boslukluysa
                if '\n' not in creds["private_key"]:
                    pk = creds["private_key"]
                    pk = pk.replace("-----BEGIN PRIVATE KEY-----", "-----BEGIN PRIVATE KEY-----\n")
                    pk = pk.replace("-----END PRIVATE KEY-----", "\n-----END PRIVATE KEY-----\n")
                    pk = pk.replace(" ", "\n")
                    pk = pk.replace("BEGIN\nPRIVATE\nKEY", "BEGIN PRIVATE KEY")
                    pk = pk.replace("END\nPRIVATE\nKEY", "END PRIVATE KEY")
                    creds["private_key"] = pk
            return credentials.Certificate(creds)
        except Exception as e:
            print(f"[UYARI] ENV icinden Firebase JSON parse edilemedi: {e}")
            pass
            
    # Fallback to file
    return credentials.Certificate("serviceAccountKey.json")
