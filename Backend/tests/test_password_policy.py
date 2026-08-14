import unittest

from pydantic import ValidationError

from app.core.password_policy import validate_password_policy
from app.schemas.users import PasswordResetConfirmRequest, RegisterRequest


VALID_PASSWORD = "Password1!"


class PasswordPolicyTests(unittest.TestCase):
    def test_signup_and_password_reset_accept_the_same_valid_password(self):
        signup = RegisterRequest(
            email="user@example.com",
            password=VALID_PASSWORD,
            nickname="사용자",
            verification_code="123456",
        )
        reset = PasswordResetConfirmRequest(token="t" * 32, new_password=VALID_PASSWORD)

        self.assertEqual(signup.password, VALID_PASSWORD)
        self.assertEqual(reset.new_password, VALID_PASSWORD)

    def test_signup_and_password_reset_reject_the_same_weak_passwords(self):
        for password in (
            "Short1!",
            "비밀번호123!",
            "Password!!",
            "Password12",
            "Password 1!",
        ):
            with self.subTest(password=password):
                with self.assertRaises(ValidationError):
                    RegisterRequest(
                        email="user@example.com",
                        password=password,
                        nickname="사용자",
                        verification_code="123456",
                    )
                with self.assertRaises(ValidationError):
                    PasswordResetConfirmRequest(token="t" * 32, new_password=password)

    def test_internal_password_policy_rejects_weak_password(self):
        with self.assertRaisesRegex(ValueError, "특수문자"):
            validate_password_policy("Password12")


if __name__ == "__main__":
    unittest.main()
