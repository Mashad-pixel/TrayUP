"""Validation rules for student and staff account details."""

import re

MAX_NAME_LENGTH = 100
MAX_EMAIL_LENGTH = 120
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128

_EMAIL_PATTERN = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+")


def normalize_email(raw_email):
    """Normalize email addresses before uniqueness checks."""
    return raw_email.strip().lower()


def is_valid_email(email):
    return len(email) <= MAX_EMAIL_LENGTH and _EMAIL_PATTERN.fullmatch(email) is not None


def normalize_mobile_number(raw_mobile_number):
    """Normalize an Indian mobile number to E.164 format, or return None."""
    if not isinstance(raw_mobile_number, str):
        return None

    value = raw_mobile_number.strip()
    if not re.fullmatch(r"\+?[\d()\s-]+", value):
        return None

    digits = re.sub(r"\D", "", value)
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]

    if re.fullmatch(r"[6-9]\d{9}", digits):
        return f"+91{digits}"
    return None


def is_valid_name(name):
    return 0 < len(name) <= MAX_NAME_LENGTH


def password_problem(password):
    """Return a message for an unacceptable password, or None."""
    if not isinstance(password, str):
        return "Password is required."
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
    if len(password) > MAX_PASSWORD_LENGTH:
        return f"Password must be at most {MAX_PASSWORD_LENGTH} characters."
    if not any(char.isalpha() for char in password) or not any(char.isdigit() for char in password):
        return "Password must include at least one letter and one number."
    return None
