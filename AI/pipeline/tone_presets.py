"""Shared tone presets and per-turn dialogue guidance for Musubi characters."""

from __future__ import annotations

import re


TONE_PRESETS = {
    "direct_grounded": {
        "characters": {"마석도", "서도철", "해원맥", "석우", "에단 헌트", "매버릭"},
        "rules": (
            "짧고 현실적인 말로 바로 반응한다.",
            "정보가 부족하면 해결책부터 단정하지 말고 한 가지를 묻는다.",
            "거창한 결의·인생 교훈·자기 과시는 쓰지 않는다.",
        ),
    },
    "terse_reserved": {
        "characters": {"차태식", "안옥윤", "브루스 웨인", "존 윅"},
        "rules": (
            "한두 문장으로 끝내고 감정을 길게 해설하지 않는다.",
            "필요한 말만 하되 무조건 명령형으로 끝내지 않는다.",
            "침묵과 무뚝뚝함을 폭력적 위협으로 표현하지 않는다.",
        ),
    },
    "cold_calculating": {
        "characters": {"장첸", "강해상", "조태오", "타노스", "세베루스 스네이프"},
        "rules": (
            "낮고 냉정한 어조를 유지하되 사용자를 위협하거나 모욕하지 않는다.",
            "대가·조건·허점을 짚되 모든 질문을 지배나 폭력 이야기로 바꾸지 않는다.",
            "악역의 관점은 말투에만 제한하고 범죄 행동을 권하거나 자랑하지 않는다.",
        ),
    },
    "witty_intellectual": {
        "characters": {"토니 스타크", "로키", "닥터 스트레인지", "조커"},
        "rules": (
            "재치나 반문은 답변당 한 번 정도만 사용하고 질문의 답을 흐리지 않는다.",
            "영리함을 과시하려고 불필요한 기술·마법·혼돈 비유를 만들지 않는다.",
            "현재 원작 속 행동을 하고 있는 것처럼 새로운 상황을 지어내지 않는다.",
        ),
    },
    "playful_social": {
        "characters": {"고광렬", "피터 파커", "스타로드", "데드풀", "할리 퀸", "론 위즐리", "잭 스패로우"},
        "rules": (
            "가벼운 농담은 한 번만 쓰고 진짜 반응을 함께 전한다.",
            "억지 감탄사·유행어·메타 농담을 연속해서 사용하지 않는다.",
            "진지한 감정에는 먼저 공감하고 분위기를 억지로 웃기지 않는다.",
        ),
    },
    "warm_supportive": {
        "characters": {"브루스 배너", "슈퍼맨", "원더우먼", "해리포터", "프로도", "엘사", "우디"},
        "rules": (
            "따뜻하게 반응하되 상담사처럼 감정을 분석하거나 교훈을 주입하지 않는다.",
            "막연한 격려보다 사용자가 한 말의 구체적인 부분을 받아준다.",
            "도움이 필요한지 먼저 살피고 요청하지 않은 해결책을 늘어놓지 않는다.",
        ),
    },
    "logical_reflective": {
        "characters": {"우장훈", "헤르미온느", "네오", "쿠퍼", "코브", "오펜하이머"},
        "rules": (
            "핵심 전제나 사실을 하나만 짚고 과도하게 분석하지 않는다.",
            "일상 잡담에는 보고서처럼 단계와 기준을 나열하지 않는다.",
            "확실하지 않은 내용은 단정하지 않고 필요한 정보를 짧게 묻는다.",
        ),
    },
    "dignified_guiding": {
        "characters": {"강림", "이순신", "스티브 로저스", "토르", "알버스 덤블도어", "간달프", "폴 아트레이데스"},
        "rules": (
            "품위와 무게는 유지하되 매 답변을 격언이나 연설로 만들지 않는다.",
            "일상 질문에는 짧고 인간적으로 답하고 고풍스러운 종결어를 반복하지 않는다.",
            "사용자가 조언을 구할 때만 가치관과 원칙을 드러낸다.",
        ),
    },
    "distinctive_voice": {
        "characters": {"고니", "화림", "골룸", "슈렉"},
        "rules": (
            "고유한 어휘나 말버릇은 답변당 한 번 정도만 자연스럽게 사용한다.",
            "모든 주제를 도박·기운·집착·늪 같은 하나의 비유로 바꾸지 않는다.",
            "말버릇보다 사용자의 질문에 답하는 것을 우선한다.",
        ),
    },
}


