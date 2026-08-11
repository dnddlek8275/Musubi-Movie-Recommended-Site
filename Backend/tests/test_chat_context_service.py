import json
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from app.services.chat_context_service import build_chat_user_context


class ChatContextServiceTests(TestCase):
    @patch("app.services.chat_context_service.get_combined_user_preference_signals")
    @patch("app.services.chat_context_service.get_user")
    def test_builds_structured_context_from_profile_and_ranked_preferences(
        self,
        get_user,
        get_signals,
    ):
        get_user.return_value = SimpleNamespace(personal_context="잔인한 영화는 피하고 싶음")
        get_signals.return_value = [
            SimpleNamespace(preference_type="genre", preference_value="SF", score=9.0),
            SimpleNamespace(preference_type="keyword", preference_value="인공지능", score=8.0),
            SimpleNamespace(preference_type="actor", preference_value="배우 A", score=7.0),
        ]

        payload = json.loads(build_chat_user_context(object(), 7))

        self.assertEqual(payload["personal_context"], "잔인한 영화는 피하고 싶음")
        self.assertEqual(payload["preferences"]["genre"], ["SF"])
        self.assertEqual(payload["preferences"]["keyword"], ["인공지능"])
        self.assertEqual(payload["preferences"]["actor"], ["배우 A"])
