import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher

from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.actors import Actor, MovieActor
from app.models.character import Character, CharacterAlias
from app.models.movies import Movie, MovieGenre


MAX_WORD_WINDOW = 6
MIN_SCORE_MARGIN = 0.05
MAX_TERM_LENGTH_DIFFERENCE = 1
MAX_LONG_CHARACTER_TERM_LENGTH_DIFFERENCE = 2

HANGUL_BASE = 0xAC00
HANGUL_END = 0xD7A3
JUNGSEONG_COUNT = 21
JONGSEONG_COUNT = 28

INITIAL_SOUND_WEIGHT = 0.50
VOWEL_SOUND_WEIGHT = 0.30
FINAL_SOUND_WEIGHT = 0.20

KOREAN_PARTICLES = (
    "으로부터",
    "에게서",
    "이라고",
    "이라도",
    "이라면",
    "으로",
    "에게",
    "한테",
    "처럼",
    "보다",
    "까지",
    "부터",
    "이랑",
    "하고",
    "에서",
    "랑",
    "은",
    "는",
    "이",
    "가",
    "을",
    "를",
    "와",
    "과",
    "도",
    "만",
    "의",
    "에",
)

EXACT_CATEGORY_PRIORITY = {
    "preferred_character": 1,
    "character_alias": 2,
    "character": 3,
    "movie": 4,
    "role": 5,
    "actor": 6,
    "director": 7,
    "genre_alias": 8,
    "genre": 9,
}

GENRE_ALIASES = {
    "에스에프": "SF",
    "에스 에프": "SF",
    "사이파이": "SF",
    "호러": "공포",
    "로맨틱": "로맨스",
    "멜로": "로맨스",
    "애니": "애니메이션",
    "다큐": "다큐멘터리",
}


# STT 보정 후보의 정상 표기와 유사도 비교 정보를 관리한다.
@dataclass(frozen=True)
class SttTermCandidate:
    display_name: str
    normalized_name: str
    pronunciation_name: str
    category: str
    is_preferred: bool = False


# 띄어쓰기와 특수문자를 제거해 STT 결과와 DB 용어를 같은 기준으로 비교한다.
def normalize_stt_term(value: str) -> str:
    return re.sub(r"[^0-9a-zA-Z가-힣]", "", value).lower()


# 한글을 자음과 모음 단위로 분해해 비슷한 발음을 비교할 수 있게 만든다.
def normalize_korean_pronunciation(value: str) -> str:
    normalized_value = normalize_stt_term(value)
    return unicodedata.normalize("NFD", normalized_value)


# 활성 캐릭터 공식 이름을 조회해 Whisper가 참고할 우선 어휘를 만든다.
def build_character_hotwords(db: Session) -> str | None:
    character_names = db.scalars(
        select(Character.name)
        .where(Character.is_active.is_(True))
        .order_by(Character.id.asc())
    ).all()
    unique_names = dict.fromkeys(
        name.strip()
        for name in character_names
        if name and name.strip()
    )
    hotwords = " ".join(unique_names)

    return hotwords or None


# 한글 한 글자를 초성·중성·종성 번호로 분해한다.
def decompose_hangul_syllable(
    character: str,
) -> tuple[int, int, int] | None:
    character_code = ord(character)

    if not HANGUL_BASE <= character_code <= HANGUL_END:
        return None

    syllable_index = character_code - HANGUL_BASE
    choseong = syllable_index // (JUNGSEONG_COUNT * JONGSEONG_COUNT)
    jungseong = (
        syllable_index % (JUNGSEONG_COUNT * JONGSEONG_COUNT)
    ) // JONGSEONG_COUNT
    jongseong = syllable_index % JONGSEONG_COUNT

    return choseong, jungseong, jongseong


# 비교할 문자열이 완성형 한글로만 구성되어 있는지 확인한다.
def is_hangul_text(value: str) -> bool:
    if not value:
        return False

    return all(
        HANGUL_BASE <= ord(character) <= HANGUL_END
        for character in value
    )


