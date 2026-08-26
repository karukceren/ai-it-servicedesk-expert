"""
Unit Tests for Core Security & Authentication Logic
===================================================
Project: Akıllı Servis Masası ve Sistem Uzmanı Chatbot (PRJIC20260201)
"""

import pytest
from src.core.security import (
    validate_password_strength,
    validate_email_format,
    hash_password,
    verify_password,
    PasswordValidationError,
    EmailValidationError,
)


# ===========================================================================
# 1. Password Strength Validation Tests
# ===========================================================================
class TestPasswordStrength:
    """Test suite for password complexity validation rules."""

    @pytest.mark.parametrize(
        "valid_password",
        [
            "StrongPass1",
            "Admin2026!",
            "Corporate#Secure9",
            "P@ssw0rdSecure",
            "Aa1bb2cc3dd",
            "VeryLongPasswordWithNumbers123"
        ]
    )
    def test_valid_passwords(self, valid_password: str):
        """Valid passwords satisfying all complexity criteria must return True."""
        assert validate_password_strength(valid_password) is True

    def test_empty_or_none_password(self):
        """Empty or None password must raise PasswordValidationError."""
        with pytest.raises(PasswordValidationError, match="boş bırakılamaz"):
            validate_password_strength("")

        with pytest.raises(PasswordValidationError):
            validate_password_strength(None)  # type: ignore

    def test_short_password(self):
        """Passwords shorter than 8 characters must fail length check."""
        with pytest.raises(PasswordValidationError, match="En az 8 karakter"):
            validate_password_strength("Aa1!")

    def test_missing_uppercase(self):
        """Passwords without uppercase letters must fail uppercase check."""
        with pytest.raises(PasswordValidationError, match="büyük harf"):
            validate_password_strength("lowercase123!")

    def test_missing_lowercase(self):
        """Passwords without lowercase letters must fail lowercase check."""
        with pytest.raises(PasswordValidationError, match="küçük harf"):
            validate_password_strength("UPPERCASE123!")

    def test_missing_digit(self):
        """Passwords without numeric digits must fail digit check."""
        with pytest.raises(PasswordValidationError, match="rakam"):
            validate_password_strength("NoDigitsHere!")

    def test_multiple_failures_message(self):
        """Multiple failed criteria should all be listed in the error message."""
        with pytest.raises(PasswordValidationError) as exc_info:
            validate_password_strength("short")
        msg = str(exc_info.value)
        assert "8 karakter" in msg
        assert "büyük harf" in msg
        assert "rakam" in msg


# ===========================================================================
# 2. Email Format Validation Tests
# ===========================================================================
class TestEmailFormat:
    """Test suite for RFC 5322 email format validation."""

    @pytest.mark.parametrize(
        "valid_email",
        [
            "user@corp.local",
            "admin.support@company.com",
            "john.doe+service@sub.domain.org",
            "engineer123@tech.net",
            "first.last@enterprise.co.uk",
            "IT_Admin@corp.io"
        ]
    )
    def test_valid_emails(self, valid_email: str):
        """Valid RFC 5322 emails must return True."""
        assert validate_email_format(valid_email) is True

    @pytest.mark.parametrize(
        "invalid_email",
        [
            "",
            "   ",
            "plainaddress",
            "@missinguser.com",
            "missingdomain@",
            "user@.com",
            "user@domain..com",
            "user name@domain.com",
            "user@domain@another.com"
        ]
    )
    def test_invalid_emails(self, invalid_email: str):
        """Invalid email structures must raise EmailValidationError."""
        with pytest.raises(EmailValidationError):
            validate_email_format(invalid_email)


# ===========================================================================
# 3. Salted Hash Password & Verification Tests
# ===========================================================================
class TestPasswordHashing:
    """Test suite for bcrypt salted password hashing and constant-time verification."""

    def test_hash_generation_and_verification(self):
        """Hashing a strong password and verifying with identical password must succeed."""
        password = "SecurePassword2026!"
        hashed = hash_password(password, rounds=10)

        # Must be valid bcrypt hash string
        assert isinstance(hashed, str)
        assert hashed.startswith("$2b$") or hashed.startswith("$2a$")
        assert hashed != password

        # Positive verification
        assert verify_password(password, hashed) is True

        # Negative verification
        assert verify_password("WrongPassword123!", hashed) is False
        assert verify_password("securepassword2026!", hashed) is False  # Case sensitive

    def test_salt_uniqueness(self):
        """Hashing the same password twice must produce different salted hashes."""
        password = "CorporatePass123"
        hash1 = hash_password(password, rounds=8)
        hash2 = hash_password(password, rounds=8)

        assert hash1 != hash2
        assert verify_password(password, hash1) is True
        assert verify_password(password, hash2) is True

    def test_hash_with_weak_password_validation(self):
        """hash_password must enforce password validation when validate=True."""
        with pytest.raises(PasswordValidationError):
            hash_password("weak", validate=True)

        # When validate=False, hashing proceeds without complexity checks
        weak_hash = hash_password("weak", rounds=6, validate=False)
        assert verify_password("weak", weak_hash) is True

    def test_verify_password_edge_cases(self):
        """verify_password must safely return False on empty or corrupted inputs."""
        assert verify_password("", "$2b$12$invalidhashvalue...") is False
        assert verify_password("Pass123!", "") is False
        assert verify_password("Pass123!", "not_a_bcrypt_hash") is False
        assert verify_password(None, None) is False  # type: ignore


# ===========================================================================
# Direct Execution Entrypoint
# ===========================================================================
if __name__ == "__main__":
    pytest.main(["-v", __file__])
