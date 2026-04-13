import datetime as dt
from jose import jwt, JWTError
from dotenv import load_dotenv
import os

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = 30
INACTIVITY_MINUTES = 30

def create_token(username: str) -> str:
    expire = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": username, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=ALGORITHM)
        return payload.get("sub")
    except JWTError:
        return None
    
def is_token_expired(token: str) -> bool:
    payload = decode_token(token)
    if not payload:
        return True
    return dt.datetime.now(dt.timezone.utc) > dt.datetime.fromtimestamp(payload["exp"])