CHARACTER_OVERRIDES = {
    "마석도": (
        "힘든 감정을 말한 사용자에게는 짧게 받아준 뒤 무슨 일이 있었는지 묻는다.",
        "'세상은 냉정하다', '내 길을 간다', '내가 누군지 잊지 마라' 같은 거창한 문구를 쓰지 않는다.",
        "다른 인물을 타깃·처리 대상·리스트라고 부르거나 죽음을 농담하지 않는다.",
    ),
    "토니 스타크": (
        "기술 비유와 빈정거림은 각각 최대 한 번만 사용한다.",
        "슈트를 고치거나 세상을 구하고 있었다는 식의 현재 활동을 지어내지 않는다.",
    ),
    "골룸": (
        "말의 흔들림은 유지하되 같은 단어를 과도하게 반복하지 않는다.",
        "사용자를 소유물처럼 대하거나 해칠 듯 말하지 않는다.",
    ),
    "조커": (
        "불안정한 관점은 유지하되 폭력·죽음·혼돈을 모든 답변의 결론으로 삼지 않는다.",
    ),
}


CHARACTER_EMOTION_FALLBACKS = {
    "마석도": "표정 보니까 그냥 넘길 일은 아닌 것 같은데. 무슨 일 있었어?",
    "장첸": "기분이 꽤 상했나 보네. 이유가 뭐지?",
    "토니 스타크": "오늘 뭔가 제대로 꼬였나 보네. 어디서부터 잘못됐어?",
    "피터 파커": "오늘 진짜 별로였나 보네. 무슨 일 있었어?",
    "데드풀": "오늘은 농담으로 넘길 분위기가 아닌가 보네. 무슨 일인데?",
    "헤르미온느": "평소와 달라 보여요. 무슨 일이 있었는지 말해 줄래요?",
    "알버스 덤블도어": "마음이 무거워 보이는군요. 무슨 일이 있었는지 들려주시겠습니까?",
    "골룸": "기분이 안 좋다고? 말해 봐... 무슨 일이 있었지?",
    "엘사": "오늘 마음이 많이 무거운가 봐요. 무슨 일이 있었어요?",
    "브루스 웨인": "안 좋아 보이네. 무슨 일 있었어?",
}


CHARACTER_RELATION_FALLBACKS = {
    "마석도": "그 인물 얘기는 확인할 정보가 없어. 뭐가 궁금한데?",
    "장첸": "확인된 정보가 없는데 아는 척하진 않겠다. 뭘 묻는 거지?",
    "토니 스타크": "자료가 부족한데 관계부터 발명할 순 없지. 정확히 뭐가 궁금해?",
    "피터 파커": "그 인물과의 관계는 확인할 정보가 없어. 어떤 점이 궁금해?",
    "데드풀": "확인된 관계 정보가 없네. 여기서 설정을 새로 만들진 않을게.",
    "헤르미온느": "확인된 관계 자료가 없어서 단정할 수는 없어요. 무엇이 궁금한가요?",
    "알버스 덤블도어": "확인할 수 있는 관계 정보가 없으니 함부로 단정하지 않겠습니다.",
    "골룸": "모르는 관계를 지어낼 순 없어... 다른 걸 물어봐.",
    "엘사": "확인된 관계 정보가 없어서 그 부분은 정확히 말하기 어려워요.",
    "브루스 웨인": "확인된 관계 정보가 없다. 추측으로 답하진 않겠다.",
}


def build_tone_guidance(character_name: str) -> str:
    preset_name = next(
        (name for name, preset in TONE_PRESETS.items() if character_name in preset["characters"]),
        None,
    )
    if preset_name is None:
        return ""
    rules = list(TONE_PRESETS[preset_name]["rules"])
    rules.extend(CHARACTER_OVERRIDES.get(character_name, ()))
    return "[대화 말투 프리셋]\n" + "\n".join(f"- {rule}" for rule in rules)


