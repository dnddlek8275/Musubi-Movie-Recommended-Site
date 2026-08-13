import unittest

from pipeline.dialogue_guard import general_history_recall_reply


class GeneralHistoryRecallTests(unittest.TestCase):
    def test_recalls_movie_from_recorded_user_history(self):
        history = [
            {"role": "user", "content": "내가 가장 좋아하는 영화는 인터스텔라야."},
            {"role": "assistant", "content": "인터스텔라를 좋아하시는군요."},
        ]
        self.assertEqual(
            general_history_recall_reply("내가 방금 말한 영화가 뭐였지?", history),
            "방금 말한 영화는 인터스텔라야.",
        )

    def test_does_not_invent_when_history_has_no_movie_title(self):
        history = [{"role": "user", "content": "오늘 기분이 좋아."}]
        self.assertEqual(
            general_history_recall_reply("아까 말한 영화 제목이 뭐였지?", history),
            "대화 기록에서 방금 말한 영화 제목을 정확히 확인하지 못했어. 제목을 한 번만 다시 알려줘.",
        )

    def test_ignores_non_recall_questions(self):
        self.assertIsNone(
            general_history_recall_reply(
                "인터스텔라와 비슷한 영화 추천해줘",
                [{"role": "user", "content": "좋아하는 영화는 인터스텔라야."}],
            )
        )


if __name__ == "__main__":
    unittest.main()