# 두 한글 음절의 초성·중성·종성 일치 정도를 치환 유사도로 계산한다.
def calculate_hangul_substitution_similarity(
    recognized_character: str,
    candidate_character: str,
) -> float:
    if recognized_character == candidate_character:
        return 1.0

    recognized_syllable = decompose_hangul_syllable(
        recognized_character
    )
    candidate_syllable = decompose_hangul_syllable(
        candidate_character
    )

    if recognized_syllable is None or candidate_syllable is None:
        return 0.0

    similarity = 0.0

    if recognized_syllable[0] == candidate_syllable[0]:
        similarity += INITIAL_SOUND_WEIGHT

    if recognized_syllable[1] == candidate_syllable[1]:
        similarity += VOWEL_SOUND_WEIGHT

    if recognized_syllable[2] == candidate_syllable[2]:
        similarity += FINAL_SOUND_WEIGHT

    return similarity


# 글자 삽입과 누락을 고려하는 가중 편집거리로 한글 이름 유사도를 계산한다.
def calculate_hangul_edit_similarity(
    recognized_term: str,
    candidate_term: str,
) -> float:
    recognized_text = normalize_stt_term(recognized_term)
    candidate_text = normalize_stt_term(candidate_term)

    if not recognized_text or not candidate_text:
        return 0.0

    previous_row = [
        float(index)
        for index in range(len(candidate_text) + 1)
    ]

    for recognized_index, recognized_character in enumerate(
        recognized_text,
        start=1,
    ):
        current_row = [float(recognized_index)]

        for candidate_index, candidate_character in enumerate(
            candidate_text,
            start=1,
        ):
            substitution_similarity = (
                calculate_hangul_substitution_similarity(
                    recognized_character,
                    candidate_character,
                )
            )
            substitution_cost = 1.0 - substitution_similarity
            deletion_cost = previous_row[candidate_index] + 1.0
            insertion_cost = current_row[candidate_index - 1] + 1.0
            replacement_cost = (
                previous_row[candidate_index - 1]
                + substitution_cost
            )
            current_row.append(
                min(
                    deletion_cost,
                    insertion_cost,
                    replacement_cost,
                )
            )

        previous_row = current_row

    maximum_length = max(
        len(recognized_text),
        len(candidate_text),
    )
    distance = previous_row[-1]

    return max(
        0.0,
        1.0 - distance / maximum_length,
    )


# 정상 표기와 비교용 문자열을 STT 보정 후보 객체로 만든다.
def create_stt_candidate(
    comparison_name: str,
    display_name: str,
    category: str,
    is_preferred: bool = False,
) -> SttTermCandidate | None:
    normalized_name = normalize_stt_term(comparison_name)

    if len(normalized_name) < 2:
        return None

    return SttTermCandidate(
        display_name=display_name,
        normalized_name=normalized_name,
        pronunciation_name=normalize_korean_pronunciation(comparison_name),
        category=category,
        is_preferred=is_preferred,
    )


# 동일한 비교 이름과 카테고리가 중복으로 등록되지 않도록 후보를 추가한다.
def append_stt_candidate(
    candidates: list[SttTermCandidate],
    candidate_keys: set[tuple[str, str]],
    comparison_name: str,
    display_name: str,
    category: str,
    is_preferred: bool = False,
) -> None:
    candidate = create_stt_candidate(
        comparison_name=comparison_name,
        display_name=display_name,
        category=category,
        is_preferred=is_preferred,
    )

    if candidate is None:
        return

    candidate_key = (candidate.normalized_name, candidate.category)

    if candidate_key in candidate_keys:
        return

    candidate_keys.add(candidate_key)
    candidates.append(candidate)


# 현재 대화 중인 캐릭터 이름을 가장 먼저 검사할 우선 후보로 만든다.
def build_preferred_candidates(
    preferred_terms: list[str] | None,
) -> list[SttTermCandidate]:
    candidates = []
    candidate_keys = set()

    for preferred_term in preferred_terms or []:
        append_stt_candidate(
            candidates=candidates,
            candidate_keys=candidate_keys,
            comparison_name=preferred_term,
            display_name=preferred_term,
            category="preferred_character",
            is_preferred=True,
        )

    return candidates


