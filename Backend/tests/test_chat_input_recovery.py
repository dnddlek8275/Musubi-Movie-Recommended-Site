import unittest
import importlib.util
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

from app.services.chat_input_recovery import (
    MEANINGFUL_JAMO_SHORTHANDS,
    RECOVERY_UI_DELAY_SECONDS,
    get_general_chat_recovery,
    wait_for_recovery_ui,
)


def _load_ai_input_clarity_module():
    module_path = Path(__file__).resolve().parents[2] / "AI" / "pipeline" / "input_clarity.py"
    spec = importlib.util.spec_from_file_location("musubi_ai_input_clarity", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ChatInputRecoveryTests(unittest.TestCase):
    def test_incomplete_or_random_jamo_is_recovered(self):
        for message in ("ㅇ", "ㅏ", "ㄱ.", "ㄴㄹㅇㄹㄴ", "ㅁㄴㅇㄹ"):
            with self.subTest(message=message):
                result = get_general_chat_recovery(message)
                self.assertIsNotNone(result)
                self.assertEqual(result.kind, "ambiguous_jamo")

    def test_meaningful_jamo_shorthand_is_not_intercepted(self):
        for message in ("ㅇㅇ", "ㅇㅇ!", "ㄴㄴ", "ㄱㄱ", "ㅎㅇ"):
            with self.subTest(message=message):
                self.assertIsNone(get_general_chat_recovery(message))

    def test_backend_and_ai_shorthand_rules_stay_in_sync(self):
        ai_input_clarity = _load_ai_input_clarity_module()
        self.assertEqual(
            MEANINGFUL_JAMO_SHORTHANDS,
            ai_input_clarity.MEANINGFUL_JAMO_SHORTHANDS,
        )

    def test_backend_and_ai_recovery_kinds_stay_in_sync(self):
        ai_input_clarity = _load_ai_input_clarity_module()
        for message in ("ㅇ", "ㄴㄹㅇㄹㄴ", ".", "...", "?", "ㅋㅋ", "ㅠㅠ"):
            with self.subTest(message=message):
                backend = get_general_chat_recovery(message)
                ai = ai_input_clarity.get_input_recovery(message)
                self.assertIsNotNone(backend)
                self.assertIsNotNone(ai)
                self.assertEqual(backend.kind, ai.kind)

    def test_punctuation_and_ellipsis_have_distinct_replies(self):
        dot = get_general_chat_recovery(".")
        ellipsis = get_general_chat_recovery("...")
        question = get_general_chat_recovery("?")

        self.assertEqual(dot.kind, "punctuation")
        self.assertEqual(ellipsis.kind, "ellipsis")
        self.assertEqual(question.kind, "question_mark")

    def test_reaction_only_input_gets_emotion(self):
        self.assertEqual(get_general_chat_recovery("ㅋㅋ").emotion, "joy")
        self.assertEqual(get_general_chat_recovery("ㅠㅠ").emotion, "sorry")

    def test_meaningful_short_messages_are_not_intercepted(self):
        for message in ("왜", "응", "네", "ㄴㄴ 그거 말고", "영화 추천해줘", "😄"):
            with self.subTest(message=message):
                self.assertIsNone(get_general_chat_recovery(message))

    def test_recovery_ui_waits_for_configured_delay(self):
        async def run_test():
            with patch("app.services.chat_input_recovery.asyncio.sleep", new=AsyncMock()) as sleep:
                await wait_for_recovery_ui()
                sleep.assert_awaited_once_with(RECOVERY_UI_DELAY_SECONDS)

        import asyncio
        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
