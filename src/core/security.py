"""
Security & Password Authentication Module
=========================================
Project: Akıllı Servis Masası ve Sistem Uzmanı Chatbot (PRJIC20260201)
Description:
    Provides robust, SOLID-compliant password strength validation, RFC 5322
    email format validation, and irreversible salted hash password generation
    and verification using bcrypt.
"""

import re
import bcrypt
from typing import List


# ---------------------------------------------------------------------------
# Custom Security Exceptions
# ---------------------------------------------------------------------------
class SecurityValidationError(ValueError):
    """Base exception for security and authentication validation failures."""
    pass


class PasswordValidationError(SecurityValidationError):
    """Raised when a password does not satisfy complexity requirements."""
    pass


class EmailValidationError(SecurityValidationError):
    """Raised when an email address format is invalid."""
    pass


# ---------------------------------------------------------------------------
# 1. Password Strength Validation
# ---------------------------------------------------------------------------
def validate_password_strength(password: str) -> bool:
    """
    Validates that a password satisfies strict corporate security complexity rules:
      - Minimum 8 characters in length.
      - At least 1 uppercase letter (A-Z).
      - At least 1 lowercase letter (a-z).
      - At least 1 numeric digit (0-9).

    Args:
        password (str): Plaintext password to evaluate.

    Returns:
        bool: True if the password satisfies all complexity rules.

    Raises:
        PasswordValidationError: If one or more complexity criteria fail,
                                 detailing all failed criteria.
    """
    if not password or not isinstance(password, str):
        raise PasswordValidationError("Parola boş bırakılamaz ve metin tipinde olmalıdır.")

    missing_criteria: List[str] = []

    # 1. Length Check
    if len(password) < 8:
        missing_criteria.append("En az 8 karakter uzunluğunda olmalıdır.")

    # 2. Uppercase Check
    if not re.search(r"[A-Z]", password):
        missing_criteria.append("En az 1 büyük harf (A-Z) içermelidir.")

    # 3. Lowercase Check
    if not re.search(r"[a-z]", password):
        missing_criteria.append("En az 1 küçük harf (a-z) içermelidir.")

    # 4. Digit Check
    if not re.search(r"\d", password):
        missing_criteria.append("En az 1 rakam (0-9) içermelidir.")

    if missing_criteria:
        error_msg = "Parola karmaşıklık kurallarına uymuyor: " + " ".join(missing_criteria)
        raise PasswordValidationError(error_msg)

    return True


# ---------------------------------------------------------------------------
# 2. Email Format Validation
# ---------------------------------------------------------------------------
EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)+$"
)


def validate_email_format(email: str) -> bool:
    """
    Validates that an email address matches the standard RFC 5322 structure.

    Args:
        email (str): Email address string to validate.

    Returns:
        bool: True if the email format is valid.

    Raises:
        EmailValidationError: If the email format is invalid or malformed.
    """
    if not email or not isinstance(email, str):
        raise EmailValidationError("E-posta adresi boş bırakılamaz.")

    email_clean = email.strip()
    if ".." in email_clean or not EMAIL_REGEX.match(email_clean):
        raise EmailValidationError(f"Geçersiz e-posta formatı: '{email_clean}'.")

    return True


# ---------------------------------------------------------------------------
# 3. Salted Hash Password Encryption & Verification (bcrypt)
# ---------------------------------------------------------------------------
def hash_password(password: str, rounds: int = 12, validate: bool = True) -> str:
    """
    Generates a secure, irreversible, salted one-way hash for a given password using bcrypt.

    Args:
        password (str): Plaintext password to hash.
        rounds (int): Work factor cost for bcrypt key derivation (default: 12).
        validate (bool): Whether to enforce complexity validation before hashing (default: True).

    Returns:
        str: Bcrypt salted password hash (e.g. '$2b$12$...').

    Raises:
        PasswordValidationError: If validate=True and the password is weak.
    """
    if validate:
        validate_password_strength(password)

    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt(rounds=rounds)
    hashed_bytes = bcrypt.hashpw(password_bytes, salt)

    return hashed_bytes.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a plaintext password against a stored bcrypt salted hash in constant time.

    Args:
        plain_password (str): Candidate plaintext password provided by user.
        hashed_password (str): Stored bcrypt hash string from database.

    Returns:
        bool: True if the candidate password matches the hash, False otherwise.
    """
    if not plain_password or not hashed_password:
        return False

    try:
        plain_bytes = plain_password.encode("utf-8")
        hash_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(plain_bytes, hash_bytes)
    except (ValueError, TypeError, Exception):
        return False
