import re
from datetime import datetime, timedelta, timezone

from jose import jwt
from passlib.context import CryptContext

from app.config import get_settings
from app.core.prompts import INJECTION_PATTERNS

settings = get_settings()
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_RE = re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
_CC_RE = re.compile(r"\b(?:\d[ -]*?){13,16}\b")
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")


def mask_pii(text: str) -> str:
    """Masks common PII patterns before logging/storing analytics. Does NOT alter what's
    sent to the LLM for answering (the user's own message needs to reach the model),
    only what gets persisted to logs/analytics tables."""
    text = _EMAIL_RE.sub("[EMAIL_REDACTED]", text)
    text = _SSN_RE.sub("[SSN_REDACTED]", text)
    text = _CC_RE.sub("[CARD_REDACTED]", text)
    text = _PHONE_RE.sub("[PHONE_REDACTED]", text)
    return text


def detect_prompt_injection(text: str) -> bool:
    lowered = text.lower()
    return any(pattern in lowered for pattern in INJECTION_PATTERNS)


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return _pwd_context.verify(password, hashed)


def create_access_token(subject: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": subject, "role": role, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