# 영화·배우·감독·배역·캐릭터·별칭을 DB에서 조회해 보정 후보로 만든다.
def add_proper_name_candidates(
    db: Session,
    candidates: list[SttTermCandidate],
    candidate_keys: set[tuple[str, str]],
) -> None:
    movies = db.query(Movie.title, Movie.director, Movie.cast).all()

    for title, director, cast in movies:
        if title:
            append_stt_candidate(
                candidates,
                candidate_keys,
                title,
                title,
                "movie",
            )

        if director:
            append_stt_candidate(
                candidates,
                candidate_keys,
                director,
                director,
                "director",
            )

        for actor_name in cast or []:
            append_stt_candidate(
                candidates,
                candidate_keys,
                actor_name,
                actor_name,
                "actor",
            )

    actors = db.query(Actor.name).filter(Actor.name.isnot(None)).all()

    for actor_name, in actors:
        append_stt_candidate(
            candidates,
            candidate_keys,
            actor_name,
            actor_name,
            "actor",
        )

    role_names = (
        db.query(MovieActor.character_name)
        .filter(MovieActor.character_name.isnot(None))
        .all()
    )

    for role_name, in role_names:
        append_stt_candidate(
            candidates,
            candidate_keys,
            role_name,
            role_name,
            "role",
        )

    characters = (
        db.query(Character.name)
        .filter(Character.is_active.is_(True))
        .all()
    )

    for character_name, in characters:
        append_stt_candidate(
            candidates,
            candidate_keys,
            character_name,
            character_name,
            "character",
        )

    aliases = (
        db.query(CharacterAlias.alias, Character.name)
        .join(Character, Character.id == CharacterAlias.character_id)
        .filter(Character.is_active.is_(True))
        .all()
    )

    for alias, character_name in aliases:
        append_stt_candidate(
            candidates,
            candidate_keys,
            alias,
            character_name,
            "character_alias",
        )


# 영화별로 반복 저장된 장르에서 중복 없는 공식 장르 후보를 만든다.
def add_genre_candidates(
    db: Session,
    candidates: list[SttTermCandidate],
    candidate_keys: set[tuple[str, str]],
) -> None:
    genre_rows = (
        db.query(MovieGenre.genre)
        .filter(MovieGenre.genre.isnot(None))
        .distinct()
        .all()
    )

    for genre, in genre_rows:
        append_stt_candidate(
            candidates,
            candidate_keys,
            genre,
            genre,
            "genre",
        )

    # 의미는 같지만 발음이 다른 장르 표현을 공식 장르명으로 연결한다.
    for alias, genre_name in GENRE_ALIASES.items():
        append_stt_candidate(
            candidates,
            candidate_keys,
            alias,
            genre_name,
            "genre_alias",
        )


# DB에서 현재 사용할 전체 STT 보정 후보를 구성한다.
def build_database_candidates(db: Session) -> list[SttTermCandidate]:
    candidates = []
    candidate_keys = set()

    add_proper_name_candidates(db, candidates, candidate_keys)
    add_genre_candidates(db, candidates, candidate_keys)

    return candidates


# 완성형 문자와 한글 자모를 각각 비교해 더 높은 유사도 점수를 반환한다.
def calculate_stt_similarity(
    recognized_term: str,
    candidate: SttTermCandidate,
) -> float:
    normalized_term = normalize_stt_term(recognized_term)

    if (
        is_hangul_text(normalized_term)
        and is_hangul_text(candidate.normalized_name)
    ):
        return calculate_hangul_edit_similarity(
            recognized_term,
            candidate.normalized_name,
        )

    pronunciation_term = normalize_korean_pronunciation(recognized_term)

    character_score = SequenceMatcher(
        None,
        normalized_term,
        candidate.normalized_name,
    ).ratio()
    pronunciation_score = SequenceMatcher(
        None,
        pronunciation_term,
        candidate.pronunciation_name,
    ).ratio()

    return max(character_score, pronunciation_score)