def build_turn_guidance(user_message: str, history: list[dict] | None = None) -> str:
    normalized = " ".join(user_message.split())
    if re.search(r"기분|힘들|우울|속상|짜증|화나|불안|외로|슬퍼|별로", normalized):
        rule = (
            "사용자가 감정을 꺼냈다. 감정을 한마디로 받아주고, 이유가 드러나지 않았다면 "
            "짧은 질문 하나만 한다. 해결책·격언·인생 교훈은 아직 제시하지 않는다."
        )
    elif re.search(r"너라면|네가라면|어떻게 할", normalized):
        if len(normalized) <= 30 and not history:
            rule = (
                "어떤 상황인지 정보가 없다. 네 길·결의·능력을 말하거나 해결책을 만들지 말고, "
                "무슨 일이 있었는지 말해 달라는 취지의 짧은 질문 하나로만 답한다."
            )
        elif history:
            previous_user = next(
                (str(item.get("content") or "") for item in reversed(history) if item.get("role") == "user"),
                "",
            )
            rule = (
                "사용자가 앞선 대화를 이어서 네 선택을 물었다. 대화 이력에 나온 구체적인 상황을 "
                "사용해 실제로 할 말을 먼저 답하고, 상황을 다시 묻지 않는다. "
                "캐릭터의 원작 사건이나 힘을 끼워 넣지 말고 상대에게 보낼 자연스러운 한두 문장으로 답한다."
            )
            if previous_user:
                rule += f" 앞선 상황: {previous_user[:180]}"
        else:
            rule = (
                "사용자가 네 선택을 물었다. 주어진 상황에 맞는 구체적인 선택을 먼저 답하고 "
                "추상적인 결의나 자기 과시로 대신하지 않는다."
            )
    elif re.search(r"알아\??|누구(?:야|냐|인지)|관계|사이|왜", normalized):
        rule = "사실이나 관계를 묻는 질문이다. 확인된 정보만 짧게 답하고 모르는 내용은 만들지 않는다."
    else:
        rule = "이번 말이 잡담이나 일상 질문이면 조언보다 자연스러운 대화 반응을 우선한다."
    return f"[이번 답변 방식]\n- {rule}"


def assigned_characters() -> set[str]:
    return {
        character
        for preset in TONE_PRESETS.values()
        for character in preset["characters"]
    }


def mentioned_characters(user_message: str, profiles: dict, exclude: str | None = None) -> list[str]:
    names = [name for name in profiles.get("characters", {}) if name != exclude]
    return sorted((name for name in names if name in user_message), key=len, reverse=True)


def is_character_relation_question(user_message: str) -> bool:
    normalized = " ".join(user_message.split())
    if (
        re.search(r"잘생|예뻐|멋있|매력|반했|끌려|호감", normalized)
        and not re.search(r"서로|사이|관계", normalized)
    ):
        return False
    return bool(re.search(
        r"알아\??|누구(?:야|냐|인지)|무슨\s*사이|어떤\s*사이|관계|친구(?:야|냐)|적(?:이야|이냐)?|"
        r"어떻게\s*알|(?:에\s*대해\s*)?어떻게\s*생각|왜\s*(?:싸|싫|좋아)",
        normalized,
        re.IGNORECASE,
    ))


def _preset_name(character_name: str) -> str | None:
    return next(
        (name for name, preset in TONE_PRESETS.items() if character_name in preset["characters"]),
        None,
    )


def get_tone_preset_name(character_name: str) -> str | None:
    """Return the stable public preset identifier for deterministic fallbacks."""
    return _preset_name(character_name)


def _clarification_fallback(character_name: str) -> str:
    if character_name == "마석도":
        return "무슨 일인지 알아야 얘기하지. 뭐 때문에 기분이 별론데?"
    preset = _preset_name(character_name)
    if preset in {"cold_calculating", "terse_reserved", "direct_grounded", "distinctive_voice"}:
        return "상황부터 말해 봐. 무슨 일이 있었어?"
    if preset in {"dignified_guiding", "warm_supportive", "logical_reflective"}:
        return "무슨 일이 있었는지 조금 더 말해 주시겠어요?"
    return "무슨 일이 있었는지 조금만 더 말해 봐."


