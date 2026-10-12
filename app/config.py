import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./recengine.db")
SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "IntelliRec_Enterprise_Secure_Key_2026_Sha256_Auth_Secret_Key_Token",
)
TOKEN_MINUTES = int(os.getenv("TOKEN_MINUTES", "120"))
CACHE_TTL = int(os.getenv("CACHE_TTL", "60"))
N_TOPICS = int(os.getenv("N_TOPICS", "5"))
SEED_ON_START = os.getenv("SEED_ON_START", "true").lower() == "true"
CORS_ORIGINS = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "*").split(",")
    if o.strip()
]