# 긴 캐릭터 이름만 두 글자까지 누락을 허용하고 짧은 이름은 엄격하게 비교한다.
def get_max_term_length_difference(
    candidate: SttTermCandidate,
) -> int:
    if (
        candidate.category
        in {
            "character",
            "character_alias",
            "preferred_character",
        }
        and len(candidate.normalized_name) >= 5
    ):
        return MAX_LONG_CHARACTER_TERM_LENGTH_DIFFERENCE

    return MAX_TERM_LENGTH_DIFFERENCE


# 후보 종류와 단어 길이에 따라 자동 보정에 필요한 최소 점수를 결정한다.
def get_required_similarity(
    candidate: SttTermCandidate,
    term_length: int,
) -> float:
    if candidate.is_preferred:
        return 0.62 if term_length <= 3 else 0.70

    if candidate.category == "genre_alias":
        return 0.95

    if candidate.category == "genre":
        return 0.95 if term_length <= 2 else 0.82

    if term_length <= 3:
        # 짧은 영문 약어가 비슷한 인물명으로 바뀌지 않도록 한글만 완화한다.
        if is_hangul_text(candidate.normalized_name):
            return 0.70

        return 0.95

    if term_length <= 6:
        return 0.75

    return 0.82


# 후보 목록에서 유사도가 충분하고 다른 후보와 구분되는 이름을 찾는다.
def find_best_stt_candidate(
    recognized_term: str,
    candidates: list[SttTermCandidate],
) -> str | None:
    normalized_term = normalize_stt_term(recognized_term)

    if len(normalized_term) < 2:
        return None

    candidates_by_display_name = {}

    for candidate in candidates:
        length_difference = abs(
            len(candidate.normalized_name) - len(normalized_term)
        )

        # 한 후보가 뒤의 일반 단어까지 함께 소비하지 않도록 길이 차이를 제한한다.
        if length_difference > get_max_term_length_difference(candidate):
            continue

        similarity_score = calculate_stt_similarity(
            recognized_term,
            candidate,
        )
        display_key = normalize_stt_term(candidate.display_name)
        current_match = candidates_by_display_name.get(display_key)

        # 배우·캐릭터처럼 같은 이름이 여러 분류에 있어도 하나의 후보로 비교한다.
        if current_match is None or similarity_score > current_match[0]:
            candidates_by_display_name[display_key] = (
                similarity_score,
                candidate,
            )

    if not candidates_by_display_name:
        return None

    scored_candidates = list(candidates_by_display_name.values())
    scored_candidates.sort(key=lambda item: item[0], reverse=True)
    best_score, best_candidate = scored_candidates[0]
    required_score = get_required_similarity(
        candidate=best_candidate,
        term_length=len(normalized_term),
    )

    if best_score < required_score:
        return None

    if len(scored_candidates) > 1:
        second_score = scored_candidates[1][0]

        if best_score - second_score < MIN_SCORE_MARGIN:
            return None

    return best_candidate.display_name


# 공백과 특수문자를 제외한 문자열과 정확히 일치하는 DB 후보를 찾는다.
def find_exact_stt_candidate(
    recognized_term: str,
    candidates: list[SttTermCandidate],
) -> str | None:
    normalized_term = normalize_stt_term(recognized_term)

    if not normalized_term:
        return None

    exact_candidates = [
        candidate
        for candidate in candidates
        if candidate.normalized_name == normalized_term
    ]

    if not exact_candidates:
        return None

    exact_candidates.sort(
        key=lambda candidate: EXACT_CATEGORY_PRIORITY.get(
            candidate.category,
            100,
        )
    )

    return exact_candidates[0].display_name


