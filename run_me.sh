pkg install python-pydantic python-grpcio python-numpy python-pillow python-cryptography -y
export PIP_PREFER_BINARY=1
export PIP_ONLY_BINARY=grpcio,pydantic-core,pydantic,cryptography,pillow,numpy
pip install requests boto3 firebase-admin pydub google-genai python-dotenv
echo " "
echo "=========================================================="
echo "KURULUM BASARIYLA BITTI! ARTIK python main.py YAZABILIRSINIZ"
echo "=========================================================="