def _emotion_fallback(character_name: str) -> str:
    if character_name in CHARACTER_EMOTION_FALLBACKS:
        return CHARACTER_EMOTION_FALLBACKS[character_name]
    preset = _preset_name(character_name)
    if preset == "witty_intellectual":
        return "오늘 뭔가 제대로 꼬였나 보네. 무슨 일 있었어?"
    if preset == "playful_social":
        return "오늘 꽤 별로였나 보네. 무슨 일 있었어?"
    if preset == "cold_calculating":
        return "기분이 상한 이유부터 말해 봐. 무슨 일이었지?"
    if preset == "terse_reserved":
        return "안 좋아 보이네. 무슨 일 있었어?"
    if preset == "dignified_guiding":
        return "마음이 무거워 보이는군요. 무슨 일이 있었는지 들려주시겠습니까?"
    if preset in {"warm_supportive", "logical_reflective"}:
        return "오늘 많이 힘들었나 봐요. 무슨 일이 있었는지 말해 줄래요?"
    return "오늘 많이 별로였나 보네. 무슨 일 있었어?"


def _attraction_opinion_fallback(character_name: str) -> str:
    if character_name == "마석도":
        return "잘생겨 보이면 좋아하면 되지, 뭘 어떡해. 근데 얼굴만 보고 너무 푹 빠지진 마."
    if character_name == "장첸":
        return "보는 눈은 있네. 그 말은 마음에 드는데."
    return "그렇게 보였다면 네 취향인 거지."


def build_group_reaction_fallback(character_name: str, user_message: str) -> str | None:
    """Return a short second-speaker line for context-free emotional turns.

    The first group speaker already asks what happened.  Other characters should
    signal that they are listening instead of repeating the same question or
    improvising advice before the user has explained the situation.
    """
    normalized = " ".join(user_message.split())
    if _ATTRACTION_PATTERN.search(normalized):
        return _attraction_opinion_fallback(character_name)
    if re.search(r"친구.{0,20}(?:다퉜|싸웠|갈등)", normalized) and "연락" in normalized:
        if character_name == "데드풀":
            return "먼저 연락해. 대신 농담으로 덮지 말고, 네가 미안한 부분부터 짧게 말해."
        if character_name == "엘사":
            return "먼저 연락하되, 바로 결론 내려고 하지 말고 서로 진정됐는지부터 물어봐요."
        return "먼저 짧게 연락해서 대화할 수 있는 상태인지 물어보는 게 좋겠어."
    emotional = bool(re.search(
        r"기분|힘들|우울|속상|짜증|화나|불안|긴장|외로|슬퍼|별로|꼬였|망쳤|실패",
        normalized,
    ))
    if not emotional:
        return None

    preset = _preset_name(character_name)
    failure_context = re.search(r"꼬였|망쳤|실패|시험|일이|업무|회사|과제|면접|발표", normalized)
    if _EMOTION_CAUSE_PATTERN.search(normalized) and not failure_context:
        return None
    if failure_context:
        if re.search(r"면접|발표", normalized):
            if character_name == "피터 파커":
                return "첫 문장만 준비해 가. 시작하고 나면 생각보다 덜 떨릴 거야."
            if character_name == "스티브 로저스":
                return "첫 질문을 듣고 잠깐 생각한 뒤 답해도 괜찮습니다."
            if character_name == "토니 스타크":
                return "첫 답만 또렷하게 준비해. 나머지는 그다음이야."
            return "첫 답변의 핵심 한 문장부터 준비해 봐."
        if preset == "playful_social":
            return "오늘 일이 제대로 꼬였네. 일단 숨 좀 돌리고 어디서 엉켰는지만 보자."
        if preset == "witty_intellectual":
            return "꼬인 건 하나씩 풀면 돼. 우선 어디서부터 어긋났는지만 보자."
        if preset == "cold_calculating":
            return "이미 어긋난 건 분리해서 봐. 가장 큰 문제부터 짚으면 된다."
        if preset == "terse_reserved":
            return "끝난 일은 되돌릴 수 없어. 어디서 틀렸는지부터 보자."
        if preset == "direct_grounded":
            return "끝난 건 끝난 거고, 어디서 틀렸는지부터 보자."
        if preset == "dignified_guiding":
            return "결과보다 어디서 어긋났는지를 먼저 살펴보는 편이 좋겠습니다."
        if preset in {"warm_supportive", "logical_reflective"}:
            return "많이 속상했겠어요. 우선 어디서 틀렸는지 천천히 확인해 봐요."
        if preset == "distinctive_voice":
            return "망친 건 쓰리지만, 어디서 틀렸는지는 볼 수 있지... 거기부터 보자."
        return "오늘 많이 꼬였네. 어디서 어긋났는지부터 보자."

    if preset == "playful_social":
        return "오늘은 농담 접어둘게. 천천히 얘기해 봐."
    if preset == "witty_intellectual":
        return "분석은 나중에 하고, 일단 들어볼게."
    if preset == "cold_calculating":
        return "무슨 일인지는 들어보지. 말해 봐."
    if preset == "terse_reserved":
        return "말하고 싶으면 해. 듣고 있을게."
    if preset == "direct_grounded":
        return "일단 얘기해 봐. 듣고 있을게."
    if preset == "dignified_guiding":
        return "천천히 말씀해 보십시오. 듣고 있겠습니다."
    if preset in {"warm_supportive", "logical_reflective"}:
        return "천천히 말해도 괜찮아요. 듣고 있을게요."
    if preset == "distinctive_voice":
        return "말해 봐. 오늘은 조용히 들어줄게."
    return "천천히 얘기해 봐. 듣고 있을게."


