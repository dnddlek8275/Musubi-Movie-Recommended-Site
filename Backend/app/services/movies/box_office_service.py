from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.movies import Movie, MovieStats
from app.models.ranking import DailyBoxOfficeRanking, KobisMovieMapping
from app.services.admin.movie_service import (
    normalize_string_list,
    sync_admin_movie_actors,
    sync_admin_movie_genres,
)
from app.services.admin.tmdb_register_service import (
    fetch_admin_tmdb_movie_detail,
    require_non_explicit_metadata,
)
from app.services.admin.tmdb_search_service import search_admin_tmdb_movies
from app.services.movies.genre_relevance import sync_movie_genre_weights
from app.services.movies.vector_sync_service import enqueue_movie_vector_sync


KST = ZoneInfo("Asia/Seoul")
KOBIS_DAILY_BOX_OFFICE_URL = (
    "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/"
    "searchDailyBoxOfficeList.json"
)
KOBIS_MOVIE_INFO_URL = (
    "https://www.kobis.or.kr/kobisopenapi/webservice/rest/movie/"
    "searchMovieInfo.json"
)
KOBIS_DAILY_SITE_URL = (
    "https://kobis.or.kr/kobis/business/main/searchMainDailySeatTicket.do"
)
KOBIS_REFRESH_LOCK_ID = 2026080701
KOBIS_COUNTRY_CODES = {
    "한국": "KR", "미국": "US", "일본": "JP", "영국": "GB",
    "프랑스": "FR", "독일": "DE", "중국": "CN", "캐나다": "CA",
    "호주": "AU", "이탈리아": "IT", "스페인": "ES",
    "남아프리카공화국": "ZA",
}


def normalize_movie_title(value: str | None) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return re.sub(r"[^0-9a-z가-힣]", "", normalized)


