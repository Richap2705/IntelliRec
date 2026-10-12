import hashlib,hmac,secrets,re
from datetime import datetime,timedelta,timezone
import jwt
from .config import SECRET_KEY,TOKEN_MINUTES
PASSWORD_RE=re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z\d]).{8,128}$")
def password_valid(p): return bool(PASSWORD_RE.match(p))
def password_rules(p): return {"min_length":len(p)>=8,"uppercase":bool(re.search(r"[A-Z]",p)),"lowercase":bool(re.search(r"[a-z]",p)),"number":bool(re.search(r"\d",p)),"special":bool(re.search(r"[^A-Za-z\d]",p))}
def _hash(password,salt): return hashlib.pbkdf2_hmac("sha256",password.encode(),salt.encode(),210_000).hex()
def hash_password(password):
    salt=secrets.token_hex(16); return f"{salt}${_hash(password,salt)}"
def verify_password(password,stored):
    try: salt,digest=stored.split("$"); return hmac.compare_digest(_hash(password,salt),digest)
    except ValueError: return False
def create_token(user_id,role):
    exp=datetime.now(timezone.utc)+timedelta(minutes=TOKEN_MINUTES)
    return jwt.encode({"sub":str(user_id),"role":role,"exp":exp},SECRET_KEY,algorithm="HS256")
def decode_token(token):
    try: return jwt.decode(token,SECRET_KEY,algorithms=["HS256"])
    except jwt.PyJWTError: return None
