import pytest

from app.services.password_validation import validate_password_strength


@pytest.mark.parametrize(
    "password, login_id, expected_valid",
    [
        ("Ab1!2345", None, True),
        ("short1!", None, False),
        ("12345678!", None, False),
        ("NoDigits!!", None, False),
        ("NoSpecial1", None, False),
        ("Ab1!2345", "Ab1!2345", False),
    ],
)
def test_validate_password_strength(password, login_id, expected_valid):
    errors = validate_password_strength(password, login_id=login_id)
    if expected_valid:
        assert errors == []
    else:
        assert errors