def parse_kobis_date(value: str | None) -> date | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    for date_format in ("%Y%m%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, date_format).date()
        except ValueError:
            continue
    return None


def parse_integer(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalized_people(values: list[str]) -> set[str]:
    return {normalize_movie_title(value) for value in values if value}


def build_kobis_match_evidence(
    movie: Movie,
    kobis_detail: dict,
    open_date: date | None,
) -> dict:
    kobis_titles = [kobis_detail.get("movieNm"), kobis_detail.get("movieNmEn")]
    title_match = normalize_movie_title(movie.title) in {
        normalize_movie_title(title) for title in kobis_titles if title
    }
    kobis_production_year = parse_integer(kobis_detail.get("prdtYear"))
    movie_year = movie.release_date.year if movie.release_date else movie.year
    year_match = bool(
        movie_year
        and (
            movie_year == kobis_production_year
            if kobis_production_year
            else open_date is not None and movie_year == open_date.year
        )
    )
    kobis_directors = [
        name
        for director in (kobis_detail.get("directors") or [])
        if isinstance(director, dict)
        for name in (director.get("peopleNm"), director.get("peopleNmEn"))
        if name
    ]
    director_match = bool(
        movie.director
        and _normalized_people([movie.director]) & _normalized_people(kobis_directors)
    )
    kobis_runtime = parse_integer(kobis_detail.get("showTm"))
    runtime_match = bool(
        movie.runtime and kobis_runtime and abs(movie.runtime - kobis_runtime) <= 2
    )
    kobis_countries = {
        KOBIS_COUNTRY_CODES.get(str(item.get("nationNm") or "").strip())
        for item in (kobis_detail.get("nations") or [])
        if isinstance(item, dict)
    } - {None}
    country_match = bool(set(movie.production_countries or []) & kobis_countries)
    metadata_matches = sum((director_match, runtime_match, country_match))
    return {
        "title_match": title_match,
        "year_match": year_match,
        "director_match": director_match,
        "runtime_match": runtime_match,
        "country_match": country_match,
        "metadata_matches": metadata_matches,
        "high_confidence": title_match and year_match and metadata_matches >= 2,
    }


def match_kobis_movie(
    movies_by_title: dict[str, list[Movie]],
    movie_name: str,
    open_date: date | None,
) -> Movie | None:
    candidates = movies_by_title.get(normalize_movie_title(movie_name), [])
    if not candidates:
        return None
    if open_date is not None:
        exact = [movie for movie in candidates if movie.release_date == open_date]
        if len(exact) == 1:
            return exact[0]
        same_year = [
            movie for movie in candidates
            if movie.release_date and movie.release_date.year == open_date.year
        ]
        if len(same_year) == 1:
            return same_year[0]
        year_only = [movie for movie in candidates if movie.year == open_date.year]
        if len(year_only) == 1:
            return year_only[0]
    return candidates[0] if len(candidates) == 1 else None


def select_registered_tmdb_match(
    search_results: list[dict],
    movie_name: str,
    open_date: date | None,
) -> int | None:
    """KOBIS 한글 제목을 등록된 TMDB 영화 ID에 보수적으로 연결한다."""
    normalized_name = normalize_movie_title(movie_name)
    candidates = []
    for result in search_results:
        if not result.get("is_registered"):
            continue
        titles = (result.get("title"), result.get("original_title"))
        if normalized_name not in {normalize_movie_title(title) for title in titles}:
            continue
        if open_date is not None and result.get("year") != open_date.year:
            continue
        tmdb_id = result.get("tmdb_id")
        if isinstance(tmdb_id, int):
            candidates.append(tmdb_id)
    unique_ids = list(dict.fromkeys(candidates))
    return unique_ids[0] if len(unique_ids) == 1 else None


async def match_kobis_movie_via_tmdb(
    db: Session,
    movie_name: str,
    open_date: date | None,
    kobis_detail: dict,
) -> tuple[Movie | None, dict | None]:
    """직접 제목 매칭 실패 시 TMDB의 한국어 제목과 기존 tmdb_id를 대조한다."""
    try:
        result = await search_admin_tmdb_movies(db, movie_name)
    except (httpx.HTTPError, ValueError):
        # 보조 TMDB 검색 실패가 KOBIS 원본 순위 저장까지 막아서는 안 된다.
        return None, None
    search_results = result.get("movies") or []
    tmdb_id = select_registered_tmdb_match(
        search_results, movie_name, open_date
    )
    if tmdb_id is None:
        kobis_year = parse_integer(kobis_detail.get("prdtYear"))
        normalized_name = normalize_movie_title(movie_name)
        new_candidates = [
            item for item in search_results
            if not item.get("is_registered")
            and normalized_name in {
                normalize_movie_title(item.get("title")),
                normalize_movie_title(item.get("original_title")),
            }
            and (not kobis_year or item.get("year") == kobis_year)
        ]
        if len(new_candidates) != 1:
            return None, None
        try:
            data = await fetch_admin_tmdb_movie_detail(new_candidates[0]["tmdb_id"])
        except (httpx.HTTPError, ValueError):
            return None, None
        candidate = Movie(
            title=data.get("title") or "",
            release_date=data.get("release_date"),
            year=data.get("year"),
            director=data.get("director"),
            runtime=data.get("runtime"),
            production_countries=data.get("production_countries") or [],
        )
        evidence = build_kobis_match_evidence(candidate, kobis_detail, open_date)
        if not evidence["high_confidence"]:
            return None, evidence
        return create_tmdb_box_office_movie(db, data), evidence
    movie = db.scalar(select(Movie).where(Movie.tmdb_id == tmdb_id))
    if movie is None:
        return None, None
    evidence = build_kobis_match_evidence(movie, kobis_detail, open_date)
    return (movie, evidence) if evidence["high_confidence"] else (None, evidence)


def create_tmdb_box_office_movie(db: Session, data: dict) -> Movie:
    """투표 수와 무관하게 검증된 박스오피스 TMDB 영화를 시스템 등록한다."""
    values = data.copy()
    cast_credits = values.pop("cast_credits", [])
    genres = normalize_string_list(values.pop("genres", []))
    values["cast"] = normalize_string_list(values.get("cast"))
    values["keywords"] = normalize_string_list(values.get("keywords"))
    allowed = {
        "tmdb_id", "title", "overview", "director", "cast", "keywords",
        "year", "release_date", "runtime", "production_countries",
        "certification", "certification_country", "language", "vote_average",
        "vote_count", "audience_count", "poster_path", "last_synced_at",
    }
    movie = Movie(**{key: value for key, value in values.items() if key in allowed}, genres=[])
    db.add(movie)
    db.flush()
    db.add(MovieStats(movie_id=movie.id))
    sync_admin_movie_genres(db, movie, genres)
    sync_movie_genre_weights(db, movie)
    sync_admin_movie_actors(db, movie, cast_credits)
    enqueue_movie_vector_sync(
        db, tmdb_id=movie.tmdb_id, movie_id=movie.id, operation="upsert"
    )
    return movie


async def fetch_kobis_movie_info(movie_code: str) -> dict:
    async with httpx.AsyncClient(timeout=settings.KOBIS_TIMEOUT_SECONDS) as client:
        response = await client.get(
            KOBIS_MOVIE_INFO_URL,
            params={"key": settings.KOBIS_API_KEY, "movieCd": movie_code},
        )
        response.raise_for_status()
        payload = response.json()
    detail = payload.get("movieInfoResult", {}).get("movieInfo", {})
    return detail if isinstance(detail, dict) else {}


async def fetch_kobis_site_metadata() -> dict[str, dict]:
    """KOBIS 공개 일별 목록에서 오픈 API에 없는 포스터 경로를 보충한다."""
    try:
        async with httpx.AsyncClient(timeout=settings.KOBIS_TIMEOUT_SECONDS) as client:
            response = await client.get(KOBIS_DAILY_SITE_URL)
            response.raise_for_status()
            rows = response.json()
    except (httpx.HTTPError, ValueError):
        return {}
    if not isinstance(rows, list):
        return {}
    return {
        str(row.get("movieCd")): row
        for row in rows
        if isinstance(row, dict) and row.get("movieCd")
    }


def create_kobis_only_movie(
    db: Session,
    movie_code: str,
    detail: dict,
    site_metadata: dict,
    audience_count: int | None,
) -> Movie | None:
    """TMDB에 없는 안전한 작품을 KOBIS 메타데이터만으로 최소 등록한다."""
    title = str(detail.get("movieNm") or "").strip()
    open_date = parse_kobis_date(detail.get("openDt"))
    production_year = parse_integer(detail.get("prdtYear"))
    genres = [
        str(item.get("genreNm") or "").strip()
        for item in (detail.get("genres") or [])
        if isinstance(item, dict) and item.get("genreNm")
    ]
    audits = detail.get("audits") or []
    certification = next(
        (str(item.get("watchGradeNm") or "").strip() for item in audits
         if isinstance(item, dict) and item.get("watchGradeNm")),
        None,
    )
    # KOBIS에는 TMDB adult 플래그가 없으므로 청소년관람불가 작품은 자동 등록하지 않는다.
    if not title or certification == "청소년관람불가":
        return None
    require_non_explicit_metadata(
        [], certification, "KR", None, title, genres
    )
    file_location = str(site_metadata.get("fileSaveLoct") or "").strip()
    system_filename = str(site_metadata.get("sysFileNm") or "").strip()
    original_path = (
        f"{file_location.rstrip('/')}/{system_filename}"
        if file_location and system_filename
        else ""
    )
    thumb_path = str(site_metadata.get("thumbUrl") or "").strip()
    image_path = original_path or thumb_path
    if not image_path:
        return None
    poster_path = (
        image_path if image_path.startswith(("http://", "https://"))
        else f"https://kobis.or.kr{image_path}"
    )
    directors = [
        str(item.get("peopleNm") or item.get("peopleNmEn") or "").strip()
        for item in (detail.get("directors") or [])
        if isinstance(item, dict)
        and (item.get("peopleNm") or item.get("peopleNmEn"))
    ]
    cast = [
        str(item.get("peopleNm") or item.get("peopleNmEn") or "").strip()
        for item in (detail.get("actors") or [])[:10]
        if isinstance(item, dict)
        and (item.get("peopleNm") or item.get("peopleNmEn"))
    ]
    countries = list(dict.fromkeys(
        code
        for item in (detail.get("nations") or [])
        if isinstance(item, dict)
        for code in [KOBIS_COUNTRY_CODES.get(str(item.get("nationNm") or "").strip())]
        if code
    ))
    movie = Movie(
        title=title,
        overview=None,
        genres=[],
        director=", ".join(directors) or None,
        cast=cast,
        keywords=[],
        year=production_year or (open_date.year if open_date else None),
        release_date=open_date,
        runtime=parse_integer(detail.get("showTm")),
        production_countries=countries,
        certification=certification,
        certification_country="KR" if certification else None,
        audience_count=audience_count,
        poster_path=poster_path,
    )
    db.add(movie)
    db.flush()
    db.add(MovieStats(movie_id=movie.id))
    sync_admin_movie_genres(db, movie, genres)
    sync_movie_genre_weights(db, movie)
    db.add(KobisMovieMapping(
        kobis_movie_code=movie_code,
        movie_id=movie.id,
        tmdb_id=None,
        match_method="kobis_only",
        evidence={"source": "KOBIS", "recommendation_confidence": "low"},
    ))
    return movie


async def fetch_kobis_daily_box_office(target_date: date) -> list[dict]:
    if not settings.KOBIS_API_KEY:
        return []
    async with httpx.AsyncClient(timeout=settings.KOBIS_TIMEOUT_SECONDS) as client:
        response = await client.get(
            KOBIS_DAILY_BOX_OFFICE_URL,
            params={
                "key": settings.KOBIS_API_KEY,
                "targetDt": target_date.strftime("%Y%m%d"),
            },
        )
        response.raise_for_status()
        payload = response.json()
    result = payload.get("boxOfficeResult", {}).get("dailyBoxOfficeList", [])
    return result if isinstance(result, list) else []


async def refresh_daily_box_office(
    db: Session,
    target_date: date | None = None,
    *,
    force: bool = False,
) -> int:
    target_date = target_date or (datetime.now(KST).date() - timedelta(days=1))
    if not settings.KOBIS_API_KEY:
        return 0
    lock_acquired = bool(
        db.scalar(
            text("SELECT pg_try_advisory_xact_lock(:lock_id)"),
            {"lock_id": KOBIS_REFRESH_LOCK_ID},
        )
    )
    if not lock_acquired:
        return 0
    try:
        existing_count = db.scalar(
            select(func.count())
            .select_from(DailyBoxOfficeRanking)
            .where(DailyBoxOfficeRanking.box_office_date == target_date)
        )
        if existing_count and not force:
            return int(existing_count)

        rows = await fetch_kobis_daily_box_office(target_date)
        if not rows:
            return 0
        site_metadata_by_code = await fetch_kobis_site_metadata()

        movies_by_title: dict[str, list[Movie]] = defaultdict(list)
        for movie in db.scalars(select(Movie).where(Movie.tmdb_id.is_not(None))):
            movies_by_title[normalize_movie_title(movie.title)].append(movie)

        parsed_rows = []
        for row in rows[:10]:
            rank = parse_integer(row.get("rank"))
            movie_code = str(row.get("movieCd") or "").strip()
            movie_name = str(row.get("movieNm") or "").strip()
            if not rank or not movie_code or not movie_name:
                continue
            open_date = parse_kobis_date(row.get("openDt"))
            saved_mapping = db.get(KobisMovieMapping, movie_code)
            matched_movie = saved_mapping.movie if saved_mapping else None
            evidence = saved_mapping.evidence if saved_mapping else None
            try:
                kobis_detail = await fetch_kobis_movie_info(movie_code)
            except (httpx.HTTPError, ValueError):
                kobis_detail = {}
            direct_candidate = match_kobis_movie(movies_by_title, movie_name, open_date)
            if matched_movie is None and direct_candidate is not None and kobis_detail:
                candidate_evidence = build_kobis_match_evidence(
                    direct_candidate, kobis_detail, open_date
                )
                if candidate_evidence["high_confidence"]:
                    matched_movie = direct_candidate
                    evidence = candidate_evidence
            if matched_movie is None:
                matched_movie, evidence = await match_kobis_movie_via_tmdb(
                    db, movie_name, open_date, kobis_detail
                )
            if matched_movie is None and kobis_detail:
                matched_movie = create_kobis_only_movie(
                    db,
                    movie_code,
                    kobis_detail,
                    site_metadata_by_code.get(movie_code, {}),
                    parse_integer(row.get("audiAcc")),
                )
            if (
                matched_movie is not None
                and matched_movie.tmdb_id is not None
                and saved_mapping is None
            ):
                if db.get(KobisMovieMapping, movie_code) is None:
                    db.add(KobisMovieMapping(
                        kobis_movie_code=movie_code,
                        movie_id=matched_movie.id,
                        tmdb_id=matched_movie.tmdb_id,
                        match_method="metadata_auto",
                        evidence=evidence or {},
                    ))
            parsed_rows.append(
                DailyBoxOfficeRanking(
                    box_office_date=target_date,
                    kobis_movie_code=movie_code,
                    rank=rank,
                    movie_id=matched_movie.id if matched_movie else None,
                    movie_name=movie_name,
                    open_date=open_date,
                    audience_count=parse_integer(row.get("audiCnt")),
                    cumulative_audience_count=parse_integer(row.get("audiAcc")),
                )
            )
        if not parsed_rows:
            return 0

        db.execute(
            delete(DailyBoxOfficeRanking).where(
                DailyBoxOfficeRanking.box_office_date == target_date
            )
        )
        db.add_all(parsed_rows)
        db.commit()
        return len(parsed_rows)
    except Exception:
        db.rollback()
        raise


def latest_box_office_rows(db: Session) -> list[DailyBoxOfficeRanking]:
    latest_date = db.scalar(select(func.max(DailyBoxOfficeRanking.box_office_date)))
    if latest_date is None:
        return []
    return list(
        db.scalars(
            select(DailyBoxOfficeRanking)
            .where(DailyBoxOfficeRanking.box_office_date == latest_date)
            .order_by(DailyBoxOfficeRanking.rank)
        ).all()
    )
