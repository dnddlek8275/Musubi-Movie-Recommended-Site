import unittest

from app.services.email.email_service import (
    build_contact_inquiry_message,
    build_contact_reply_message,
    build_signup_verification_message,
)


class SignupVerificationEmailTests(unittest.TestCase):
    def test_message_contains_plain_text_and_html_versions(self):
        message = build_signup_verification_message("member@example.com", "394971")

        self.assertEqual(message["To"], "member@example.com")
        self.assertIn("394971", message["Subject"])
        self.assertTrue(message.is_multipart())

        parts = list(message.iter_parts())
        self.assertEqual([part.get_content_type() for part in parts], ["text/plain", "text/html"])
        self.assertIn("394971", parts[0].get_content())
        self.assertIn("394971", parts[1].get_content())
        self.assertIn("MUSUBI", parts[1].get_content())

    def test_contact_message_escapes_user_html_and_sets_reply_to(self):
        message = build_contact_inquiry_message(
            inquiry_id=27,
            category="movie_data",
            reply_email="viewer@example.com",
            subject="영화 정보 수정",
            content="<script>alert('x')</script>\n개봉일을 확인해 주세요.",
            member=False,
        )

        self.assertEqual(message["Reply-To"], "viewer@example.com")
        self.assertIn("#27", message["Subject"])
        html = list(message.iter_parts())[1].get_content()
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("영화 정보 수정 요청", html)

    def test_contact_reply_escapes_admin_html_and_targets_requester(self):
        message = build_contact_reply_message(
            email="viewer@example.com",
            inquiry_id=27,
            subject="영화 정보 수정",
            body="<b>확인했습니다.</b>\n수정 후 알려드릴게요.",
        )

        self.assertEqual(message["To"], "viewer@example.com")
        self.assertIn("#27", message["Subject"])
        html = list(message.iter_parts())[1].get_content()
        self.assertNotIn("<b>확인했습니다.</b>", html)
        self.assertIn("&lt;b&gt;확인했습니다.&lt;/b&gt;", html)
        self.assertIn("MUSUBI SUPPORT", html)


if __name__ == "__main__":
    unittest.main()
