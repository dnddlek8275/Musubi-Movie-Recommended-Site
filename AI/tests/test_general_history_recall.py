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

    def test_latest_corrected_user_name_wins(self):
        history = [
            {"role": "user", "content": "나를 민수라고 불러줘."},
            {"role": "assistant", "content": "알겠어, 민수야."},
            {"role": "user", "content": "민수 말고 지훈이라고 불러줘."},
        ]
        self.assertEqual(
            general_history_recall_reply("내가 불러달라고 한 이름이 뭐였지?", history),
            "지금 불러달라고 한 이름은 지훈이야.",
        )

    def test_latest_schedule_day_wins(self):
        history = [
            {"role": "user", "content": "미팅은 월요일이야."},
            {"role": "user", "content": "최종적으로 금요일이야."},
        ]
        self.assertEqual(
            general_history_recall_reply("최종 미팅 요일이 뭐였지?", history),
            "최종 미팅 요일은 금요일이야.",
        )

    def test_recalls_user_stated_confidence_cause_only(self):
        history = [
            {
                "role": "user",
                "content": "오늘 팀 발표에서 준비한 걸 제대로 못 보여줘서 자신감이 많이 떨어졌어.",
            },
            {"role": "assistant", "content": "발표 내용을 분석해보자."},
            {"role": "user", "content": "용기 나는 영화를 추천해줘."},
        ]
        answer = general_history_recall_reply(
            "영화 얘기는 됐고, 내가 아까 왜 자신감이 떨어졌다고 했지?",
            history,
        )
        self.assertIn("팀 발표에서 준비한 걸 제대로 못 보여줘서", answer)
        self.assertNotIn("영화", answer)


if __name__ == "__main__":
    unittest.main()
