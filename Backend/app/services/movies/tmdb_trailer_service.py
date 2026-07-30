import logging
import re
from typing import Any

import httpx

from app.core.config import settings


logger = logging.getLogger(__name__)

# TMDB API 기본 주소
TMDB_BASE_URL = "https://api.themoviedb.org/3"

# 사이트 내부 iframe에서 사용할 YouTube 주소
YOUTUBE_EMBED_BASE_URL = "https://www.youtube.com/embed"

# 일반적인 YouTube 영상 ID는 영문, 숫자, -, _로 구성된 11자리다.
# TMDB에서 받은 key를 URL에 넣기 전에 형식을 검사한다.
YOUTUBE_KEY_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")


def get_tmdb_auth() -> tuple[dict[str, str], dict[str, str]] | None:
    """
    현재 환경변수에 설정된 인증 방식에 맞춰
    TMDB 요청용 헤더와 쿼리 파라미터를 만든다.
    """

    # 모든 TMDB 요청에 사용할 기본 헤더
    headers = {
        "accept": "application/json",
    }

    # API Key를 사용하는 경우 쿼리 파라미터에 들어간다.
    params: dict[str, str] = {}

    if settings.TMDB_ACCESS_TOKEN:
        # Access Token이 있으면 Authorization 헤더 방식 사용
        headers["Authorization"] = (
            f"Bearer {settings.TMDB_ACCESS_TOKEN}"
        )

    elif settings.TMDB_API_KEY:
        # Access Token이 없으면 기존 API Key 방식 사용
        params["api_key"] = settings.TMDB_API_KEY

    else:
        # 인증 정보가 없으면 TMDB를 호출할 수 없다.
        return None

    return headers, params


def select_youtube_trailer(
    videos: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """
    TMDB가 반환한 여러 영상 중 사이트에서 재생할
    YouTube Trailer 한 개를 선택한다.
    """

    trailers = [
        video
        for video in videos
        # YouTube 영상만 사용한다.
        if video.get("site") == "YouTube"

        # Teaser, Clip, Featurette 등이 아닌 Trailer만 사용한다.
        and video.get("type") == "Trailer"

        # key가 문자열인지 확인한다.
        and isinstance(video.get("key"), str)

        # iframe URL에 사용할 수 있는 YouTube ID 형식인지 확인한다.
        and YOUTUBE_KEY_PATTERN.fullmatch(video["key"])
    ]

    if not trailers:
        # 조건에 맞는 영상이 없다.
        return None

    # official=True인 공식 영상을 우선한다.
    # 공식 여부가 같으면 published_at이 최근인 영상을 선택한다.
    return max(
        trailers,
        key=lambda video: (
            video.get("official") is True,
            video.get("published_at") or "",
        ),
    )


async def get_movie_trailer_url(
    tmdb_id: int | None,
) -> str | None:
    """
    영화의 TMDB ID를 이용해 예고편을 조회하고
    YouTube iframe용 embed URL을 반환한다.

    예고편이 없거나 TMDB 요청이 실패하면 None을 반환한다.
    """

    # DB 영화에 tmdb_id가 없으면 조회할 수 없다.
    if tmdb_id is None or tmdb_id <= 0:
        return None

    auth = get_tmdb_auth()

    # TMDB 인증 정보가 없더라도 영화 상세 API가
    # 실패하지 않도록 None만 반환한다.
    if auth is None:
        return None

    headers, auth_params = auth

    # 동기 httpx.Client가 아닌 AsyncClient를 사용한다.
    # 현재 영화 상세 엔드포인트가 async 함수이기 때문이다.
    async with httpx.AsyncClient(
        base_url=TMDB_BASE_URL,
        headers=headers,
        timeout=5.0,
    ) as client:

        # 한국어 예고편을 먼저 찾는다.
        # 한국어 결과가 없으면 영어 결과로 다시 조회한다.
        for language in ("ko-KR", "en-US"):
            try:
                response = await client.get(
                    f"/movie/{tmdb_id}/videos",
                    params={
                        **auth_params,
                        "language": language,
                    },
                )

                # 400, 401, 404, 500 등의 응답을 예외로 처리한다.
                response.raise_for_status()

                # TMDB JSON 응답을 파이썬 객체로 변환한다.
                payload = response.json()

            except (httpx.HTTPError, ValueError) as exc:
                # TMDB 오류 때문에 영화 상세 조회 전체가 실패하면 안 된다.
                # 현재 언어 조회가 실패하면 다음 언어를 시도한다.
                logger.warning(
                    "TMDB 예고편 조회 실패: "
                    "tmdb_id=%s language=%s error=%s",
                    tmdb_id,
                    language,
                    exc,
                )
                continue

            # 예상하지 못한 응답 형식 방어
            if not isinstance(payload, dict):
                continue

            results = payload.get("results", [])

            if not isinstance(results, list):
                continue

            # results 안에 잘못된 자료형이 들어올 가능성을 방어한다.
            valid_results = [
                video
                for video in results
                if isinstance(video, dict)
            ]

            # YouTube Trailer 선택
            trailer = select_youtube_trailer(valid_results)

            if trailer is not None:
                video_key = trailer["key"]

                # 프론트 iframe의 src에 바로 사용할 수 있는 주소 반환
                return (
                    f"{YOUTUBE_EMBED_BASE_URL}/{video_key}"
                )

    # 한국어와 영어 응답 모두 예고편이 없는 경우
    return None