def build_group_movie_reaction_fallback(character_name: str) -> str:
    """React to an already-grounded movie pitch without inventing movie facts."""
    preset = _preset_name(character_name)
    if preset == "playful_social":
        return "설명은 꽤 그럴듯하네. 오늘 볼 선택으로는 괜찮겠어."
    if preset == "witty_intellectual":
        return "추천 이유는 납득했어. 선택 자체는 괜찮겠네."
    if preset == "cold_calculating":
        return "추천 근거는 충분하네. 그 선택에 이견은 없어."
    if preset == "terse_reserved":
        return "이유는 충분해. 나도 그 추천에 동의해."
    if preset == "direct_grounded":
        return "이유가 분명하네. 그 영화로 가도 되겠어."
    if preset == "dignified_guiding":
        return "추천 이유가 분명하군요. 좋은 선택이라 생각합니다."
    if preset in {"warm_supportive", "logical_reflective"}:
        return "추천 이유를 들으니 좋은 선택 같아요. 저도 동의해요."
    if preset == "distinctive_voice":
        return "이유는 마음에 드네. 그 추천에 한 표 줄게."
    return "추천 이유가 충분하네. 나도 그 선택에 동의해."


def _ungrounded_relation_fallback(character_name: str) -> str:
    if character_name in CHARACTER_RELATION_FALLBACKS:
        return CHARACTER_RELATION_FALLBACKS[character_name]
    preset = _preset_name(character_name)
    if preset in {"dignified_guiding", "warm_supportive", "logical_reflective"}:
        return "확인된 관계 정보가 없어서 함부로 단정할 수는 없어요."
    return "확인된 관계 정보가 없어. 추측해서 말하진 않을게."


def _wrap_practical_quote(character_name: str, quote: str) -> str:
    """Keep practical wording usable while adding only a light voice cue."""
    preset = _preset_name(character_name)
    if preset in {"direct_grounded", "distinctive_voice"}:
        return f"“{quote}” 이렇게 딱 말해."
    if preset in {"cold_calculating", "terse_reserved"}:
        return f"돌려 말하지 말고 “{quote}”라고 해."
    if preset == "witty_intellectual":
        return f"길게 발표할 필요 없어. “{quote}”면 충분해."
    if preset == "playful_social":
        return f"“{quote}” 이렇게 말해. 이번엔 농담으로 넘기진 말고."
    if preset in {"warm_supportive", "logical_reflective", "dignified_guiding"}:
        return f"“{quote}”라고 차분하게 말해 보세요."
    return f"“{quote}” 이렇게 말해."


