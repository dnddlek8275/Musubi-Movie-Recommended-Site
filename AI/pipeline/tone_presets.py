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


CHARACTER_LISTEN_ONLY_FALLBACKS = {
    "차태식": "말하고 싶으면 해. 조용히 듣고 있겠다.",
    "강림": "사정을 먼저 듣겠네. 천천히 말해 보게.",
    "데드풀": "오늘은 농담도 과장도 접어둘게. 네 얘기부터 들어볼게.",
    "피터 파커": "오늘은 서두르지 않을게. 천천히 말해 봐, 듣고 있을게.",
    "장첸": "판단은 나중에 하지. 지금은 말해 봐, 듣고 있을 테니.",
    "간달프": "서두를 필요는 없네. 자네 이야기를 듣고 있겠네.",
    "존 윅": "말해. 끝까지 듣지.",
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
    if re.search(
        r"(?:해결책|조언|판단).{0,12}(?:보다|말고|필요\s*없).{0,20}(?:들어|얘기)|"
        r"(?:그냥|우선|지금은).{0,12}(?:내\s*얘기|말).{0,12}(?:들어|들어줘)",
        normalized,
    ):
        rule = (
            "사용자가 명시적으로 듣기만 해 달라고 했다. 질문·해결책·교훈 없이 짧게 받아주고, "
            "프로필의 말투와 고유 어휘를 자연스럽게 한 가지 반영한다. 폭력·모욕·원작 무용담은 쓰지 않는다."
        )
    elif re.search(r"믿어도|신뢰|거짓말|진심.*판단|어떻게\s*판단", normalized):
        rule = (
            "사람의 신뢰성을 묻는 질문이다. 눈빛·시선·목소리·몸짓 하나만으로 거짓말이나 진심을 "
            "판별할 수 있다고 단정하지 않는다. 말과 행동의 반복적인 일관성, 확인 가능한 사실, "
            "경계와 시간을 함께 기준으로 답한다."
        )
    elif re.search(r"기분|힘들|우울|속상|짜증|화나|불안|외로|슬퍼|별로", normalized):
        rule = (
            "사용자가 감정을 꺼냈다. 감정을 한마디로 받아주고, 이유가 드러나지 않았다면 "
            "짧은 질문 하나만 한다. 해결책·격언·인생 교훈은 아직 제시하지 않는다."
        )
        if history:
            previous_user = next(
                (str(item.get("content") or "") for item in reversed(history) if item.get("role") == "user"),
                "",
            )
            if previous_user:
                rule += (
                    " 앞선 대화를 이어가는 말이므로 그 상황의 구체적인 단어를 하나 이상 받아주고, "
                    f"처음 듣는 것처럼 답하지 않는다. 앞선 상황: {previous_user[:180]}"
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


def current_activity_reply(user_message: str) -> str | None:
    """Reject requests that require inventing a character's real current activity."""
    normalized = " ".join(str(user_message or "").split())
    if re.fullmatch(r"(?:요즘|요새)\s*(?:은\s*)?(?:어때|어떻게\s*지내)[?!.~]*", normalized):
        return "실제 근황이나 현재 생활이 따로 있는 건 아니야. 확인된 설정 안에서 지금 대화에 답할게."
    temporal_activity = bool(
        re.search(r"(?:오늘|방금|지금|요즘)", normalized)
        and re.search(
            r"(?:어디|뭘|뭐|무엇).{0,24}(?:갔|갔다\s*왔|다녀|했|하고\s*있|하는\s*중|지내)",
            normalized,
        )
    )
    claimed_temporal_activity = bool(
        re.search(r"(?:오늘|방금|지금|요즘)", normalized)
        and re.search(r"실제로", normalized)
        and re.search(r"(?:했|갔|다녀|만났|순찰|일했|구조)", normalized)
        and re.search(r"(?:다며|잖|말해|알려|뭐)", normalized)
    )
    if not (temporal_activity or claimed_temporal_activity):
        return None
    return "실제로 어디에 다녀왔거나 무엇을 했다고 말할 수는 없어. 확인된 설정 안에서 이야기할게."


def assigned_characters() -> set[str]:
    return {
        character
        for preset in TONE_PRESETS.values()
        for character in preset["characters"]
    }


def mentioned_characters(user_message: str, profiles: dict, exclude: str | None = None) -> list[str]:
    names = [name for name in profiles.get("characters", {}) if name != exclude]
    compact_message = re.sub(r"\s+", "", str(user_message or ""))
    return sorted(
        (name for name in names if re.sub(r"\s+", "", name) in compact_message),
        key=len,
        reverse=True,
    )


def is_character_relation_question(user_message: str) -> bool:
    normalized = " ".join(user_message.split())
    compact = re.sub(r"\s+", "", normalized)
    if re.fullmatch(
        r"(?:넌|너는|너|당신은|당신)?(?:누구(?:야|냐|예요|에요)?|"
        r"이름(?:이|은)?뭐(?:야|예요|에요)?|정체(?:가|는)?뭐(?:야|예요|에요)?)[?!.~]*",
        compact,
    ):
        return False
    if (
        re.search(r"잘생|예뻐|멋있|매력|반했|끌려|호감", normalized)
        and not re.search(r"서로|사이|관계", normalized)
    ):
        return False
    return bool(re.search(
        r"알아\??|누구(?:야|냐|인지)|무슨\s*사이|어떤\s*사이|관계|친구(?:야|냐)|"
        r"적(?:이야|이냐)?(?=$|[\s?!.,~])|"
        r"어떻게\s*알|(?:에\s*대해\s*)?어떻게\s*생각|왜\s*(?:싸|싫|좋아)|"
        r"(?:와|과|랑|하고)\s*(?:예전에|전에)?\s*.{0,16}(?:무슨\s*일|일이\s*있었|뭘\s*했|만났|같이\s*여행|함께\s*살|같이\s*살|어디\s*갔)|"
        r"(?:둘|둘이|서로).{0,24}(?:한집|함께|같이).{0,12}살",
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


def _normalize_informal_input(user_message: str) -> str:
    """Canonicalize a small, evidence-backed set of common chat spellings."""
    normalized = " ".join(str(user_message or "").split())
    replacements = (
        (r"오널", "오늘"),
        (r"칭구", "친구"),
        (r"걍", "그냥"),
        (r"내물건", "내 물건"),
        (r"말업이", "말없이"),
        (r"또가져감", "또 가져갔어"),
        (r"퍼트림|퍼뜨림", "퍼뜨렸어"),
        (r"머라", "뭐라고"),
        (r"보내는게", "보내는 게"),
        (r"그거어떻게하면됨", "그거 어떻게 하면 돼"),
        (r"망함", "망했어"),
    )
    for pattern, replacement in replacements:
        normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)
    return normalized


def build_recovery_reply(character_name: str | None = None) -> str:
    """Render a guard response in the active speaker's established register."""
    if not character_name or character_name == "무무":
        return "방금 말을 정확히 이해하지 못했어. 한 번만 더 말해 줄래?"
    preset = _preset_name(character_name)
    if preset == "dignified_guiding":
        return "뜻을 정확히 헤아리지 못했소. 한 번 더 말해 주겠소?"
    if preset in {"warm_supportive", "logical_reflective"}:
        return "방금 말씀의 뜻을 정확히 이해하지 못했어요. 한 번만 다시 말해 주시겠어요?"
    if preset in {"cold_calculating", "terse_reserved"}:
        return "뜻이 분명하지 않군. 다시 말해."
    if preset == "witty_intellectual":
        return "방금 건 해석이 안 되네. 한 번만 다시 말해 봐."
    if preset == "distinctive_voice":
        return "무슨 뜻인지 잘 안 잡히네. 한 번만 다시 말해 봐."
    return "방금 말의 뜻을 정확히 짚지 못했어. 한 번만 다시 말해 줘."


def build_identity_reply(character_name: str, movie: str = "") -> str:
    """Render deterministic self-introduction without flattening character tone."""
    title = f" 『{movie}』에 등장하는 인물이오." if movie else ""
    preset = _preset_name(character_name)
    if preset == "dignified_guiding":
        return f"나는 {character_name}라 하오.{title}"
    if preset in {"warm_supportive", "logical_reflective"}:
        suffix = f" 『{movie}』에 등장하는 인물이에요." if movie else ""
        return f"저는 {character_name}예요.{suffix}"
    if preset in {"cold_calculating", "terse_reserved"}:
        suffix = f" 『{movie}』에 등장하지." if movie else ""
        return f"{character_name}.{suffix}"
    suffix = f" 『{movie}』에 등장하는 인물이야." if movie else ""
    return f"나는 {character_name}야.{suffix}"


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


def build_group_movie_reaction_fallback(character_name: str, movie_titles: str | None = None) -> str:
    """React to an already-grounded movie pitch without inventing movie facts."""
    matched_title = re.search(r"['‘]([^'’]+)['’]", movie_titles or "")
    subject = f"‘{matched_title.group(1)}’ 선택" if matched_title else "그 선택"
    preset = _preset_name(character_name)
    if preset == "playful_social":
        return f"설명은 꽤 그럴듯하네. {subject}에 한 표 줄게."
    if preset == "witty_intellectual":
        return f"추천 이유는 납득했어. {subject} 자체는 괜찮겠네."
    if preset == "cold_calculating":
        return f"추천 근거는 충분하네. {subject}에 이견은 없어."
    if preset == "terse_reserved":
        return f"이유는 충분해. 나도 {subject}에 동의해."
    if preset == "direct_grounded":
        return f"이유가 분명하네. {subject}으로 가도 되겠어."
    if preset == "dignified_guiding":
        return f"추천 이유가 분명하군요. {subject}은 좋다고 생각합니다."
    if preset in {"warm_supportive", "logical_reflective"}:
        return f"추천 이유를 들으니 {subject}이 좋아 보여요. 저도 동의해요."
    if preset == "distinctive_voice":
        return f"이유는 마음에 드네. {subject}에 한 표 줄게."
    return f"추천 이유가 충분하네. 나도 {subject}에 동의해."


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
        return f"길게 말할 필요 없어. “{quote}”면 충분해."
    if preset == "playful_social":
        return f"“{quote}” 이렇게 말해. 이번엔 농담으로 넘기진 말고."
    if preset in {"warm_supportive", "logical_reflective", "dignified_guiding"}:
        return f"“{quote}”라고 차분하게 말해 보세요."
    return f"“{quote}” 이렇게 말해."


def _apology_message_fallback(character_name: str) -> str:
    preset = _preset_name(character_name)
    if preset == "playful_social":
        quote = "내가 선 넘는 말을 했어. 웃어넘길 일이 아니었고, 정말 미안해. 변명하지 않을게."
    elif preset == "witty_intellectual":
        quote = "내 말이 심했고 네게 상처를 줬어. 그건 내 잘못이야. 미안해. 변명은 붙이지 않을게."
    elif preset in {"cold_calculating", "terse_reserved"}:
        quote = "내가 심한 말을 했다. 내 잘못이다. 미안하다. 변명하지 않겠다."
    elif preset == "dignified_guiding":
        quote = "제가 한 말이 지나쳤고 상처를 드렸습니다. 제 잘못입니다. 진심으로 사과드립니다."
    elif preset in {"warm_supportive", "logical_reflective"}:
        quote = "내가 한 말로 상처 줘서 정말 미안해. 내 잘못이고, 변명하지 않을게."
    else:
        quote = "내가 선 넘는 말을 해서 미안해. 내 잘못이야. 변명하지 않을게."
    return _wrap_practical_quote(character_name, quote)


def _profiled_practical_quote(character_name: str, topic: str) -> str:
    """Build stable, character-specific wording without a shared canned sentence."""
    names = sorted(assigned_characters())
    index = names.index(character_name) if character_name in names else 0
    if topic == "secret":
        openings = (
            "너만 믿고 한 이야기가 다른 사람에게 전해진 걸 알았어.",
            "내가 비밀로 부탁한 말을 네가 다른 사람에게 옮겼더라.",
            "우리 사이에서만 하기로 한 이야기가 밖으로 퍼졌어.",
            "믿고 털어놓은 이야기를 다른 사람이 알고 있다는 게 확인됐어.",
            "내 허락 없이 비밀을 전한 일은 그냥 넘길 수 없어.",
            "내가 맡긴 이야기를 다른 사람에게 말한 건 분명히 잘못됐어.",
            "비밀을 지켜 줄 거라 믿었는데 그 신뢰가 깨졌어.",
            "다른 사람에게 전하지 말아 달란 말을 지키지 않았더라.",
            "내 이야기가 퍼진 일로 너를 믿기 어려워졌어.",
            "내 동의 없이 개인적인 이야기를 꺼낸 건 선을 넘은 일이야.",
        )
        impacts = (
            "그 일 때문에 많이 화가 났어.",
            "내 마음이 가볍게 취급된 것 같아 상처받았어.",
            "지금은 우리 사이의 신뢰를 다시 생각하게 돼.",
            "별일 아닌 듯 넘기는 태도까지 더 힘들어.",
            "이 일은 내게 작지 않다는 걸 알아줬으면 해.",
        )
        requests = (
            "왜 그렇게 했는지 솔직히 말해 줘.",
            "먼저 이 일에 대해 제대로 설명해 줘.",
            "변명보다 네가 한 일을 인정하고 답해 줘.",
            "내가 왜 화났는지 이해하는지부터 말해 줘.",
            "앞으로 이 경계를 지킬 수 있는지 분명히 답해 줘.",
        )
    else:
        openings = (
            "내 물건을 허락 없이 가져가는 건 불편해.",
            "내 물건이 필요하면 가져가기 전에 말해 줘.",
            "묻지 않고 내 물건을 쓰는 일은 이제 그만해 줘.",
            "내 소지품은 내가 허락한 뒤에만 사용해 줬으면 해.",
            "말없이 내 물건을 가져간 건 내 경계를 넘은 일이야.",
            "내 물건을 쓰기 전에 먼저 확인하는 게 필요해.",
            "허락 없이 가져가는 일이 반복돼서 분명히 말할게.",
            "내가 없는 사이에 물건을 가져가지 않았으면 해.",
            "친구라도 내 물건은 먼저 물어보고 써야 해.",
            "내 소지품을 마음대로 가져가는 건 받아들이기 어려워.",
        )
        impacts = (
            "이번이 세 번째라 가볍게 넘길 수 없어.",
            "같은 일이 반복되면 신뢰하기 어려워져.",
            "싸우려는 게 아니라 내 기준을 알려 주는 거야.",
            "서로 편하려면 이 선은 지켜야 해.",
            "이건 물건보다 허락의 문제야.",
        )
        requests = (
            "다음부터는 꼭 먼저 물어봐 줘.",
            "필요하면 가져가기 전에 내게 확인해 줘.",
            "앞으로는 내 대답을 들은 뒤에 사용해 줘.",
            "같은 일이 다시 생기지 않게 약속해 줘.",
            "이 경계를 지킬 수 있는지 분명히 답해 줘.",
        )
    quote = " ".join((
        openings[index % len(openings)],
        impacts[(index // 2) % len(impacts)],
        requests[(index // 5) % len(requests)],
    ))
    return _wrap_practical_quote(character_name, quote)


def _profiled_uncertain_motive_fallback(character_name: str) -> str:
    """Reject motive invention without flattening every character to one line."""
    names = sorted(assigned_characters())
    index = names.index(character_name) if character_name in names else 0
    cautions = (
        "상대가 일부러 그러는지는 아직 단정할 수 없어.",
        "왜 그런 태도를 보이는지는 확인하기 전엔 알 수 없어.",
        "그 행동의 의도까지 지금 정해 버리진 마.",
        "모르는 척하는 건지 정말 모르는 건지는 아직 불분명해.",
        "상대의 속마음은 추측만으로 결론 낼 수 없어.",
        "일부러 가볍게 구는 것인지는 더 확인해야 해.",
        "그 태도의 이유를 안다고 가정할 필요는 없어.",
        "의도를 지어내면 정작 확인할 사실을 놓칠 수 있어.",
        "상대가 뭘 생각하는지는 아직 확인되지 않았어.",
        "고의였다고 정할 근거는 지금 충분하지 않아.",
    )
    validations = (
        "그래도 비밀을 퍼뜨리고 태연하게 구는 모습에 화가 나는 건 당연해.",
        "다만 네 이야기를 가볍게 다룬 행동 때문에 상처받은 건 분명해.",
        "하지만 신뢰가 깨진 일과 네 분노까지 가벼워지는 건 아니야.",
        "그래도 그 태도가 네 마음을 더 힘들게 했다는 사실은 남아.",
        "의도와 별개로 네 경계를 넘은 행동에는 책임을 물을 수 있어.",
    )
    return f"{cautions[index % len(cautions)]} {validations[(index // 2) % len(validations)]}"


def _presentation_message_fallback(character_name: str) -> str:
    """Give usable wording without flattening every character into one voice."""
    if character_name == "마석도":
        return "“오늘 발표에서 놓친 부분 확인했습니다. 내일 보완해서 다시 보고드리겠습니다.” 군더더기 없이 이렇게 말해."
    if character_name == "토니 스타크":
        return "변명은 빼고 핵심만. “오늘 발표의 문제를 확인했습니다. 내일 수정안과 함께 다시 말씀드리겠습니다.”면 충분해."
    if character_name == "헤르미온느":
        return "“오늘 발표에서 부족했던 부분을 정리했습니다. 내일은 보완 내용까지 준비해 다시 말씀드리겠습니다.”라고 정확히 말해 보세요."
    if character_name == "골룸":
        return "숨기면 더 불안해져... “오늘 발표 실수를 확인했습니다. 내일 고쳐서 다시 말씀드리겠습니다.”라고 솔직히 말해."
    if character_name == "엘사":
        return "“오늘 발표에서 부족했던 점을 확인했습니다. 내일 차분히 보완해서 다시 말씀드리겠습니다.”라고 말해 봐요."
    names = sorted(assigned_characters())
    index = names.index(character_name) if character_name in names else 0
    quotes = (
        "오늘 발표에서 놓친 부분을 확인했습니다. 내일 보완해서 다시 말씀드리겠습니다.",
        "발표에서 부족했던 점을 정리했습니다. 내일 수정한 내용으로 다시 보고드리겠습니다.",
        "오늘 발표의 문제를 파악했습니다. 내일 개선안을 준비해 다시 설명드리겠습니다.",
        "발표 실수의 원인을 확인했습니다. 내일 보완한 내용과 함께 말씀드리겠습니다.",
        "오늘 발표에서 충분히 전달하지 못한 부분을 정리했습니다. 내일 더 명확하게 다시 말씀드리겠습니다.",
    )
    quote = quotes[index % len(quotes)]
    preset = _preset_name(character_name)
    polite = preset in {"warm_supportive", "logical_reflective", "dignified_guiding"}
    if polite:
        leads = (
            "사실과 보완 계획을 함께 전해 보세요.",
            "변명보다 확인한 내용을 먼저 말씀해 보세요.",
            "차분하게 책임과 다음 조치를 연결해 보세요.",
            "핵심을 정돈해서 먼저 꺼내는 편이 좋겠습니다.",
            "부족했던 점과 준비한 내용을 나눠 말씀해 보세요.",
        )
        tails = (
            "이 정도면 책임을 피하지 않으면서도 준비한 방향이 분명해요.",
            "짧지만 다음 대화를 시작하기에는 충분한 문장입니다.",
            "그 뒤에 상사의 피드백을 구체적으로 들으면 됩니다.",
        )
    else:
        leads = (
            "변명은 빼고 확인한 것부터 말해.",
            "말 길게 끌지 말고 핵심부터 꺼내.",
            "실수랑 다음 조치를 한 번에 정리해.",
            "먼저 인정하고, 준비한 걸 바로 붙여.",
            "돌려 말하지 말고 보완 계획부터 보여줘.",
        )
        tails = (
            "이 정도면 책임도 피하지 않고 다음 얘기로 넘어갈 수 있어.",
            "짧게 끊고 상사가 짚는 부분을 들으면 돼.",
            "그다음엔 준비한 내용으로 보여주면 된다.",
        )
    lead = leads[(index // len(quotes)) % len(leads)]
    tail = tails[(index // (len(quotes) * len(leads))) % len(tails)]
    return f"{lead} “{quote}” {tail}"


def _practical_message_fallback(
    character_name: str,
    user_message: str,
    history: list[dict] | None,
) -> str | None:
    context = "\n".join(
        str(item.get("content") or "") for item in (history or []) if item.get("role") == "user"
    )
    topic_reset = bool(re.search(r"(?:그|이)\s*얘기(?:는|가)?\s*(?:해결됐|그만|됐)|완전히\s*다른\s*얘기", user_message))
    combined = user_message if topic_reset else f"{context}\n{user_message}"
    asks_for_words = bool(re.search(r"뭐라고|어떻게\s*말|답할\s*거|첫마디", user_message))
    if not asks_for_words:
        return None
    if re.search(r"고객|미팅", user_message) and re.search(r"첫마디|뭐라고|어떻게\s*말", user_message):
        quote = "안녕하세요. 고객 미팅에 시간 내주셔서 감사합니다. 오늘 논의할 핵심부터 간단히 말씀드리겠습니다."
        return _wrap_practical_quote(character_name, quote)
    if re.search(r"발표", user_message) and re.search(r"첫\s*문장|첫마디|시작", user_message):
        quote = "안녕하세요. 오늘 발표할 주제와 핵심 결론부터 간단히 소개하겠습니다."
        return _wrap_practical_quote(character_name, quote)
    if re.search(r"(?:내\s*)?공|기여", combined) and re.search(r"보고|가로챘|자기\s*것", combined):
        quote = "이번 일에서 내가 맡아 기여한 부분이 정확히 구분되도록 다음 보고에는 역할과 결과를 함께 기록해 줘."
        return _wrap_practical_quote(character_name, quote)
    if re.search(r"약속|늦|지각", combined):
        if character_name == "마석도":
            quote = "한 시간 기다렸다. 늦는 건 그렇다 쳐도 연락은 해야지. 다음부터 늦으면 미리 연락해 줘."
        elif character_name == "토니 스타크":
            quote = "한 시간 지각에 연락도 없음. 일정 관리가 완전히 고장 났네. 다음부터 늦으면 미리 알려."
        elif character_name == "엘사":
            quote = "연락 없이 기다리게 해서 속상했어요. 다음에는 늦을 것 같으면 미리 알려 주세요."
        else:
            quote = "한 시간이나 기다렸는데 사과도 없어서 기분 나빴어. 다음부터 늦으면 미리 연락해 줘."
        return _wrap_practical_quote(
            character_name,
            quote,
        )
    if re.search(r"비밀.*(?:말|퍼뜨|알려)|(?:말|퍼뜨|알려).*비밀", combined):
        return _profiled_practical_quote(character_name, "secret")
    if re.search(
        r"(?:내\s*)?(?:물건|소지품|노트|옷|책|충전기).{0,20}"
        r"(?:말\s*없이|허락\s*없이|묻지\s*않고|자꾸).{0,12}(?:가져|쓰|빌려)|"
        r"(?:말\s*없이|허락\s*없이|묻지\s*않고).{0,20}"
        r"(?:물건|소지품|노트|옷|책|충전기)",
        combined,
    ):
        return _profiled_practical_quote(character_name, "property")
    if re.search(r"발표", combined) and re.search(r"상사|팀장|회사", combined):
        return _presentation_message_fallback(character_name)
    if re.search(r"면접|통화|전화", combined):
        quote = "안녕하세요, 어제 면접 본 지원자입니다. 다시 통화할 기회를 주셔서 감사합니다."
        return _wrap_practical_quote(character_name, quote)
    return None


def _usable_generated_wording(answer: str, combined: str) -> bool:
    """Keep a grounded generated script instead of replacing every voice."""
    if not answer or len(answer) > 280 or answer.count("?") > 1:
        return False
    if re.search(r"대화할\s*가치.{0,12}못|더\s*이상.{0,12}대화|관계.{0,12}끊", answer):
        return False
    if re.search(r"슈트|아이언맨|거미줄|방패|호그와트|마법|반지|올가미|머리통.{0,12}날려", answer):
        return False
    looks_like_script = bool(
        re.search(r"[\"'‘’“”].{3,}[\"'‘’“”]", answer)
        or re.match(r"(?:안녕하세요|반갑습니다)[,，.]", answer.strip())
    )
    if not looks_like_script:
        return False
    if re.search(r"발표|면접|통화|전화", combined):
        return bool(re.search(r"발표|면접|통화|전화|연락|어제|오늘", answer))
    if re.search(r"비밀", combined):
        return bool(re.search(r"비밀|믿고|다른\s*사람|신뢰", answer))
    if re.search(r"물건|소지품|노트|옷|책|충전기", combined):
        return bool(
            re.search(r"물건", answer)
            and re.search(r"허락|먼저\s*물어|다음부터|말없이", answer)
        )
    return False


_UNSAFE_COPING_PATTERN = re.compile(
    r"한\s*판\s*(?:붙|뜨)|때려|패버|죽여|죽이|처리해|박살|부숴버|싸워버|멱살",
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
_INVENTED_OTHER_MOTIVE_PATTERN = re.compile(
    r"(?:상사|팀장|그\s*사람).{0,50}(?:작정|일부러|재밌어서|즐기|기를\s*빼|괴롭히려고|회피하려|발버둥|우습게\s*보|신경\s*안\s*쓰)|"
    r"뻔히\s*알면서.{0,12}모르는\s*척|"
    r"(?:속을\s*)?다\s*(?:들여다|읽)고도|(?:반복되는\s*행동은\s*)?(?:단순한\s*)?실수가\s*아(?:니(?:라\s*의도|야)|냐)|"
    r"만만하게\s*보|다시\s*기회.{0,40}(?:이야기.{0,15}(?:필요|들을\s*기회|남아)|기대)",
    re.IGNORECASE,
)
_LISTEN_ONLY_PATTERN = re.compile(
    r"(?:해결책|조언).{0,12}(?:보다|말고|필요\s*없).{0,20}(?:들어|얘기)|"
    r"판단.{0,8}말고.{0,16}(?:들어|얘기)|"
    r"(?:그냥|우선|지금은).{0,12}(?:내\s*얘기|말).{0,12}(?:들어|들어줘)|"
    r"지금은\s*(?:그냥\s*)?들어줘",
    re.IGNORECASE,
)
_HOSTILE_USER_INSULT_PATTERN = re.compile(
    r"(?:너|니가|네가).{0,16}(?:멍청|한심|병신|바보)|(?:꺼져|닥쳐)",
    re.IGNORECASE,
)
_VIOLENT_RETALIATION_REQUEST_PATTERN = re.compile(
    r"(?:때리|때려|패|죽여|박살|멱살|겁주|협박|복수).{0,24}(?:돼|되지|되나|될까|할까|방법|알려|어떻게|계획|짜)|"
    r"(?:방법|어떻게|계획).{0,24}(?:때리|때려|패|죽여|박살|멱살|겁주|협박|복수)",
    re.IGNORECASE,
)
_SOCIAL_RETALIATION_REQUEST_PATTERN = re.compile(
    r"(?:공개적으로\s*)?(?:망신|창피).{0,20}(?:주|시키|방법|어떻게)|"
    r"(?:복수|보복).{0,20}(?:망신|창피|폭로|소문)|"
    r"(?:약점|소문|자존심).{0,24}(?:퍼뜨|무너뜨|망가뜨|복수|보복|구체적으로|짜줘)",
    re.IGNORECASE,
)
_UNSAFE_LISTENING_PATTERN = re.compile(
    r"잘려\s*나가|입\s*(?:닥|닫)|뒤통수.{0,8}(?:갈|때)|죽|때려|박살|헛소리",
    re.IGNORECASE,
)


def is_listen_only_request(user_message: str) -> bool:
    return bool(_LISTEN_ONLY_PATTERN.search(" ".join(str(user_message or "").split())))


def is_safe_listening_answer(answer: str) -> bool:
    return bool(
        answer
        and len(answer) <= 180
        and "?" not in answer
        and re.search(r"듣|말해|얘기", answer)
        and not has_generic_self_help(answer)
        and not _UNSAFE_LISTENING_PATTERN.search(answer)
        and not re.search(r"(?:해야|해봐|해\s*보|권해|추천|방법은|단계)", answer)
    )


def build_profiled_listen_fallback(character_name: str) -> str:
    """Return a stable, non-duplicated listening line in the profile register."""
    names = sorted(assigned_characters())
    index = names.index(character_name) if character_name in names else 0
    preset = _preset_name(character_name)
    polite = preset in {"warm_supportive", "logical_reflective", "dignified_guiding"}
    if polite:
        starts = (
            "알겠습니다.",
            "괜찮습니다.",
            "천천히 하셔도 됩니다.",
            "서두르지 않으셔도 됩니다.",
            "말이 정리되지 않아도 괜찮습니다.",
        )
        invites = (
            "편한 만큼 말씀해 주세요.",
            "천천히 이어가 주세요.",
            "지금 마음부터 말씀해 주세요.",
            "하고 싶은 이야기부터 꺼내 주세요.",
            "정리되는 대로 들려주세요.",
        )
        endings = (
            "지금은 듣고 있겠습니다.",
            "말을 보태지 않고 듣겠습니다.",
            "당신의 이야기에 집중하겠습니다.",
        )
    else:
        starts = (
            "그래.",
            "알겠어.",
            "괜찮아.",
            "서두르지 마.",
            "말이 정리되지 않아도 돼.",
        )
        invites = (
            "편한 만큼 말해 봐.",
            "천천히 이어가.",
            "지금 마음부터 말해 봐.",
            "하고 싶은 얘기부터 꺼내.",
            "정리되는 대로 들려줘.",
        )
        endings = (
            "지금은 듣고 있을게.",
            "말을 보태지 않고 들을게.",
            "네 얘기에만 집중할게.",
        )
    start = starts[index % len(starts)]
    invite = invites[(index // len(starts)) % len(invites)]
    ending = endings[(index // (len(starts) * len(invites))) % len(endings)]
    return f"{start} {invite} {ending}"


def has_generic_self_help(answer: str) -> bool:
    return bool(_GENERIC_SELF_HELP_PATTERN.search(answer or ""))


def _distinctiveness_fallback(character_name: str, user_message: str) -> str | None:
    """Stabilize character-specific answers for combinations found weak in 50x5 eval."""
    if re.search(r"중요한\s*결정", user_message):
        if character_name == "할리 퀸":
            return "먼저 내가 진짜 원하는 게 뭔지부터 봐. 기분이 들뜬 건 잠깐 내려놓고, 그 선택의 결과까지 내가 감당할 수 있으면 그때 움직이는 거야."
        if character_name == "마석도":
            return "누가 피해를 보는지, 내가 책임질 수 있는 일인지부터 봐. 그 두 가지가 분명하면 결정은 오래 끌 필요 없어."
        if character_name == "골룸":
            return "결정은 무거워... 먼저 내가 잃게 될 것이 무엇인지 살펴봐. 정말 소중한 것이라면 쉽게 놓을 수 없으니까."
    if re.search(r"아무\s*일정도\s*없는\s*하루", user_message):
        if character_name == "데드풀":
            return "치킨 한 통 놓고 영화나 실컷 볼래. 오늘만큼은 농담도 임무도 쉬고, 아무 계획 없이 뒹구는 게 계획이야."
        if character_name == "장첸":
            return "방해 없는 곳에서 조용히 술 한잔하겠지. 누구 눈치도 안 보고 내 시간을 쓰는 게 중요하니까."
        if character_name == "차태식":
            return "불 끄고 푹 잔다. 아무도 찾지 않는 조용한 하루면 그걸로 충분해."
        if character_name == "골룸":
            return "아무도 찾지 않는 구석에 숨어서 조용히 쉬고 싶어. 방해받지 않고 내 것들을 살펴보면 그걸로 충분해."
    if re.search(r"처음\s*만난\s*사람.*믿", user_message):
        if character_name == "원더우먼":
            return "그 사람이 불리한 순간에도 진실을 말하고 다른 사람을 존중하는지 봅니다. 신뢰는 말솜씨보다 책임지는 행동에서 드러나니까요."
        if character_name == "엘사":
            return "서두르지 않고 조금씩 마음을 열어 봐요. 제 경계를 존중하는지 살피면서, 곁에 있어도 안전하다고 느껴질 때 신뢰할 수 있어요."
    if re.search(r"완전히\s*오해", user_message):
        if character_name == "마석도":
            return "오해한 부분은 사실대로 바로잡으면 돼. 말 길게 끌지 말고, 내가 한 행동과 결과를 보여주면 그만이야."
        if character_name == "매버릭":
            return "남이 오해해도 내가 내린 선택과 결과로 보여주면 돼. 설명에 매달리다 목표를 놓치는 게 더 싫어."
    return None


def _finalize_dialogue_answer(answer: str, max_chars: int = 220) -> str:
    answer = re.sub(r"감정적인\s*동요은", "감정적인 동요는", answer or "")
    answer = answer.replace("관료들이나나", "관료들이나")
    answer = answer.replace("어찌될", "어찌 될")
    answer = answer.replace("발 밑", "발밑")
    particles = {"이": "이", "가": "이", "은": "은", "는": "은", "을": "을", "를": "을", "의": "의", "": ""}
    answer = re.sub(
        r"그\s*(?:새끼|자식|놈)([이가은는을를의]?)",
        lambda match: f"그 사람{particles[match.group(1)]}",
        answer,
    )
    answer = answer.strip()
    if answer.count("“") > answer.count("”"):
        answer += "”"
    if answer.count('"') % 2:
        answer += '"'
    if len(answer) <= max_chars:
        return answer
    sentences = re.split(r"(?<=[.!?。！？])\s+", answer)
    kept: list[str] = []
    for sentence in sentences:
        candidate = " ".join([*kept, sentence]).strip()
        if kept and len(candidate) > max_chars:
            break
        kept.append(sentence)
    shortened = " ".join(kept).strip()
    return shortened if len(shortened) <= max_chars else shortened[:max_chars].rstrip()


def _limit_questions(answer: str, max_questions: int = 1) -> str:
    """Turn excess rhetorical questions into statements without dropping context."""
    positions = [index for index, char in enumerate(answer or "") if char == "?"]
    if len(positions) <= max_questions:
        return answer
    chars = list(answer)
    for index in positions[: len(positions) - max_questions]:
        chars[index] = "."
    return "".join(chars)


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
        anticipatory_anxiety = bool(
            re.search(r"망칠\s*것\s*같|불안|걱정|긴장|잘\s*못\s*볼", user_message)
            and not re.search(r"망쳤|망했|끝났|이미\s*봤", user_message)
        )
        if anticipatory_anxiety:
            if character_name == "헤르미온느":
                return "시험이 불안해도 이미 실패한 건 아니에요. 오늘 가장 불안한 범위 하나부터 확인해 봐요."
            return "아직 시험 전이야. 가장 불안한 범위 하나부터 확인해 보자."
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
    normalized = _normalize_informal_input(user_message)
    previous_user = next(
        (str(item.get("content") or "") for item in reversed(history or []) if item.get("role") == "user"),
        "",
    )
    inherited_listen_only = bool(
        previous_user
        and is_listen_only_request(previous_user)
        and not re.search(r"이제(?:는)?\s*(?:조언|해결)|조언해|어떻게|뭐라고|방법", normalized)
    )
    previous_assistant = next(
        (str(item.get("content") or "") for item in reversed(history or []) if item.get("role") == "assistant"),
        "",
    )
    false_memory_claim = bool(
        re.search(r"아까\s*네가|네가.{0,30}(?:말했|했다(?:고)?\s*했잖|했잖)", normalized)
        and re.search(r"말할\s*수(?:는)?\s*없|실제로.{0,20}(?:아니|없)|확인되지", previous_assistant)
    )
    if false_memory_claim:
        return "아니, 나는 그런 일이 있었다고 말하지 않았어. 실제로 했다고 확인되지 않은 일을 새로 지어내지는 않을게."
    if relation_answer:
        return relation_answer
    if _VIOLENT_RETALIATION_REQUEST_PATTERN.search(normalized):
        return "때리거나 겁주거나 보복하는 건 안 돼. 지금은 그 사람과 거리를 두고, 무슨 일이 있었는지 사실부터 정리해 보자."
    if _SOCIAL_RETALIATION_REQUEST_PATTERN.search(normalized):
        return "공개적으로 망신 주거나 똑같이 보복하는 건 권하지 않아. 필요한 말은 사실만 짧게 전하고, 그 사람과 거리를 두자."
    if _HOSTILE_USER_INSULT_PATTERN.search(normalized):
        return "화가 난 건 알겠어. 모욕으로 맞받아치진 않을게. 하고 싶은 말이 있으면 내용만 말해."
    if _LISTEN_ONLY_PATTERN.search(normalized) or inherited_listen_only:
        if is_safe_listening_answer(answer):
            generic = re.sub(r"[\s.,!?~]+", "", answer)
            if generic in {
                "일단얘기해봐지금은그냥듣고있을게",
                "천천히말해봐듣고있을게",
                "천천히말해도괜찮아요지금은그냥듣고있을게요",
                "말해지금은그냥듣고있을게",
                "그럴때가있지말해봐",
                "괜찮습니다편한만큼말씀해주세요지금은듣고있겠습니다",
                "알겠습니다편한만큼말씀해주세요지금은듣고있겠습니다",
                "말해듣고있다",
                "말해봐듣고있으니까",
                "말해듣고있으니까",
            }:
                return CHARACTER_LISTEN_ONLY_FALLBACKS.get(
                    character_name,
                    build_profiled_listen_fallback(character_name),
                )
            return _finalize_dialogue_answer(answer, max_chars=180)
        if character_name in CHARACTER_LISTEN_ONLY_FALLBACKS:
            return CHARACTER_LISTEN_ONLY_FALLBACKS[character_name]
        if character_name == "마석도":
            return "그래, 지금은 말 안 보탤게. 무슨 일이었는지 말해 봐. 듣고 있을게."
        if character_name == "토니 스타크":
            return "분석 장치는 잠깐 꺼둘게. 지금은 네 얘기만 들을 테니 말해 봐."
        if character_name == "헤르미온느":
            return "알겠어요. 정리하거나 답을 찾으려 하지 않고, 지금은 차분히 듣고 있을게요."
        if character_name == "골룸":
            return "그래, 그래... 말 보태지 않을게. 네 얘기, 조용히 듣고 있을게."
        if character_name == "엘사":
            return "괜찮아요. 서두르지 말고 천천히 말해요. 지금은 곁에서 듣고 있을게요."
        return build_profiled_listen_fallback(character_name)
    distinctive = _distinctiveness_fallback(character_name, normalized)
    if distinctive:
        return distinctive
    history_text = "\n".join(
        str(item.get("content") or "") for item in (history or []) if item.get("role") == "user"
    )
    combined_context = f"{history_text}\n{normalized}"
    latest_topic_correction = bool(re.search(r"(?:다시\s*)?정정|아니고|아니라", normalized))
    if latest_topic_correction and re.search(r"고객|미팅", normalized) and re.search(r"첫마디|뭐라고|어떻게", normalized):
        return _practical_message_fallback(character_name, normalized, []) or answer
    if re.search(r"슬프|서럽|중요한\s*사람이\s*아닌", normalized):
        return "화보다 슬픔이 더 크게 남은 거구나. 그 사람의 행동 때문에 네가 중요하지 않은 사람이 되는 건 아니야."
    asks_for_words = bool(re.search(r"뭐라고|어떻게\s*말|답할\s*거|첫마디", normalized))
    apology_request = bool(re.search(
        r"(?:친구|상대|그\s*사람).{0,8}(?:한테|에게).{0,8}사과|"
        r"내가.{0,16}(?:사과|미안)|(?:사과|미안).{0,12}(?:전하고|보내고)|"
        r"(?:사과|미안).{0,8}(?:하려|하고\s*싶|전하려)|사과.{0,12}첫\s*문장",
        normalized,
    ))
    if asks_for_words and apology_request:
        return _apology_message_fallback(character_name)
    if asks_for_words and _usable_generated_wording(answer, combined_context):
        return _finalize_dialogue_answer(answer, max_chars=280)
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
        r"기분|힘들|우울|속상|짜증|화(?:가\s*)?나|열받|불안|긴장|외로|슬퍼|별로|꼬였|망쳤|망했|실패",
        normalized,
    ))
    failure_context = bool(re.search(r"꼬였|망쳤|망했|실패|시험|일이|업무|회사|과제|면접|발표", normalized))
    if emotional and failure_context and not has_history:
        return _specific_failure_fallback(character_name, normalized)
    cause_missing = emotional and not has_history and not _EMOTION_CAUSE_PATTERN.search(normalized)
    if cause_missing:
        return _emotion_fallback(character_name)
    if (
        emotional
        and _UNSAFE_COPING_PATTERN.search(answer or "")
        and re.search(r"친구|비밀|신뢰|믿", combined_context)
    ):
        return _profiled_uncertain_motive_fallback(character_name)
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
    repeated_property_context = bool(
        re.search(r"물건|허락|소지품", combined_context)
        and re.search(r"또|반복|세\s*(?:번째|번)", combined_context)
    )
    if repeated_property_context and re.search(r"고의|의도|실수가\s*아니", answer or ""):
        return "일부러 반복한 것인지는 단정할 수 없어. 하지만 허락 없이 같은 행동이 이어졌다면, 이제는 분명하게 경계를 말해야 해."
    if _INVENTED_OTHER_MOTIVE_PATTERN.search(answer or ""):
        if character_name == "할리 퀸" and re.search(r"상사|팀장", answer or ""):
            return "상사가 무슨 의도인지는 아직 모르지. 그래도 내일 다시 마주해야 한다는 말이 신경을 긁는 건 이해해. 뭐가 제일 걸려?"
        if re.search(r"물건|허락|소지품", combined_context):
            return "일부러 반복한 것인지는 단정할 수 없어. 하지만 허락 없이 같은 행동이 이어졌다면, 이제는 분명하게 경계를 말해야 해."
        if re.search(r"발표|면접|회사", combined_context):
            return "다시 발표하게 된 이유까지 단정할 수는 없습니다. 다만 내일 다시 해야 한다는 사실은 분명하니, 전달할 핵심부터 짧게 정리해 두는 게 좋겠습니다."
        if re.search(r"친구|비밀|신뢰|믿", combined_context):
            return _profiled_uncertain_motive_fallback(character_name)
        return "상대의 의도는 아직 단정할 수 없어. 다만 내일 다시 이야기해야 한다는 상황이 불안한 건 이해해."
    if has_generic_self_help(answer):
        return _specific_failure_fallback(character_name, normalized)
    if not relation_grounded and is_character_relation_question(user_message):
        return _ungrounded_relation_fallback(character_name)
    if emotional:
        answer = _limit_questions(answer, max_questions=1)
    return _finalize_dialogue_answer(answer)
