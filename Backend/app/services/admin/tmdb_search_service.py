import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.movies import Movie
from app.services.movies.tmdb_trailer_service import get_tmdb_auth


# TMDB 영화 검색 API의 기본 주소
TMDB_BASE_URL = "https://api.themoviedb.org/3"

# 관리자 검색 화면에서 사용할 TMDB 포스터 이미지 주소
TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"


def tmdb_image_url(poster_path: str | None) -> str | None:
    """TMDB 포스터 경로를 프론트에서 사용할 전체 URL로 변환한다."""

    # 포스터가 없는 영화는 이미지 URL도 None으로 반환한다.
    if not poster_path:
        return None

    # 이미 전체 URL이면 TMDB 이미지 주소를 중복으로 붙이지 않는다.
    if poster_path.startswith(("http://", "https://")):
        return poster_path

    # TMDB가 반환한 /abc.jpg 형식의 경로 앞에 이미지 서버 주소를 붙인다.
    return f"{TMDB_IMAGE_BASE_URL}{poster_path}"


def get_registered_tmdb_ids(
    db: Session,
    tmdb_ids: list[int],
) -> set[int]:
    """TMDB 검색 결과 중 이미 movies 테이블에 등록된 ID를 조회한다."""

    # 검색 결과가 없다면 불필요한 DB 쿼리를 실행하지 않는다.
    if not tmdb_ids:
        return set()

    # 영화마다 따로 조회하지 않고 IN 조건으로 등록 여부를 한 번에 확인한다.
    registered_tmdb_ids = db.scalars(
        select(Movie.tmdb_id)
        .where(Movie.tmdb_id.in_(tmdb_ids))
    ).all()

    # 검색 결과에 등록 여부를 빠르게 표시할 수 있도록 set으로 반환한다.
    return {
        tmdb_id
        for tmdb_id in registered_tmdb_ids
        if tmdb_id is not None
    }


async def search_admin_tmdb_movies(
    db: Session,
    query: str,
    page: int = 1,
) -> dict:
    """관리자용 TMDB 영화 검색 결과와 내부 DB 등록 여부를 함께 반환한다."""

    # 검색어 앞뒤의 불필요한 공백을 제거한다.
    normalized_query = query.strip()

    if not normalized_query:
        raise ValueError("검색할 영화 제목을 입력해주세요.")

    # TMDB 검색 API가 허용하는 페이지 범위만 요청한다.
    if page < 1 or page > 500:
        raise ValueError("검색 페이지는 1부터 500 사이여야 합니다.")

    # 기존 TMDB 서비스의 인증 로직을 재사용한다.
    # Access Token이 있으면 헤더 인증을 사용하고, 없으면 API Key를 사용한다.
    auth = get_tmdb_auth()

    if auth is None:
        raise ValueError("TMDB 인증 정보가 설정되지 않았습니다.")

    headers, auth_params = auth

    # 검색 단계에서는 상세 API를 영화마다 호출하지 않고 검색 API 한 번만 사용한다.
    async with httpx.AsyncClient(
        base_url=TMDB_BASE_URL,
        headers=headers,
        timeout=10.0,
    ) as client:
        response = await client.get(
            "/search/movie",
            params={
                **auth_params,
                "query": normalized_query,
                "language": "ko-KR",
                "include_adult": False,
                "page": page,
            },
        )

        # 인증 오류나 TMDB 서버 오류 응답을 예외로 처리한다.
        response.raise_for_status()
        payload = response.json()

    # 예상하지 못한 TMDB 응답 형식이 들어오는 경우를 방어한다.
    if not isinstance(payload, dict):
        raise ValueError("TMDB 검색 응답 형식이 올바르지 않습니다.")

    raw_movies = payload.get("results", [])

    if not isinstance(raw_movies, list):
        raise ValueError("TMDB 영화 검색 결과 형식이 올바르지 않습니다.")

    movies = []

    for raw_movie in raw_movies:
        if not isinstance(raw_movie, dict):
            continue

        tmdb_id = raw_movie.get("id")

        # 이후 등록에 사용할 수 있는 정상적인 TMDB ID가 있는 결과만 포함한다.
        if not isinstance(tmdb_id, int) or tmdb_id <= 0:
            continue

        # TMDB 검색 결과의 개봉일은 일반적으로 YYYY-MM-DD 문자열이다.
        # 개봉일이 없거나 예상 형식이 아닐 수도 있으므로 값을 먼저 확인한 뒤
        # 앞 네 글자가 숫자인 경우에만 프론트에서 사용할 개봉 연도로 변환한다.
        release_date = raw_movie.get("release_date")
        release_year = (
            int(release_date[:4])
            if (
                isinstance(release_date, str)
                and len(release_date) >= 4
                and release_date[:4].isdigit()
            )
            else None
        )

        movies.append(
            {
                "tmdb_id": tmdb_id,
                "title": raw_movie.get("title"),
                "original_title": raw_movie.get("original_title"),
                "release_date": release_date,
                "year": release_year,
                "overview": raw_movie.get("overview"),
                "poster_path": tmdb_image_url(
                    raw_movie.get("poster_path")
                ),
                "vote_average": raw_movie.get("vote_average"),
                "vote_count": raw_movie.get("vote_count"),
                "original_language": raw_movie.get("original_language"),
            }
        )

    # 검색 결과의 TMDB ID만 모아 기존 등록 영화를 DB에서 한 번에 조회한다.
    registered_tmdb_ids = get_registered_tmdb_ids(
        db=db,
        tmdb_ids=[movie["tmdb_id"] for movie in movies],
    )

    # 관리자 화면에서 등록 버튼 활성화 여부를 결정할 수 있도록 표시한다.
    for movie in movies:
        movie["is_registered"] = (
            movie["tmdb_id"] in registered_tmdb_ids
        )

    # 검색 목록과 함께 프론트의 페이지 이동에 필요한 정보도 반환한다.
    return {
        "page": payload.get("page", page),
        "total_pages": payload.get("total_pages", 0),
        "total_results": payload.get("total_results", 0),
        "movies": movies,
    }