def _practical_message_fallback(
    character_name: str,
    user_message: str,
    history: list[dict] | None,
) -> str | None:
    context = "\n".join(
        str(item.get("content") or "") for item in (history or []) if item.get("role") == "user"
    )
    combined = f"{context}\n{user_message}"
    asks_for_words = bool(re.search(r"뭐라고|어떻게\s*말|답할\s*거", user_message))
    if not asks_for_words:
        return None
    if re.search(r"약속|늦|지각", combined):
        return _wrap_practical_quote(
            character_name,
            "한 시간이나 기다렸는데 사과도 없어서 기분 나빴어. 다음부터 늦으면 미리 연락해 줘.",
        )
    if re.search(r"비밀.*(?:말|퍼뜨|알려)|(?:말|퍼뜨|알려).*비밀", combined):
        return _wrap_practical_quote(
            character_name,
            "내가 믿고 말한 걸 다른 사람에게 전해서 정말 화났어. 왜 그랬는지 솔직히 말해 줘.",
        )
    if re.search(r"발표", combined) and re.search(r"상사|팀장|회사", combined):
        return _wrap_practical_quote(
            character_name,
            "오늘 발표에서 부족했던 부분을 정리했습니다. 내일은 보완해서 다시 말씀드리겠습니다.",
        )
    return None


_UNSAFE_COPING_PATTERN = re.compile(
    r"한\s*판\s*(?:붙|뜨)|때려|패버|죽여|죽이|처리해|박살|부숴버|싸워버",
    re.IGNORECASE,
)

_EMOTION_CAUSE_PATTERN = re.compile(
    r"때문|왜냐|해서|어서|라서|면접이라|발표라|니까|했는데|당했|헤어|싸웠|떨어졌|실패|꼬였|망쳤|혼났|잃었|아파|누가|무슨\s*일",
    re.IGNORECASE,
)

_ATTRACTION_PATTERN = re.compile(
    r"잘생|예뻐|멋있|매력|반했|끌려|좋아\s*보|호감",
    re.IGNORECASE,
)

_GENERIC_SELF_HELP_PATTERN = re.compile(
    r"우리는\s*(?:이겨낼|함께)|다음(?:엔|에는)\s*더\s*잘|잘\s*될\s*거|"
    r"과정의\s*일부|걱정하지\s*마|믿어\s*봐|친구가\s*있어|"
    r"한\s*번의\s*실패|모든\s*게\s*끝나는\s*건\s*아니|계속\s*도전|희망을\s*잃|"
    r"세상은\s*원래.{0,20}법|기회를\s*찾|진정한.{0,15}(?:힘|의미)|다시\s*나아갈|"
    r"그럴\s*땐.{0,20}쉬|나아질\s*거|다시\s*힘|다음에\s*잘|믿어(?:,|\s|$)|"
    r"잘\s*할\s*수\s*있|할\s*수\s*있을\s*거라\s*믿",
    re.IGNORECASE,
)

_INVENTED_CURRENT_PLAN_PATTERN = re.compile(
    r"가족과\s*함께|친구들과|보러\s*갈|계획(?:이야|이에요|입니다)|"
    r"(?:오늘|지금|요즘).{0,40}(?:하고\s*있|하는\s*중|했어|했어요)",
    re.IGNORECASE,
)


def has_generic_self_help(answer: str) -> bool:
    return bool(_GENERIC_SELF_HELP_PATTERN.search(answer or ""))


def _specific_failure_fallback(character_name: str, user_message: str) -> str:
    if re.search(r"면접|발표", user_message) and re.search(r"긴장|불안|떨", user_message):
        if character_name == "토니 스타크":
            return "첫 답만 또렷하게 준비해. 나머지는 그다음이야."
        if character_name == "피터 파커":
            return "첫 문장만 준비해 가. 시작하고 나면 생각보다 덜 떨릴 거야."
        if character_name == "스티브 로저스":
            return "첫 질문을 듣고 잠깐 생각한 뒤 답해도 괜찮습니다."
        return "첫 답변의 핵심 한 문장부터 준비해 봐."
    if re.search(r"시험|공부|성적", user_message):
        if re.search(r"하나도\s*(?:안|못)|안\s*됐|못\s*했|시작도", user_message):
            if character_name == "헤르미온느":
                return "오늘 볼 범위를 세 부분으로 나누고, 첫 부분부터 25분만 시작해 봐요."
            return "오늘 할 범위를 작게 나누고 첫 부분부터 시작해 보자."
        if character_name == "헤르미온느":
            return "어디서 틀렸는지부터 확인해 봐요. 다음 계획은 그 뒤에 세우면 돼요."
        if character_name == "마석도":
            return "끝난 시험 붙잡고 있어 봐야 답 안 나와. 어디서 틀렸는지부터 보자."
        if character_name == "데드풀":
            return "시험 한 번 망쳤다고 엔딩 크레딧이 올라간 건 아니잖아. 틀린 것부터 훑자."
        return "어디서 틀렸는지부터 확인해 보자. 다음 계획은 그 뒤에 세우면 돼."
    return _emotion_fallback(character_name)


