import ast
from datetime import datetime, timedelta, timezone

from cryptography.fernet import Fernet, InvalidToken
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_fernet() -> Fernet:
    key = settings.credentials_key.encode()
    return Fernet(key)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return pwd_context.verify(password, hashed_password)


def create_access_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def decode_access_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        return payload.get("sub")
    except JWTError:
        return None


def encrypt_payload(payload: dict) -> str:
    return get_fernet().encrypt(repr(payload).encode()).decode()


def decrypt_payload(blob: str | None) -> dict:
    if not blob:
        return {}
    try:
        raw = get_fernet().decrypt(blob.encode()).decode()
        parsed = ast.literal_eval(raw)
        return parsed if isinstance(parsed, dict) else {}
    except (InvalidToken, SyntaxError, ValueError):
        return {}