# 현재 채팅 캐릭터를 먼저 검사하고 없으면 전체 DB 후보를 검사한다.
def find_stt_correction(
    recognized_term: str,
    preferred_candidates: list[SttTermCandidate],
    database_candidates: list[SttTermCandidate],
) -> str | None:
    if preferred_candidates:
        preferred_correction = find_best_stt_candidate(
            recognized_term,
            preferred_candidates,
        )

        if preferred_correction:
            return preferred_correction

    return find_best_stt_candidate(
        recognized_term,
        database_candidates,
    )


# 이름 뒤의 쉼표와 마침표 같은 문장 부호를 분리해 보정 후 복원한다.
def split_trailing_punctuation(value: str) -> tuple[str, str]:
    matched = re.search(r"([^\w가-힣]+)$", value)

    if matched is None:
        return value, ""

    punctuation = matched.group(1)

    return value[:-len(punctuation)], punctuation


# 정확한 전체 이름이 아닌 경우에만 이름 뒤의 한국어 조사를 분리한다.
def split_trailing_particle(value: str) -> tuple[str, str]:
    for particle in KOREAN_PARTICLES:
        if not value.endswith(particle):
            continue

        term = value[:-len(particle)]

        if len(normalize_stt_term(term)) < 2:
            continue

        return term, particle

    return value, ""


# 이름·별칭의 정확 일치를 우선하고 조사와 문장 부호를 보존해 보정한다.
def correct_stt_term(
    recognized_term: str,
    preferred_candidates: list[SttTermCandidate],
    database_candidates: list[SttTermCandidate],
) -> str | None:
    term, punctuation = split_trailing_punctuation(
        recognized_term
    )
    all_candidates = [
        *preferred_candidates,
        *database_candidates,
    ]
    exact_correction = find_exact_stt_candidate(
        recognized_term=term,
        candidates=all_candidates,
    )

    # 전체 표현을 먼저 검사해 "고니"를 "곤 + 이"처럼 잘못 나누지 않는다.
    if exact_correction:
        return f"{exact_correction}{punctuation}"

    term_without_particle, particle = split_trailing_particle(
        term
    )
    exact_correction = find_exact_stt_candidate(
        recognized_term=term_without_particle,
        candidates=all_candidates,
    )

    if exact_correction:
        return f"{exact_correction}{particle}{punctuation}"

    fuzzy_correction = find_stt_correction(
        recognized_term=term_without_particle,
        preferred_candidates=preferred_candidates,
        database_candidates=database_candidates,
    )

    if fuzzy_correction:
        return f"{fuzzy_correction}{particle}{punctuation}"

    fuzzy_correction = find_stt_correction(
        recognized_term=term,
        preferred_candidates=preferred_candidates,
        database_candidates=database_candidates,
    )

    if fuzzy_correction:
        return f"{fuzzy_correction}{punctuation}"

    return None


# STT 문장을 단어 묶음으로 검사해 확실한 고유명사와 장르를 보정한다.
def correct_stt_terms(
    db: Session,
    text: str,
    preferred_terms: list[str] | None = None,
) -> str:
    words = text.split()

    if not words:
        return text

    preferred_candidates = build_preferred_candidates(preferred_terms)
    database_candidates = build_database_candidates(db)

    if not preferred_candidates and not database_candidates:
        return text

    corrected_words = []
    word_index = 0

    while word_index < len(words):
        selected_correction = None
        selected_word_count = 0
        max_window_size = min(
            MAX_WORD_WINDOW,
            len(words) - word_index,
        )

        # 여러 단어로 된 이름을 찾기 위해 긴 단어 묶음부터 비교한다.
        for window_size in range(max_window_size, 0, -1):
            recognized_term = " ".join(
                words[word_index:word_index + window_size]
            )
            correction = correct_stt_term(
                recognized_term=recognized_term,
                preferred_candidates=preferred_candidates,
                database_candidates=database_candidates,
            )

            if correction:
                selected_correction = correction
                selected_word_count = window_size
                break

        if selected_correction:
            corrected_words.append(selected_correction)
            word_index += selected_word_count
        else:
            corrected_words.append(words[word_index])
            word_index += 1

    return " ".join(corrected_words)