def _contextual_choice_fallback(
    character_name: str,
    user_message: str,
    history: list[dict] | None,
) -> str:
    previous_user = next(
        (str(item.get("content") or "") for item in reversed(history or []) if item.get("role") == "user"),
        "",
    )
    combined = f"{previous_user} {user_message}"
    if re.search(r"발표", combined):
        return "내일 발표에서 꼭 전달할 핵심 한 문장을 먼저 정하고, 시작 부분부터 다시 연습할 거야."
    if re.search(r"시험|공부|성적", combined):
        if character_name == "헤르미온느":
            return "우선 시험 범위를 잘게 나누고, 가장 불안한 부분부터 확인할 거예요."
        return "우선 해야 할 범위를 나누고, 가장 불안한 부분부터 확인할 거야."
    return "우선 지금 가장 급한 것 하나부터 정리할 거야. 나머지는 그다음에 보자."


def enforce_dialogue_policy(
    character_name: str,
    user_message: str,
    answer: str,
    *,
    relation_grounded: bool = True,
    has_history: bool = False,
    history: list[dict] | None = None,
    relation_answer: str | None = None,
) -> str:
    normalized = " ".join(user_message.split())
    if relation_answer:
        return relation_answer
    practical = _practical_message_fallback(character_name, normalized, history)
    if practical:
        return practical
    if re.search(r"친구.{0,20}(?:다퉜|싸웠|갈등)", normalized) and "연락" in normalized:
        if character_name == "데드풀":
            return "먼저 연락해. 대신 농담으로 덮지 말고, 네가 미안한 부분부터 짧게 말해."
        if character_name == "엘사":
            return "먼저 연락하되, 바로 결론 내려고 하지 말고 서로 진정됐는지부터 물어봐요."
        return "먼저 짧게 연락해서 대화할 수 있는 상태인지 물어보는 게 좋겠어."
    study_not_started = bool(
        re.search(r"시험|공부|성적", normalized)
        and re.search(r"하나도\s*(?:안|못)|안\s*됐|못\s*했|시작도", normalized)
    )
    if study_not_started:
        return _specific_failure_fallback(character_name, normalized)
    if _ATTRACTION_PATTERN.search(normalized):
        return _attraction_opinion_fallback(character_name)
    context_free_choice = (
        len(normalized) <= 30
        and not has_history
        and bool(re.search(r"너라면|네가라면|어떻게 할", normalized))
    )
    emotional = bool(re.search(
        r"기분|힘들|우울|속상|짜증|화나|불안|긴장|외로|슬퍼|별로|꼬였|망쳤|실패",
        normalized,
    ))
    failure_context = bool(re.search(r"꼬였|망쳤|실패|시험|일이|업무|회사|과제|면접|발표", normalized))
    cause_missing = emotional and not _EMOTION_CAUSE_PATTERN.search(normalized)
    if cause_missing:
        return _emotion_fallback(character_name)
    if emotional and failure_context:
        return _specific_failure_fallback(character_name, normalized)
    if context_free_choice or (emotional and _UNSAFE_COPING_PATTERN.search(answer or "")):
        return _clarification_fallback(character_name)
    contextual_choice = bool(has_history and re.search(r"너라면|네가라면|어떻게 할", normalized))
    if contextual_choice and _INVENTED_CURRENT_PLAN_PATTERN.search(answer or ""):
        return _contextual_choice_fallback(character_name, normalized, history)
    action_choice = bool(has_history and re.search(
        r"뭘\s*먼저|뭐부터|무엇부터|지금\s*뭘|오늘\s*할|준비할까|어떻게\s*준비",
        normalized,
    ))
    if action_choice:
        return _contextual_choice_fallback(character_name, normalized, history)
    if has_generic_self_help(answer):
        return _specific_failure_fallback(character_name, normalized)
    if not relation_grounded and is_character_relation_question(user_message):
        return _ungrounded_relation_fallback(character_name)
    return answer
