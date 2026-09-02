import re

SPECIAL_CHAR_PATTERN = re.compile(r'[!@#$%^&*(),.?":{}|<>]')
LETTER_PATTERN = re.compile(r"[A-Za-z]")
DIGIT_PATTERN = re.compile(r"\d")


def validate_password_strength(
    password: str, *, login_id: str | None = None
) -> list[str]:
    """Return validation error messages (empty if valid)."""
    errors: list[str] = []

    if len(password) < 8:
        errors.append("Password should be at least 8 characters.")
    if login_id and login_id in password:
        errors.append("Password should not contain login id.")

    has_letter = bool(LETTER_PATTERN.search(password))
    has_digit = bool(DIGIT_PATTERN.search(password))
    has_special = bool(SPECIAL_CHAR_PATTERN.search(password))
    if not (has_letter and has_digit and has_special):
        errors.append(
            "Password must include letters, numbers, and special characters."
        )

    return errors
