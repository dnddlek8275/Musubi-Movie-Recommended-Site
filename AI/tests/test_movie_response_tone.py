import unittest

from pipeline.response_tone import (
    enforce_general_polite_answer,
    has_informal_ending,
    has_stiff_ending,
)


class MovieResponseToneTests(unittest.TestCase):
    def test_actual_informal_answer_is_converted_to_polite_tone(self):
        answer = (
            "‘도그맨’은 정말 재밌고 가벼운 액션 영화야!\n\n"
            "유머도 많이 나와서 기분 전환하기 딱이야."
        )
        polished = enforce_general_polite_answer(answer, [{"title": "도그맨"}])

        self.assertIn("영화예요!", polished)
        self.assertIn("딱이에요.", polished)
        self.assertFalse(has_informal_ending(polished))

    def test_existing_polite_answer_is_unchanged(self):
        answer = "‘도그맨’을 추천해요.\n\n기분 전환하기 좋은 영화예요."
        self.assertEqual(
            enforce_general_polite_answer(answer, [{"title": "도그맨"}]),
            answer,
        )

    def test_stiff_formal_ending_is_softened(self):
        answer = (
            "‘러브, 어게인’을 추천해 드릴게요.\n\n"
            "데이트에 좋은 선택입니다. 로맨틱한 분위기를 연출합니다."
        )
        polished = enforce_general_polite_answer(answer, [{"title": "러브, 어게인"}])

        self.assertIn("선택이에요.", polished)
        self.assertIn("연출해요.", polished)
        self.assertFalse(has_stiff_ending(polished))

    def test_unhandled_plain_style_uses_grounded_fallback(self):
        answer = "이 영화는 가족이 함께 즐길 만하다."
        movies = [{"title": "도그맨"}, {"title": "스파이 지니어스"}]
        polished = enforce_general_polite_answer(answer, movies)

        self.assertIn("‘도그맨’", polished)
        self.assertIn("‘스파이 지니어스’", polished)
        self.assertNotIn("즐길 만하다", polished)
        self.assertFalse(has_informal_ending(polished))


if __name__ == "__main__":
    unittest.main()
