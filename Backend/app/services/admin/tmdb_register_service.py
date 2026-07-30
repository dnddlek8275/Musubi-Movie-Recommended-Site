from datetime import datetime, timezone

import httpx

from app.services.admin.tmdb_search_service import (
    TMDB_BASE_URL,
    tmdb_image_url,
)
from app.services.movies.tmdb_trailer_service import get_tmdb_auth


def _truncate(value: str | None, max_length: int) -> str | None:
    """외부 API 문자열을 DB 컬럼 길이에 맞게 안전하게 자른다."""

    if value is None:
        return None

    normalized_value = value.strip()

    if not normalized_value:
        return None

    return normalized_value[:max_length]


async def fetch_admin_tmdb_movie_detail(tmdb_id: int) -> dict:
    """관리자가 선택한 TMDB 영화의 상세정보를 내부 Movie 형식으로 변환한다.

    Args:
        tmdb_id: TMDB 검색 결과에서 선택한 영화의 고유 ID.

    Returns:
        Movie 모델의 컬럼 이름에 맞춘 영화 정보 딕셔너리.

    Raises:
        ValueError: 잘못된 ID, TMDB 인증 누락, 존재하지 않는 영화 또는
            예상하지 못한 TMDB 응답 형식이 확인된 경우.
        httpx.HTTPError: TMDB 인증 오류, 요청 제한 또는 서버 오류가 발생한 경우.
    """

    # 0 이하의 값은 정상적인 TMDB 영화 ID가 아니므로 외부 요청 전에 차단한다.
    if tmdb_id <= 0:
        raise ValueError("올바른 TMDB 영화 ID가 아닙니다.")

    # 기존 예고편 서비스의 인증 처리를 재사용해 Access Token과 API Key
    # 처리 로직을 관리자 서비스에 중복 구현하지 않는다.
    auth = get_tmdb_auth()

    if auth is None:
        raise ValueError("TMDB 인증 정보가 설정되지 않았습니다.")

    headers, auth_params = auth

    # 상세정보, 출연진, 제작진, 키워드를 한 번의 TMDB 요청으로 가져온다.
    # 검색 결과의 데이터를 그대로 저장하지 않고 서버가 tmdb_id로 다시
    # 조회함으로써 클라이언트에서 조작한 영화 정보가 저장되는 것을 막는다.
    async with httpx.AsyncClient(
        base_url=TMDB_BASE_URL,
        headers=headers,
        timeout=10.0,
    ) as client:
        response = await client.get(
            f"/movie/{tmdb_id}",
            params={
                **auth_params,
                "language": "ko-KR",
                "append_to_response": "credits,keywords",
            },
        )

        if response.status_code == 404:
            raise ValueError("TMDB에서 해당 영화를 찾을 수 없습니다.")

        # 401 인증 실패, 429 요청 제한, 5xx 서버 오류 등을 예외로 처리한다.
        response.raise_for_status()
        detail = response.json()

    if not isinstance(detail, dict):
        raise ValueError("TMDB 영화 상세정보 형식이 올바르지 않습니다.")

    returned_tmdb_id = detail.get("id")

    if not isinstance(returned_tmdb_id, int) or returned_tmdb_id <= 0:
        raise ValueError("TMDB 영화 상세정보에 올바른 ID가 없습니다.")

    # credits 안의 crew는 감독을 찾는 데 사용하고 cast는 출연 배우를
    # 영화에 표시하는 순서대로 가져오는 데 사용한다.
    credits = detail.get("credits") or {}

    if not isinstance(credits, dict):
        credits = {}

    raw_crew = credits.get("crew") or []
    raw_cast = credits.get("cast") or []

    if not isinstance(raw_crew, list):
        raw_crew = []

    if not isinstance(raw_cast, list):
        raw_cast = []

    directors = [
        crew_member.get("name")
        for crew_member in raw_crew
        if (
            isinstance(crew_member, dict)
            and crew_member.get("job") == "Director"
            and isinstance(crew_member.get("name"), str)
        )
    ]

    # 출연진 전체를 저장하면 응답과 추천 연산이 불필요하게 커질 수 있으므로
    # TMDB 출연 순서 기준 상위 10명만 영화 배열과 배우 관계 저장에 사용한다.
    cast_names = []
    cast_credits = []

    for default_order, cast_member in enumerate(raw_cast[:10]):
        if not isinstance(cast_member, dict):
            continue

        tmdb_actor_id = cast_member.get("id")
        actor_name = cast_member.get("name")

        # actors 테이블은 TMDB 배우 ID를 중복 방지 기준으로 사용하므로
        # 정상적인 ID와 이름이 모두 있는 출연진만 관계 저장 대상으로 삼는다.
        if (
            not isinstance(tmdb_actor_id, int)
            or tmdb_actor_id <= 0
            or not isinstance(actor_name, str)
            or not actor_name.strip()
        ):
            continue

        normalized_actor_name = actor_name.strip()[:100]
        cast_names.append(normalized_actor_name)

        raw_order = cast_member.get("order")

        cast_credits.append(
            {
                "tmdb_actor_id": tmdb_actor_id,
                "name": normalized_actor_name,
                "profile_path": _truncate(
                    tmdb_image_url(cast_member.get("profile_path")),
                    300,
                ),
                "character_name": _truncate(
                    cast_member.get("character"),
                    150,
                ),
                # TMDB order가 없거나 정수가 아니면 현재 목록 순서를 사용한다.
                "cast_order": (
                    raw_order
                    if isinstance(raw_order, int)
                    else default_order
                ),
            }
        )

    keyword_payload = detail.get("keywords") or {}

    if not isinstance(keyword_payload, dict):
        keyword_payload = {}

    raw_keywords = keyword_payload.get("keywords") or []

    if not isinstance(raw_keywords, list):
        raw_keywords = []

    keyword_names = [
        keyword.get("name")
        for keyword in raw_keywords
        if (
            isinstance(keyword, dict)
            and isinstance(keyword.get("name"), str)
        )
    ]

    raw_genres = detail.get("genres") or []

    if not isinstance(raw_genres, list):
        raw_genres = []

    genre_names = [
        genre.get("name")
        for genre in raw_genres
        if (
            isinstance(genre, dict)
            and isinstance(genre.get("name"), str)
        )
    ]

    # release_date는 YYYY-MM-DD 형식이므로 앞의 네 자리가 숫자인 경우에만
    # 개봉 연도로 변환하고, 날짜가 없거나 잘못된 경우에는 None을 저장한다.
    release_date = detail.get("release_date") or ""
    year = (
        int(release_date[:4])
        if (
            isinstance(release_date, str)
            and len(release_date) >= 4
            and release_date[:4].isdigit()
        )
        else None
    )

    # 기존 TMDB 일괄 가져오기 스크립트가 original_title을 저장하므로
    # 관리자 등록 영화도 같은 제목 기준을 사용해 기존 DB의 일관성을 유지한다.
    title = (
        _truncate(detail.get("original_title"), 300)
        or _truncate(detail.get("title"), 300)
        or f"TMDB {returned_tmdb_id}"
    )

    # Movie 모델의 컬럼 이름과 동일한 키로 변환해 공통 영화 등록 서비스가
    # TMDB 등록과 수동 등록을 같은 방식으로 처리할 수 있게 한다.
    return {
        "tmdb_id": returned_tmdb_id,
        "title": title,
        "overview": detail.get("overview") or None,
        "genres": genre_names,
        "director": _truncate(
            ", ".join(dict.fromkeys(directors)),
            200,
        ),
        "cast": list(dict.fromkeys(cast_names)),
        # movies.cast에는 표시·추천용 이름 배열을 저장하고, cast_credits는
        # actors와 movie_actors 테이블을 정규화해 생성하는 내부 자료로 쓴다.
        "cast_credits": cast_credits,
        "keywords": list(dict.fromkeys(keyword_names)),
        "year": year,
        "language": _truncate(detail.get("original_language"), 10),
        "vote_average": detail.get("vote_average"),
        "vote_count": detail.get("vote_count"),
        # TMDB에는 국내 관객 수 정보가 없으므로 등록 시 None을 사용한다.
        "audience_count": None,
        "poster_path": _truncate(
            tmdb_image_url(detail.get("poster_path")),
            300,
        ),
        # TMDB에서 정보를 가져온 시각을 기록해 이후 재동기화 판단에 사용한다.
        "last_synced_at": datetime.now(timezone.utc),
    }
