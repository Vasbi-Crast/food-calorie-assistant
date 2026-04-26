import datetime as dt
from jose import jwt, JWTError
from dotenv import load_dotenv
import os
from typing import Optional

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("SECRET_KEY environment variable is not set")

ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = 1440


def create_token(username: str) -> str:
    """
    Creates a JWT access token for user authentication.

    Args:
        username (str): The username to encode in the token.

    Returns:
        str: Encoded JWT token string.
    """
    expire = dt.datetime.now(dt.timezone.utc) + dt.timedelta(
        minutes=TOKEN_EXPIRE_MINUTES
    )
    return jwt.encode({"sub": username, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[str]:
    """
    Decodes and validates a JWT access token.

    Args:
        token (str): JWT token string to decode.

    Returns:
        str | None: Username from token if valid, None if invalid or expired.

    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None
    except Exception:
        return None
