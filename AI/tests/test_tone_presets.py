import json
import unittest
from pathlib import Path

from pipeline.tone_presets import (
    build_group_movie_reaction_fallback,
    build_group_reaction_fallback,
    TONE_PRESETS,
    assigned_characters,
    build_tone_guidance,
    build_turn_guidance,
    enforce_dialogue_policy,
    is_character_relation_question,
    mentioned_characters,
)


class TonePresetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        profile_path = Path(__file__).resolve().parents[1] / "character_profiles_ALL_50.json"
        cls.profile_names = set(json.loads(profile_path.read_text())["characters"])

    def test_every_profile_has_exactly_one_preset(self):
        all_assignments = [
            character
            for preset in TONE_PRESETS.values()
            for character in preset["characters"]
        ]
        self.assertEqual(set(all_assignments), self.profile_names)
        self.assertEqual(len(all_assignments), len(set(all_assignments)))

    def test_maseokdo_has_specific_safety_guidance(self):
        guidance = build_tone_guidance("마석도")
        self.assertIn("타깃", guidance)
        self.assertIn("거창한", guidance)

    def test_emotion_turn_asks_before_advising(self):
        guidance = build_turn_guidance("오늘 기분 너무 별론데")
        self.assertIn("질문 하나", guidance)
        self.assertIn("해결책", guidance)

    def test_relationship_turn_requires_grounded_answer(self):
        guidance = build_turn_guidance("강해상이라고 알아?")
        self.assertIn("확인된 정보", guidance)

    def test_context_free_hypothetical_requires_one_question(self):
        guidance = build_turn_guidance("너라면 어떻게 할 거야")
        self.assertIn("정보가 없다", guidance)
        self.assertIn("질문 하나", guidance)
        self.assertIn("결의", guidance)

    def test_context_free_maseokdo_answer_is_deterministically_safe(self):
        answer = enforce_dialogue_policy(
            "마석도",
            "너라면 어떻게 할 거야",
            "기분 안 좋으면 한 판 붙어버리면 된다.",
        )
        self.assertEqual(answer, "무슨 일인지 알아야 얘기하지. 뭐 때문에 기분이 별론데?")

    def test_ungrounded_character_relation_is_not_invented(self):
        answer = enforce_dialogue_policy(
            "마석도",
            "강해상이라고 알아?",
            "내 친구이자 적이다.",
            relation_grounded=False,
        )
        self.assertNotIn("친구", answer)
        self.assertIn("확인할 정보가 없어", answer)

    def test_registered_character_mention_is_detected(self):
        profiles = {"characters": {"마석도": {}, "강해상": {}, "토니 스타크": {}}}
        self.assertEqual(
            mentioned_characters("강해상이라고 알아?", profiles, exclude="마석도"),
            ["강해상"],
        )

    def test_character_opinion_is_not_misclassified_as_relation_question(self):
        message = "장첸이 너무 잘생겨 보여 어떡해"
        self.assertFalse(is_character_relation_question(message))
        answer = enforce_dialogue_policy(
            "마석도",
            message,
            "취향 한번 독특하네. 뭐, 그렇게 보일 수도 있지.",
            relation_grounded=False,
        )
        self.assertEqual(
            answer,
            "잘생겨 보이면 좋아하면 되지, 뭘 어떡해. 근데 얼굴만 보고 너무 푹 빠지진 마.",
        )

    def test_group_attraction_opinion_is_not_relation_question(self):
        self.assertFalse(is_character_relation_question(
            "장첸이 잘생겼다는 말에 둘은 어떻게 생각해?"
        ))
        answer = enforce_dialogue_policy(
            "장첸",
            "장첸이 잘생겼다는 말에 어떻게 생각해?",
            "진짜 힘은 의지에서 나오는 법이다.",
        )
        self.assertEqual(answer, "보는 눈은 있네. 그 말은 마음에 드는데.")

    def test_character_knowledge_question_requires_grounding(self):
        self.assertTrue(is_character_relation_question("강해상이라고 알아?"))

    def test_ordinary_friend_problem_is_not_character_relation(self):
        self.assertFalse(is_character_relation_question(
            "친구랑 다퉜는데 먼저 연락할지 고민이야. 둘의 의견이 궁금해."
        ))

    def test_character_opinion_question_requires_grounding(self):
        self.assertTrue(is_character_relation_question("강해상에 대해 어떻게 생각해?"))

    def test_unregistered_character_opinion_is_still_a_relation_question(self):
        self.assertTrue(is_character_relation_question("울버린에 대해 어떻게 생각해?"))
        answer = enforce_dialogue_policy(
            "데드풀",
            "울버린에 대해 어떻게 생각해?",
            "내 가장 친한 친구야.",
            relation_grounded=False,
        )
        self.assertNotIn("가장 친한 친구", answer)

    def test_verified_relation_uses_only_curated_answer(self):
        answer = enforce_dialogue_policy(
            "마석도",
            "강해상에 대해 어떻게 생각해?",
            "내 손에 놀아야 할 타깃이다.",
            relation_grounded=True,
            relation_answer="강해상? 해외에서 범죄를 저질러서 내가 쫓던 놈이지.",
        )
        self.assertEqual(answer, "강해상? 해외에서 범죄를 저질러서 내가 쫓던 놈이지.")
        self.assertNotIn("타깃", answer)

    def test_followup_uses_history_instead_of_clarification(self):
        history = [{"role": "user", "content": "친구가 내 비밀을 말해서 화가 났어."}]
        guidance = build_turn_guidance("그럼 너라면 지금 뭐라고 답할 거야?", history)
        self.assertIn("대화 이력", guidance)
        self.assertIn("다시 묻지 않는다", guidance)
        self.assertIn("친구가 내 비밀", guidance)
        answer = enforce_dialogue_policy(
            "마석도",
            "그럼 너라면 지금 뭐라고 답할 거야?",
            "그건 네가 직접 말해야지.",
            has_history=True,
        )
        self.assertEqual(answer, "그건 네가 직접 말해야지.")

    def test_late_friend_request_returns_usable_words(self):
        answer = enforce_dialogue_policy(
            "마석도",
            "친구가 한 시간 늦고 사과도 안 했어. 뭐라고 말할까?",
            "상대에게 대가를 치르게 해.",
        )
        self.assertIn("다음부터 늦으면 미리 연락해 줘", answer)
        self.assertNotIn("대가", answer)

    def test_history_secret_followup_returns_usable_words(self):
        history = [{"role": "user", "content": "친구가 내 비밀을 다른 사람에게 말했어."}]
        answer = enforce_dialogue_policy(
            "토니 스타크",
            "그럼 너라면 지금 뭐라고 답할 거야?",
            "내 카드를 보여주겠다고 해.",
            has_history=True,
            history=history,
        )
        self.assertIn("내가 믿고 말한 걸", answer)
        self.assertNotIn("카드", answer)

    def test_presentation_followup_returns_usable_words(self):
        history = [{"role": "user", "content": "오늘 회사 발표를 망쳤어."}]
        answer = enforce_dialogue_policy(
            "토니 스타크",
            "상사한테 뭐라고 말하면 좋을까?",
            "아이언맨 슈트의 결함이라고 말해.",
            has_history=True,
            history=history,
        )
        self.assertIn("부족했던 부분을 정리했습니다", answer)
        self.assertNotIn("아이언맨", answer)

    def test_study_not_started_is_not_treated_as_wrong_answers(self):
        answer = enforce_dialogue_policy(
            "헤르미온느",
            "시험 공부가 하나도 안 됐어.",
            "어디서 틀렸는지 확인해요.",
        )
        self.assertIn("25분", answer)
        self.assertNotIn("틀렸", answer)

    def test_action_followup_uses_previous_presentation_context(self):
        history = [{"role": "user", "content": "오늘 발표를 완전히 망쳤어."}]
        answer = enforce_dialogue_policy(
            "토니 스타크",
            "지금 뭘 먼저 준비할까?",
            "일단 쉬어.",
            has_history=True,
            history=history,
        )
        self.assertIn("핵심 한 문장", answer)

    def test_friend_conflict_uses_practical_answer_without_invented_lore(self):
        answer = enforce_dialogue_policy(
            "엘사",
            "친구랑 다퉜는데 먼저 연락할지 고민이야.",
            "내가 브리저스와 싸웠을 때도 그랬어요.",
        )
        self.assertIn("먼저 연락하되", answer)
        self.assertNotIn("브리저스", answer)

    def test_interview_anxiety_uses_short_specific_answer(self):
        answer = enforce_dialogue_policy(
            "토니 스타크",
            "내일 면접이라 긴장돼. 짧게 한마디만 해줘.",
            "오늘 뭔가 꼬였나 보네.",
        )
        self.assertIn("첫 답", answer)
        self.assertNotIn("꼬였", answer)

    def test_invented_current_plan_is_replaced_with_contextual_choice(self):
        history = [{"role": "user", "content": "시험을 망칠 것 같아서 불안해."}]
        answer = enforce_dialogue_policy(
            "헤르미온느",
            "너라면 오늘 뭐부터 할래?",
            "오늘 저녁엔 가족과 자습하고 친구들과 영화를 보러 갈 계획이야.",
            has_history=True,
            history=history,
        )
        self.assertIn("시험 범위를 잘게 나누고", answer)
        self.assertNotIn("영화를 보러", answer)

    def test_generic_failure_cliche_is_replaced_with_specific_response(self):
        answer = enforce_dialogue_policy(
            "마석도",
            "시험을 망쳤어.",
            "한 번의 실패일 뿐이야. 다음엔 더 잘 보면 돼. 계속 도전하면 된다.",
        )
        self.assertIn("어디서 틀렸는지", answer)
        self.assertNotIn("계속 도전", answer)

    def test_failure_context_is_stable_even_without_detected_cliche(self):
        answer = enforce_dialogue_policy(
            "토니 스타크",
            "오늘 일이 완전히 꼬였어.",
            "세상은 이미 수십 번 무너졌으니 다시 시작하면 돼.",
        )
        self.assertIn("어디서부터 잘못됐어", answer)
        self.assertNotIn("세상은", answer)

    def test_cause_free_emotion_uses_distinct_type_fallbacks(self):
        replies = {
            character: enforce_dialogue_policy(character, "오늘 기분 너무 별론데", "나도 힘들어")
            for character in ("마석도", "토니 스타크", "알버스 덤블도어", "골룸")
        }
        self.assertEqual(len(set(replies.values())), 4)
        self.assertTrue(all(reply.endswith(("?", "까?")) for reply in replies.values()))
        self.assertNotIn("반지", replies["골룸"])
        self.assertNotIn("강한", replies["토니 스타크"])

    def test_representative_fallbacks_are_character_specific(self):
        representatives = (
            "마석도", "장첸", "토니 스타크", "피터 파커", "데드풀",
            "헤르미온느", "알버스 덤블도어", "골룸", "엘사", "브루스 웨인",
        )
        emotion_replies = {
            enforce_dialogue_policy(name, "오늘 기분이 너무 별로야.", "괜찮아")
            for name in representatives
        }
        relation_replies = {
            enforce_dialogue_policy(
                name,
                "등록되지 않은 인물에 대해 어떻게 생각해?",
                "내 친구야.",
                relation_grounded=False,
            )
            for name in representatives
        }
        self.assertEqual(len(emotion_replies), len(representatives))
        self.assertEqual(len(relation_replies), len(representatives))

    def test_group_emotion_reactions_listen_instead_of_repeating_question(self):
        replies = {
            name: build_group_reaction_fallback(name, "오늘 기분이 너무 별로야.")
            for name in ("데드풀", "엘사", "브루스 웨인")
        }
        self.assertTrue(all(replies.values()))
        self.assertTrue(all("?" not in reply for reply in replies.values()))
        self.assertEqual(len(set(replies.values())), 3)
        self.assertIsNone(build_group_reaction_fallback("엘사", "친구가 약속에 늦어서 속상해."))

    def test_group_failure_reactions_are_stable_and_preset_specific(self):
        replies = {
            name: build_group_reaction_fallback(name, "시험을 망쳤어.")
            for name in ("헤르미온느", "마석도", "데드풀")
        }
        self.assertTrue(all(replies.values()))
        self.assertEqual(len(set(replies.values())), 3)
        self.assertTrue(all("?" not in reply for reply in replies.values()))

    def test_group_movie_reactions_do_not_invent_titles_or_relationships(self):
        replies = {
            name: build_group_movie_reaction_fallback(name)
            for name in ("데드풀", "엘사", "브루스 웨인")
        }
        self.assertEqual(len(set(replies.values())), 3)
        self.assertTrue(all("추천" in reply or "선택" in reply for reply in replies.values()))
        self.assertTrue(all("토니" not in reply for reply in replies.values()))


if __name__ == "__main__":
    unittest.main()
