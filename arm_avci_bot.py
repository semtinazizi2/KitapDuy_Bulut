import oci
import time
import datetime
from oci.core.models import LaunchInstanceDetails, CreateVnicDetails

# === KULLANICI AYARLARI ===
CONFIG = {
    "user": "ocid1.user.oc1..aaaaaaaa3q7ifzw24osugvsjs5ssvnh2sgziucoudlj63y36nz4gswiwqxmq",
    "fingerprint": "16:66:5a:e0:d8:8c:da:1b:99:f8:7d:cd:91:aa:9c:4d",
    "tenancy": "ocid1.tenancy.oc1..aaaaaaaactozoucj7wraq7frkqwtipzwermnhyvzrndvcxrgjayhtqnkmpzq",
    "region": "eu-frankfurt-1",
    "key_file": "/home/ubuntu/KitapDuy_Bulut/api_key.pem"
}

SUBNET_ID = "ocid1.subnet.oc1.eu-frankfurt-1.aaaaaaaajza53fsgoznmhjvj2rmrx6zrc3x4wo7zcsd7jzq4g5bdhsgdpqua"
IMAGE_ID = "ocid1.image.oc1.eu-frankfurt-1.aaaaaaaa6fudunmmzo6fnegjii3rwiduwzxtkpvoi25c6t5cswcdtpgt4gvq"

def main():
    print("=======================================")
    print("  ORACLE 24GB ARM AVCI BOTU BAŞLADI!")
    print("=======================================")
    
    try:
        oci.config.validate_config(CONFIG)
        compute = oci.core.ComputeClient(CONFIG)
        identity = oci.identity.IdentityClient(CONFIG)
        
        # OCI'dan gerçek AD (Veri Merkezi) isimlerini otomatik çek (Çünkü her hesabın prefix'i farklıdır)
        ads_response = identity.list_availability_domains(CONFIG["tenancy"]).data
        ads = [ad.name for ad in ads_response]
        print(f"[BİLGİ] Geçerli AD'ler bulundu: {ads}")
        
    except Exception as e:
        print(f"HATA: Başlatma başarısız.\nDetay: {e}")
        return

    instance_details = LaunchInstanceDetails(
        compartment_id=CONFIG["tenancy"],
        shape="VM.Standard.A1.Flex",
        shape_config=oci.core.models.LaunchInstanceShapeConfigDetails(
            ocpus=4,
            memory_in_gbs=24
        ),
        display_name="ARM-24GB-AVCI",
        image_id=IMAGE_ID,
        create_vnic_details=CreateVnicDetails(
            subnet_id=SUBNET_ID,
            assign_public_ip=True
        )
    )

    deneme_sayisi = 1
    current_ad_index = 0

    while True:
        simdi = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if not ads:
            print("HATA: Hiçbir Availability Domain bulunamadı.")
            break
            
        secilen_ad = ads[current_ad_index]
        instance_details.availability_domain = secilen_ad
        
        try:
            print(f"[{simdi}] Deneme {deneme_sayisi} -> 24GB ARM ({secilen_ad}) deneniyor...")
            response = compute.launch_instance(instance_details)
            print(f"\n[MÜJDE!!!] SUNUCU BAŞARIYLA OLUŞTURULDU! Panelden kontrol edebilirsiniz.")
            break
        except oci.exceptions.ServiceError as e:
            if e.status == 500 and "Out of host capacity" in e.message:
                print(f"  -> Kapasite yok. Diğer AD'ye geçiliyor...")
            elif e.status == 401:
                print(f"  -> HATA: Kimlik Doğrulanamadı (NotAuthenticated).")
                break
            elif e.status == 400 and "LimitExceeded" in e.message:
                 print(f"  -> HATA: Zaten bir 24GB sunucunuz var veya limitiniz dolmuş!")
                 break
            else:
                print(f"  -> Hata kodu: {e.status} - Mesaj: {e.message}")
        except Exception as e:
            print(f"  -> Beklenmeyen hata: {str(e)}")
            
        current_ad_index = (current_ad_index + 1) % len(ads)
        time.sleep(60)
        deneme_sayisi += 1

if __name__ == "__main__":
    main()
