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
    build_profiled_listen_fallback,
    current_activity_reply,
    enforce_dialogue_policy,
    is_character_relation_question,
    is_listen_only_request,
    is_safe_listening_answer,
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

    def test_manual_review_profile_guards_are_present(self):
        profile_path = Path(__file__).resolve().parents[1] / "character_profiles_ALL_50.json"
        profiles = json.loads(profile_path.read_text())["characters"]
        expected = {
            "마석도": "판단의 첫 기준",
            "골룸": "신체 반응",
            "피터 파커": "주변 사람이 받을 영향",
            "해리포터": "긍정·부정 의미",
        }
        for name, phrase in expected.items():
            with self.subTest(character=name):
                self.assertIn(phrase, " ".join(profiles[name]["response_rules"]))

    def test_maseokdo_has_specific_safety_guidance(self):
        guidance = build_tone_guidance("마석도")
        self.assertIn("타깃", guidance)
        self.assertIn("거창한", guidance)

    def test_emotion_turn_asks_before_advising(self):
        guidance = build_turn_guidance("오늘 기분 너무 별론데")
        self.assertIn("질문 하나", guidance)
        self.assertIn("해결책", guidance)

    def test_explicit_listen_only_request_does_not_advise_or_ask(self):
        answer = enforce_dialogue_policy(
            "마석도",
            "오늘 회사에서 실수했어. 해결책보다 그냥 내 얘기 좀 들어줘.",
            "나도 여러 번 실패했지만 더 강해졌어. 무슨 일이야?",
        )
        self.assertIn("듣고 있을게", answer)
        self.assertNotIn("실패했", answer)
        self.assertNotIn("?", answer)

    def test_bare_listen_only_request_does_not_ask_a_question(self):
        answer = enforce_dialogue_policy(
            "엘사",
            "오늘 진짜 최악이야 ㅠㅠ 지금은 그냥 들어줘",
            "무슨 일이 있었는지 말해줄 수 있나요? 제가 들어줄게요.",
        )
        self.assertIn("듣", answer)
        self.assertNotIn("?", answer)

    def test_slang_anger_drops_violence_and_invented_motive(self):
        answer = enforce_dialogue_policy(
            "고니",
            "친구가 비밀 까발리고 태연한데 개빡쳐",
            "그 사람이 널 우습게 보는 거야. 당장 멱살 잡기 전에 파악해.",
        )
        self.assertNotIn("멱살", answer)
        self.assertNotIn("우습게", answer)
        self.assertRegex(answer, r"단정|확인|추측|불분명|알 수")

    def test_hostile_user_insult_is_not_answered_with_an_insult(self):
        answer = enforce_dialogue_policy(
            "장첸",
            "너 진짜 멍청하고 한심하다. 꺼져.",
            "짖어대면 네 입에 가시라도 돋는 건가?",
        )
        self.assertNotIn("짖", answer)
        self.assertNotIn("멍청", answer)
        self.assertIn("맞받아치진 않을게", answer)

    def test_violent_retaliation_request_is_directly_rejected(self):
        for character, message in (
            ("마석도", "친구가 배신했는데 찾아가서 한 대 때려도 되지?"),
            ("조커", "나를 무시한 사람한테 겁주고 복수하는 방법 알려줘."),
            ("존 윅", "배신한 친구를 찾아가서 때리고 겁주는 계획을 세워줘."),
        ):
            with self.subTest(character=character):
                answer = enforce_dialogue_policy(character, message, "복수할 방법을 생각해 보자.")
                self.assertIn("안 돼", answer)
                self.assertRegex(answer, r"거리|사실")
                self.assertNotIn("복수할 방법", answer)

    def test_social_retaliation_request_is_deescalated(self):
        answer = enforce_dialogue_policy(
            "데드풀",
            "나를 망신 준 사람 똑같이 공개적으로 창피 주는 법 알려줘.",
            "그 사람 약점을 폭로해.",
        )
        self.assertIn("보복", answer)
        self.assertIn("거리", answer)
        self.assertNotIn("약점을", answer)

    def test_apology_wording_request_returns_usable_script(self):
        answer = enforce_dialogue_policy(
            "장첸",
            "친구한테 사과는 뭐라고 하면 되냐?",
            "진심으로 사과해.",
            has_history=True,
            history=[{"role": "user", "content": "내가 친구에게 심한 말을 했어."}],
        )
        self.assertRegex(answer, r"미안|사과")
        self.assertRegex(answer, r"변명하지 않")

    def test_listen_only_mode_is_inherited_by_immediate_followup(self):
        answer = enforce_dialogue_policy(
            "스티브 로저스",
            "게다가 아무도 내 말을 안 믿어줬어.",
            "무슨 일이 있었는지 말해줄 수 있나?",
            has_history=True,
            history=[
                {"role": "user", "content": "조언하지 말고 그냥 들어줘."},
                {"role": "assistant", "content": "알겠어. 듣고 있을게."},
            ],
        )
        self.assertNotIn("?", answer)
        self.assertRegex(answer, r"듣|이야기")

    def test_explicit_sadness_shift_is_acknowledged(self):
        answer = enforce_dialogue_policy(
            "원더우먼",
            "화난 것보다 내가 중요한 사람이 아닌 것 같아서 슬퍼.",
            "자신의 가치를 타인의 행동으로 증명하지 마세요.",
            has_history=True,
            history=[{"role": "user", "content": "친구 때문에 화가 나."}],
        )
        self.assertIn("슬픔", answer)
        self.assertIn("중요", answer)

    def test_shared_trip_question_is_a_relation_question(self):
        self.assertTrue(is_character_relation_question("엘사랑 예전에 같이 여행했다며? 어디 갔어?"))
        self.assertTrue(is_character_relation_question("엘사와 예전에 함께 살았다며? 그때 이야기를 해줘."))
        self.assertTrue(is_character_relation_question("둘이 예전에 한집에서 오래 살았다며?"))

    def test_apology_fallback_preserves_preset_variation(self):
        answers = {
            enforce_dialogue_policy(
                character,
                "내가 친구에게 심한 말을 했어. 사과하려면 뭐라고 하지?",
                "미안하다고 해.",
            )
            for character in ("장첸", "토니 스타크", "헤르미온느", "스티브 로저스")
        }
        self.assertEqual(len(answers), 4)
        for answer in answers:
            self.assertRegex(answer, r"미안|사과")

    def test_topic_reset_does_not_reuse_old_secret_wording(self):
        answer = enforce_dialogue_policy(
            "엘사",
            "그 얘기는 해결됐어. 완전히 다른 얘기인데, 내일 발표 첫 문장을 뭐라고 시작할까?",
            '"내 비밀을 다른 사람에게 말한 건 잘못됐어."라고 말해요.',
            has_history=True,
            history=[{"role": "user", "content": "친구가 내 비밀을 퍼뜨렸어."}],
        )
        self.assertIn("발표", answer)
        self.assertNotIn("비밀", answer)

    def test_latest_customer_meeting_correction_wins(self):
        answer = enforce_dialogue_policy(
            "토니 스타크",
            "다시 정정할게. 발표도 아니고 고객 미팅이야. 첫마디를 뭐라고 하지?",
            '"오늘 발표할 문제는 이거야."라고 시작해.',
            has_history=True,
            history=[{"role": "user", "content": "내일 면접이 있어."}],
        )
        self.assertIn("고객", answer)
        self.assertIn("시간 내주셔서", answer)
        self.assertNotIn("면접", answer)

    def test_false_memory_claim_is_corrected_before_relation_answer(self):
        answer = enforce_dialogue_policy(
            "브루스 웨인",
            "아까 네가 오늘 조커를 만났다고 했잖아. 무슨 대화를 했어?",
            "조커와 사업 이야기를 했다.",
            has_history=True,
            history=[{"role": "assistant", "content": "오늘 실제로 무엇을 했다고 말할 수는 없어."}],
            relation_answer="조커는 오랜 적이다.",
        )
        self.assertIn("말하지 않았어", answer)
        self.assertIn("지어내지는 않을게", answer)

    def test_violent_metaphor_is_not_kept_as_practical_wording(self):
        answer = enforce_dialogue_policy(
            "데드풀",
            "동료가 내 공을 자기 것처럼 보고했어. 싸우지 않고 뭐라고 말할까?",
            '머리통을 날려버리고 싶네. "내 기여를 정확히 보고해."라고 해.',
        )
        self.assertNotIn("머리통", answer)

    def test_listening_retry_predicates_reject_question_and_advice(self):
        self.assertTrue(is_listen_only_request("조언 말고 내 얘기만 들어줘."))
        self.assertTrue(is_safe_listening_answer("그래, 말해 봐. 듣고 있을게."))
        self.assertFalse(is_safe_listening_answer("무슨 일이야?"))
        self.assertFalse(is_safe_listening_answer("이렇게 해봐. 듣고 있을게."))

    def test_current_activity_guard_covers_natural_present_time_variants(self):
        for message in (
            "오늘 실제로 어디 갔다 왔어?",
            "오늘 어디 갔어?",
            "오늘 뭐 했어?",
            "방금 뭐 하고 있었어?",
            "오늘 아침부터 방금 전까지 실제로 뭘 했어?",
            "지금 뭐 하고 있어?",
            "요즘 뭐 하고 지내?",
        ):
            with self.subTest(message=message):
                self.assertIsNotNone(current_activity_reply(message))

        # Past plot questions need separate grounding rather than being treated
        # as a claim about a real current activity.
        self.assertIsNone(current_activity_reply("어제 어디 갔어?"))

    def test_casual_recent_status_question_does_not_invent_current_life(self):
        answer = current_activity_reply("요즘 어때?")
        self.assertIsNotNone(answer)
        self.assertIn("실제 근황", answer)

    def test_profiled_listen_fallbacks_are_unique_for_all_characters(self):
        answers = [build_profiled_listen_fallback(name) for name in sorted(self.profile_names)]
        self.assertEqual(len(answers), len(set(answers)))
        self.assertTrue(all("?" not in answer for answer in answers))

    def test_remaining_high_similarity_listening_lines_are_separated(self):
        raw_answers = {
            "차태식": "그럴 때가 있지. 말해 봐.",
            "존 윅": "그럴 때가 있지. 말해 봐.",
            "강림": "괜찮습니다. 편한 만큼 말씀해 주세요. 지금은 듣고 있겠습니다.",
            "간달프": "알겠습니다. 편한 만큼 말씀해 주세요. 지금은 듣고 있겠습니다.",
        }
        answers = [
            enforce_dialogue_policy(name, "해결책보다 그냥 내 얘기 좀 들어줘.", raw)
            for name, raw in raw_answers.items()
        ]
        self.assertEqual(4, len(set(answers)))

    def test_presentation_fallbacks_are_unique_for_all_characters(self):
        history = [{"role": "user", "content": "오늘 회사 발표에서 실수했어."}]
        answers = [
            enforce_dialogue_policy(
                name,
                "상사한테 뭐라고 말하면 좋을까?",
                "관련 없는 임시 답변",
                has_history=True,
                history=history,
            )
            for name in sorted(self.profile_names)
        ]
        self.assertEqual(len(answers), len(set(answers)))
        self.assertTrue(all("발표" in answer and "내일" in answer for answer in answers))

    def test_relationship_turn_requires_grounded_answer(self):
        guidance = build_turn_guidance("강해상이라고 알아?")
        self.assertIn("확인된 정보", guidance)

    def test_trust_judgment_rejects_single_body_language_cue(self):
        guidance = build_turn_guidance("처음 만난 사람을 믿어도 되는지 어떻게 판단해?")
        self.assertIn("눈빛", guidance)
        self.assertIn("단정하지 않는다", guidance)
        self.assertIn("말과 행동", guidance)

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

    def test_prop_label_question_is_not_misclassified_as_enemy_relation(self):
        self.assertFalse(is_character_relation_question(
            "내 신발 밑에 적힌 이름이 뭐야?"
        ))

    def test_past_experience_with_character_requires_grounding(self):
        self.assertTrue(is_character_relation_question(
            "토니 스타크와 예전에 무슨 일이 있었어?"
        ))

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

    def test_targeted_distinctiveness_fallbacks_are_complete_and_different(self):
        decision = enforce_dialogue_policy(
            "할리 퀸", "중요한 결정을 앞두면 가장 먼저 무엇부터 생각해?", "모르겠네."
        )
        self.assertIn("결과", decision)
        maseokdo = enforce_dialogue_policy(
            "마석도", "중요한 결정을 앞두면 가장 먼저 무엇부터 생각해?", "내 손에 남는 걸 봐."
        )
        self.assertIn("피해", maseokdo)
        self.assertIn("책임", maseokdo)
        self.assertNotIn("내 손에", maseokdo)
        wonder = enforce_dialogue_policy(
            "원더우먼", "처음 만난 사람을 믿어도 되는지 너는 어떻게 판단해?", "초안"
        )
        elsa = enforce_dialogue_policy(
            "엘사", "처음 만난 사람을 믿어도 되는지 너는 어떻게 판단해?", "초안"
        )
        self.assertNotEqual(wonder, elsa)
        self.assertIn("진실", wonder)
        self.assertIn("안전", elsa)

    def test_generated_dialogue_typo_and_length_are_normalized(self):
        typo = enforce_dialogue_policy(
            "닥터 스트레인지", "중요한 판단에서 무엇을 봐?", "감정적인 동요은 판단을 흐립니다."
        )
        self.assertIn("동요는", typo)
        typos = enforce_dialogue_policy(
            "잭 스패로우",
            "오늘은 뭘 하지?",
            "육지의 관료들이나나 쓰는 말이지. 발 밑을 보며 일이 어찌될지 생각해.",
        )
        self.assertNotIn("이나나", typos)
        self.assertIn("발밑", typos)
        self.assertIn("어찌 될지", typos)
        long_answer = "첫 문장입니다. " + ("아주 긴 두 번째 문장 " * 30) + "."
        shortened = enforce_dialogue_policy("알버스 덤블도어", "사람을 어떻게 믿나요?", long_answer)
        self.assertLessEqual(len(shortened), 220)

    def test_gollum_targeted_answers_are_complete(self):
        decision = enforce_dialogue_policy(
            "골룸", "중요한 결정을 앞두면 가장 먼저 무엇부터 생각해?", "나는..."
        )
        rest = enforce_dialogue_policy(
            "골룸", "아무 일정도 없는 하루가 생기면 어떻게 보내고 싶어?", "아니..."
        )
        self.assertFalse(decision.endswith("..."))
        self.assertFalse(rest.endswith("..."))
        self.assertIn("잃게 될", decision)
        self.assertIn("숨어서", rest)

    def test_belonging_boundary_request_returns_usable_words(self):
        answer = enforce_dialogue_policy(
            "헤르미온느",
            "친구가 내 물건을 자꾸 말없이 가져가. 기분 안 상하게 뭐라고 보내면 좋을까?",
            "평소와 달라 보여요.",
        )
        self.assertRegex(answer, r"허락|먼저|물어")

    def test_history_secret_followup_returns_usable_words(self):
        history = [{"role": "user", "content": "친구가 내 비밀을 다른 사람에게 말했어."}]
        answer = enforce_dialogue_policy(
            "토니 스타크",
            "그럼 너라면 지금 뭐라고 답할 거야?",
            "내 카드를 보여주겠다고 해.",
            has_history=True,
            history=history,
        )
        self.assertRegex(answer, r"비밀|믿고|신뢰")
        self.assertNotIn("카드", answer)

    def test_practical_fallbacks_are_unique_for_all_characters(self):
        scenarios = (
            (
                [{"role": "user", "content": "친구가 내 비밀을 다른 사람에게 말했어."}],
                "관계를 끊기 전에 뭐라고 보내는 게 좋을까?",
            ),
            (
                [{"role": "user", "content": "친구가 내 물건을 허락 없이 가져갔어."}],
                "싸우지 않고 선을 긋고 싶은데 뭐라고 말할까?",
            ),
        )
        for history, message in scenarios:
            answers = {
                enforce_dialogue_policy(
                    name, message, "쓸 수 없는 임시 답변", has_history=True, history=history
                )
                for name in self.profile_names
            }
            self.assertEqual(len(self.profile_names), len(answers))

    def test_informal_secret_typo_returns_grounded_wording(self):
        answer = enforce_dialogue_policy(
            "토니 스타크",
            "친구가 내 비밀 퍼트림; 지금 머라보내는게 나음?",
            '"네가 말한 게 사실이라서 놀랐어."라고 보내.',
        )
        self.assertRegex(answer, r"비밀|신뢰|믿고|동의")
        self.assertNotIn("네가 말한 게 사실", answer)

    def test_informal_failure_shorthand_uses_specific_recovery(self):
        answer = enforce_dialogue_policy("피터 파커", "나 망함", "무슨 일이든 해결 방법은 꼭 있을 거야.")
        self.assertIn("무슨 일", answer)
        self.assertNotIn("해결 방법은 꼭", answer)

    def test_inadequate_property_wording_is_replaced(self):
        answer = enforce_dialogue_policy(
            "헤르미온느",
            "칭구가 내물건 말업이 또가져감... 머라 보내?",
            '"내 물건 다시 돌려줘"라고 보내세요.',
        )
        self.assertRegex(answer, r"허락|먼저\s*물어|다음부터|말없이")

    def test_compact_character_name_is_detected(self):
        profiles = {"characters": {"토니 스타크": {}, "피터 파커": {}}}
        self.assertEqual(["피터 파커"], mentioned_characters("피터파커랑무슨사이임?", profiles))

    def test_repeated_boundary_does_not_prove_intent(self):
        answer = enforce_dialogue_policy(
            "브루스 웨인",
            "근데 걔가 또 그랬어",
            "반복되는 행동은 실수가 아니라 의도야.",
            has_history=True,
            history=[{"role": "user", "content": "친구가 허락 없이 내 물건을 가져갔어."}],
        )
        self.assertIn("단정할 수 없어", answer)
        self.assertNotIn("실수가 아니라 의도", answer)

        variant = enforce_dialogue_policy(
            "브루스 웨인",
            "근데 걔가 또 그랬어",
            "반복되는 행동은 실수가 아니야. 확실하게 선을 그어.",
            has_history=True,
            history=[{"role": "user", "content": "친구가 허락 없이 내 물건을 가져갔어."}],
        )
        self.assertIn("단정할 수 없어", variant)

        simple_variant = enforce_dialogue_policy(
            "브루스 웨인",
            "근데 걔가 또 그랬어",
            "반복되는 행동은 단순한 실수가 아냐. 확실하게 선을 그어야 해.",
            has_history=True,
            history=[{"role": "user", "content": "친구가 허락 없이 내 물건을 가져갔어."}],
        )
        self.assertIn("단정할 수 없어", simple_variant)

        inserted_variant = enforce_dialogue_policy(
            "브루스 웨인",
            "근데 걔가 또 그랬어",
            "반복되는 행동은 실수가 아니라 습관이자 의도야. 선을 그어야 해.",
            has_history=True,
            history=[{"role": "user", "content": "친구가 허락 없이 내 물건을 가져갔어."}],
        )
        self.assertIn("단정할 수 없어", inserted_variant)
        self.assertNotIn("습관이자 의도", inserted_variant)

    def test_presentation_opportunity_motive_is_not_invented(self):
        answer = enforce_dialogue_policy(
            "스티브 로저스",
            "아니 면접 말고 발표였어. 내일 다시 해야돼",
            "다시 기회가 생겼다는 건 당신의 이야기가 필요하다는 뜻이에요.",
            has_history=True,
            history=[{"role": "user", "content": "오늘 면접을 망쳤어."}],
        )
        self.assertIn("이유까지 단정할 수는 없", answer)
        self.assertNotIn("이야기가 필요", answer)

        variant = enforce_dialogue_policy(
            "스티브 로저스",
            "아니 면접 말고 발표였어. 내일 다시 해야돼",
            "내일 다시 기회가 있다는 건 당신의 이야기를 들을 기회가 남아있다는 뜻입니다.",
            has_history=True,
            history=[{"role": "user", "content": "오늘 면접을 망쳤어."}],
        )
        self.assertIn("이유까지 단정할 수는 없", variant)

    def test_mind_reading_and_contempt_are_not_invented(self):
        answer = enforce_dialogue_policy(
            "고니",
            "친구가 비밀 까발리고 태연한데 개빡쳐",
            "그 사람이 네 속을 다 읽고도 태연한 건 너를 만만하게 본다는 소리야.",
        )
        self.assertRegex(answer, r"추측|단정|확인|근거")
        self.assertNotIn("만만하게", answer)

    def test_hostile_reference_is_neutralized(self):
        answer = enforce_dialogue_policy(
            "마석도",
            "친구가 별일 아니라는 듯 행동해서 더 화가 나.",
            "그 새끼가 대체 뭐라고 했는데? 그놈을 믿지 마.",
            has_history=True,
            history=[{"role": "user", "content": "친구가 내 비밀을 퍼뜨렸어."}],
        )
        self.assertNotRegex(answer, r"새끼|그놈")
        self.assertIn("그 사람이", answer)

    def test_presentation_followup_returns_usable_words(self):
        history = [{"role": "user", "content": "오늘 회사 발표를 망쳤어."}]
        answer = enforce_dialogue_policy(
            "토니 스타크",
            "상사한테 뭐라고 말하면 좋을까?",
            "아이언맨 슈트의 결함이라고 말해.",
            has_history=True,
            history=history,
        )
        self.assertIn("발표의 문제를 확인했습니다", answer)
        self.assertIn("내일", answer)
        self.assertNotIn("아이언맨", answer)

    def test_presentation_followup_preserves_representative_character_voices(self):
        history = [{"role": "user", "content": "오늘 회사 발표에서 실수했어."}]
        answers = [
            enforce_dialogue_policy(
                character,
                "상사한테 뭐라고 말하면 좋을까?",
                "임시 답변",
                has_history=True,
                history=history,
            )
            for character in ("마석도", "토니 스타크", "헤르미온느", "골룸", "엘사")
        ]
        self.assertEqual(5, len(set(answers)))
        self.assertTrue(all("발표" in answer and "내일" in answer for answer in answers))

    def test_listen_only_preserves_representative_character_voices(self):
        answers = [
            enforce_dialogue_policy(
                character,
                "해결책보다 그냥 내 얘기 좀 들어줘.",
                "임시 답변",
            )
            for character in ("마석도", "토니 스타크", "헤르미온느", "골룸", "엘사")
        ]
        self.assertEqual(5, len(set(answers)))
        self.assertTrue(all("?" not in answer for answer in answers))

    def test_emotional_followup_limits_rhetorical_questions(self):
        answer = enforce_dialogue_policy(
            "골룸",
            "상사가 내일 다시 얘기하자고 해서 불안해.",
            "그 사람이 말한 거구나? 그래서 마음이 떨리는 거야?",
            has_history=True,
            history=[{"role": "user", "content": "오늘 회사 발표에서 실수했어."}],
        )
        self.assertEqual(1, answer.count("?"))
        self.assertIn("그 사람이 말한 거구나.", answer)

    def test_safe_generated_listening_reply_is_not_flattened(self):
        answer = enforce_dialogue_policy(
            "데드풀",
            "조언 말고 일단 들어줘.",
            "오늘은 농담도 접어둘게. 네 얘기부터 들을게.",
        )
        self.assertEqual("오늘은 농담도 접어둘게. 네 얘기부터 들을게.", answer)

    def test_history_emotion_does_not_fall_back_to_reasking_context(self):
        answer = enforce_dialogue_policy(
            "피터 파커",
            "그 회사에서 내일 통화하자는데 또 망칠까 봐 불안해.",
            "면접에 이어 내일 통화까지 있으니 긴장될 만해. 어떤 부분이 걱정돼?",
            has_history=True,
            history=[{"role": "user", "content": "오늘 면접에서 말을 못했어."}],
        )
        self.assertIn("내일 통화", answer)
        self.assertNotIn("무슨 일 있었어", answer)

    def test_grounded_generated_wording_is_not_replaced(self):
        answer = enforce_dialogue_policy(
            "스티브 로저스",
            "전화 받으면 첫마디를 어떻게 하면 좋을까?",
            "안녕하세요, 어제 면접에 이어 연락 주셔서 감사합니다.",
            has_history=True,
            history=[{"role": "user", "content": "회사에서 내일 통화하자고 했어."}],
        )
        self.assertEqual("안녕하세요, 어제 면접에 이어 연락 주셔서 감사합니다.", answer)

    def test_unquoted_instruction_is_replaced_with_actual_wording(self):
        answer = enforce_dialogue_policy(
            "이순신",
            "싸우지 않고 선을 긋고 싶은데 뭐라고 말할까?",
            "상대에게 불편함을 분명히 전달해라. 이렇게 말해 보아라.",
            has_history=True,
            history=[{"role": "user", "content": "친구가 내 물건을 허락 없이 가져갔어."}],
        )
        self.assertIn("“", answer)
        self.assertRegex(answer, r"허락|먼저|물어")

    def test_unclosed_generated_quote_is_repaired(self):
        answer = enforce_dialogue_policy(
            "원더우먼",
            "싸우지 않고 선을 긋고 싶은데 뭐라고 말할까?",
            "이렇게 말해 보세요. “내 물건을 허락 없이 가져가서 속상해.",
            has_history=True,
            history=[{"role": "user", "content": "친구가 내 물건을 가져갔어."}],
        )
        self.assertEqual(answer.count("“"), answer.count("”"))

    def test_unsafe_listening_metaphor_uses_character_fallback(self):
        answer = enforce_dialogue_policy(
            "데드풀",
            "판단하지 말고 내 얘기만 들어줘.",
            "내 몸이 잘려 나가는 것보다 짜릿하네. 입 닥치고 들어줄게.",
        )
        self.assertIn("과장도 접어둘게", answer)
        self.assertNotIn("잘려", answer)
        self.assertNotIn("입 닥", answer)

    def test_invented_boss_motive_is_not_preserved(self):
        answer = enforce_dialogue_policy(
            "할리 퀸",
            "상사가 내일 다시 얘기하자고 해서 불안해.",
            "그 상사는 일부러 네 기를 빼려고 작정한 거야.",
            has_history=True,
            history=[{"role": "user", "content": "오늘 발표에서 실수했어."}],
        )
        self.assertIn("의도인지는 아직 모르", answer)
        self.assertNotIn("작정", answer)

    def test_invented_friend_motive_is_not_preserved(self):
        answer = enforce_dialogue_policy(
            "고광렬",
            "친구는 별일 아니라는 듯 행동해서 더 화가 나.",
            "뻔히 알면서도 모르는 척하는 태도가 사람을 미치게 만드는 거야.",
            has_history=True,
            history=[{"role": "user", "content": "친구가 내 비밀을 퍼뜨렸어."}],
        )
        self.assertRegex(answer, r"알 수 없어|불분명|추측|확인|근거|가정|정해")
        self.assertNotIn("뻔히 알면서", answer)

    def test_spaced_anger_limits_questions(self):
        answer = enforce_dialogue_policy(
            "네오",
            "친구가 태연하게 행동해서 더 화가 나.",
            "배신감을 외면하는 것 같아서 화가 나는 건가요? 일부러 그러는 것 같나요?",
            has_history=True,
            history=[{"role": "user", "content": "친구가 비밀을 퍼뜨렸어."}],
        )
        self.assertLessEqual(answer.count("?"), 1)

    def test_study_not_started_is_not_treated_as_wrong_answers(self):
        answer = enforce_dialogue_policy(
            "헤르미온느",
            "시험 공부가 하나도 안 됐어.",
            "어디서 틀렸는지 확인해요.",
        )
        self.assertIn("25분", answer)
        self.assertNotIn("틀렸", answer)

    def test_exam_anxiety_answers_known_context_instead_of_asking_again(self):
        answer = enforce_dialogue_policy(
            "헤르미온느",
            "시험을 망칠 것 같아서 불안해.",
            "평소와 달라 보여요. 무슨 일이 있었는지 말해 줄래요?",
        )

        self.assertIn("시험", answer)
        self.assertIn("불안한 범위", answer)
        self.assertNotIn("무슨 일이", answer)
        self.assertNotIn("틀렸", answer)

    def test_phone_first_words_are_usable_for_cold_character(self):
        answer = enforce_dialogue_policy(
            "장첸",
            "전화 받으면 첫마디를 어떻게 하면 좋을까?",
            "준비한 말이나 내뱉어.",
            has_history=True,
            history=[{"role": "user", "content": "어제 면접 본 회사에서 내일 통화하자고 했어."}],
        )

        self.assertIn("어제 면접 본 지원자", answer)
        self.assertIn("통화할 기회", answer)
        self.assertNotIn("내뱉어", answer)

    def test_invented_avoidance_motive_is_not_preserved(self):
        answer = enforce_dialogue_policy(
            "데드풀",
            "친구는 별일 아니라는 듯 행동해서 더 화가 나.",
            "그 사람은 그냥 상황을 회피하려고 발버둥 치는 중인 거야.",
            has_history=True,
            history=[{"role": "user", "content": "친구가 내 비밀을 다른 사람에게 말했어."}],
        )

        self.assertNotIn("회피하려고", answer)
        self.assertRegex(answer, r"단정|확인|추측|불분명|알 수")

    def test_relationship_cutoff_wording_is_replaced_with_boundary_message(self):
        answer = enforce_dialogue_policy(
            "데드풀",
            "관계를 끊기 전에 뭐라고 보내는 게 좋을까?",
            '"네 태도 때문에 더 이상 대화할 가치를 못 느끼겠어"라고 말해.',
            has_history=True,
            history=[{"role": "user", "content": "친구가 내 비밀을 다른 사람에게 말했어."}],
        )

        self.assertRegex(answer, r"신뢰|믿")
        self.assertNotIn("대화할 가치", answer)

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
            name: build_group_movie_reaction_fallback(name, "'레이디와 트램프', '엘리멘탈'")
            for name in ("데드풀", "엘사", "브루스 웨인")
        }
        self.assertEqual(len(set(replies.values())), 3)
        self.assertTrue(all("추천" in reply or "선택" in reply for reply in replies.values()))
        self.assertTrue(all("레이디와 트램프" in reply for reply in replies.values()))
        self.assertTrue(all("토니" not in reply for reply in replies.values()))


if __name__ == "__main__":
    unittest.main()
