"""
Security utilities for password hashing and verification.
"""
from passlib.context import CryptContext
from jose import jwt
from datetime import datetime, timedelta
from typing import Optional
import secrets

from config import settings

# Use bcrypt for password hashing (consistent with SecurityUtils)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
PASSWORD_MAX_BYTES = 72  # bcrypt limitation

def _truncate_password(password: str) -> str:
    """Truncate password to max bytes (72 for bcrypt)"""
    password_bytes = password.encode('utf-8')
    if len(password_bytes) > PASSWORD_MAX_BYTES:
        # Truncate and decode, handling potential partial characters
        truncated = password_bytes[:PASSWORD_MAX_BYTES]
        # Try to decode, removing incomplete UTF-8 sequences from the end
        while len(truncated) > 0:
            try:
                return truncated.decode('utf-8')
            except UnicodeDecodeError:
                truncated = truncated[:-1]
        return ""
    return password

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain password against a hashed password.
    Automatically truncates password to handle bcrypt 72-byte limit.
    """
    truncated_password = _truncate_password(plain_password)
    return pwd_context.verify(truncated_password, hashed_password)

def get_password_hash(password: str) -> str:
    """
    Hash a password for storage.
    Automatically truncates password to 72 bytes due to bcrypt limitation.
    """
    try:
        truncated_password = _truncate_password(password)
        return pwd_context.hash(truncated_password)
    except ValueError as e:
        # If bcrypt still complains, force truncate
        if "72" in str(e) or "bytes" in str(e):
            truncated_password = password[:72]
            return pwd_context.hash(truncated_password)
        raise

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT refresh token.
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def generate_api_key() -> str:
    """
    Generate a random API key.
    """
    return secrets.token_urlsafe(32)

def generate_api_secret() -> str:
    """
    Generate a random API secret.
    """
    return secrets.token_urlsafe(64)

def verify_token(token: str) -> dict:
    """
    Verify and decode a JWT token.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except jwt.JWTError:
        return None

def generate_password_reset_token(email: str) -> str:
    """
    Generate a password reset token.
    """
    expires = datetime.utcnow() + timedelta(hours=settings.RESET_TOKEN_EXPIRE_HOURS)
    to_encode = {"sub": email, "exp": expires, "type": "reset"}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def verify_password_reset_token(token: str) -> Optional[str]:
    """
    Verify a password reset token and return email if valid.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "reset":
            return None
        email: str = payload.get("sub")
        if email is None:
            return None
        return email
    except jwt.JWTError:
        return None

def generate_email_verification_token(email: str) -> str:
    """
    Generate an email verification token.
    """
    expires = datetime.utcnow() + timedelta(hours=24)
    to_encode = {"sub": email, "exp": expires, "type": "verify"}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def verify_email_token(token: str) -> Optional[str]:
    """
    Verify an email verification token and return email if valid.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "verify":
            return None
        email: str = payload.get("sub")
        if email is None:
            return None
        return email
    except jwt.JWTError:
        return None

def hash_api_secret(secret: str) -> str:
    """
    Hash an API secret for storage.
    """
    return get_password_hash(secret)

def generate_2fa_secret() -> str:
    """
    Generate a random secret for 2FA.
    """
    return secrets.token_hex(16)

def generate_2fa_recovery_codes(count: int = 8) -> list:
    """
    Generate recovery codes for 2FA.
    """
    return [secrets.token_hex(5).upper() for _ in range(count)]

def validate_2fa_code(secret: str, code: str) -> bool:
    """
    Validate a 2FA TOTP code.
    """
    try:
        import pyotp
        totp = pyotp.TOTP(secret)
        return totp.verify(code)
    except ImportError:
        # Fallback if pyotp is not installed
        return False
    except Exception:
        return False

def generate_session_token() -> str:
    """
    Generate a random session token.
    """
    return secrets.token_urlsafe(64)

def generate_csrf_token() -> str:
    """
    Generate a random CSRF token.
    """
    return secrets.token_urlsafe(32)

def validate_csrf_token(token: str, expected_token: str) -> bool:
    """
    Validate a CSRF token.
    """
    return secrets.compare_digest(token, expected_token)

def generate_random_password(length: int = 12) -> str:
    """
    Generate a random password.
    """
    import string
    import random
    
    characters = string.ascii_letters + string.digits + string.punctuation
    password = ''.join(random.choice(characters) for _ in range(length))
    return password

def password_strength_check(password: str) -> dict:
    """
    Check password strength.
    Returns a dict with score and feedback.
    """
    score = 0
    feedback = []
    
    # Length check
    if len(password) >= 12:
        score += 2
    elif len(password) >= 8:
        score += 1
    else:
        feedback.append("Password should be at least 8 characters long")
    
    # Lowercase check
    if any(c.islower() for c in password):
        score += 1
    else:
        feedback.append("Password should contain at least one lowercase letter")
    
    # Uppercase check
    if any(c.isupper() for c in password):
        score += 1
    else:
        feedback.append("Password should contain at least one uppercase letter")
    
    # Digit check
    if any(c.isdigit() for c in password):
        score += 1
    else:
        feedback.append("Password should contain at least one digit")
    
    # Special character check
    if any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
        score += 1
    else:
        feedback.append("Password should contain at least one special character")
    
    # Common password check (simplified)
    common_passwords = ["password", "123456", "qwerty", "admin", "letmein"]
    if password.lower() in common_passwords:
        score = 0
        feedback.append("Password is too common")
    
    # Determine strength level
    if score >= 5:
        strength = "strong"
    elif score >= 3:
        strength = "medium"
    else:
        strength = "weak"
    
    return {
        "score": score,
        "strength": strength,
        "feedback": feedback,
        "max_score": 6
    }