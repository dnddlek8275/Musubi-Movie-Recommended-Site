#!/usr/bin/env python3
"""Audit title-suspected R/unrated movies against live TMDB metadata."""

from __future__ import annotations

import argparse
import asyncio
import re

import httpx
from sqlalchemy import or_, select
from sqlalchemy.engine import make_url

from app.core.config import settings
from app.core.dependencies import SessionLocal
from app.models.movies import Movie
from app.services.admin.tmdb_search_service import TMDB_BASE_URL
from app.services.movies.tmdb_trailer_service import get_tmdb_auth


LOCAL_DB_HOSTS = {"db", "localhost", "127.0.0.1", "::1"}
TITLE_PATTERN = re.compile(
    r"sex|erotic|porn|xxx|x-rated|adult|nude|naked|bikini|swapp|wife|wives|mother.in.law|"
    r"sister.in.law|daughter.in.law|mistress|orgy|massage|playboy|hooker|"
    r"prostitut|seduction|lust|boob| 성인|에로|정사|섹스|야동|룸싸롱|안마|"
    r"스와핑|처제|며느리|장모|새엄마|엄마애인|여대생|유부녀|애마부인|"
    r"젖소|맛있는|초대남|엄마학개론",
    re.IGNORECASE,
)
EXPLICIT_KEYWORDS = {
    "adult filmmaking",
    "adult video",
    "erotic",
    "erotic movie",
    "eroticism",
    "hardcore",
    "nude modeling",
    "nudistploitation",
    "porn",
    "porn actress",
    "porn film",
    "porn industry",
    "porn star",
    "porno",
    "pornography",
    "sex club",
    "sex party",
    "sexploitation",
    "sleaze",
    "softcore",
    # 2차 엄격 모드: 노골적인 영상물뿐 아니라 성적 소재가 작품의 중심인
    # 극영화·다큐멘터리·교육 영상도 추천 DB에서 제외한다.
    "anal sex",
    "brothel",
    "casual sex",
    "escort girl",
    "female nudity",
    "group sex",
    "interracial sex",
    "lesbian sex",
    "nude photography",
    "nudism",
    "nudist",
    "naturism",
    "nymphomaniac",
    "orgy",
    "prostitute",
    "prostitution",
    "rough sex",
    "sex",
    "sex addiction",
    "sex club",
    "sex comedy",
    "sex education",
    "sex party",
    "sex scene",
    "sex worker",
    "sexual encounter",
    "sexual exploration",
    "sexual fantasy",
    "sexual revolution",
    "sexuality",
    "stripper",
    "swinger",
    "swinging",
    "threesome",
}
HIGH_CONFIDENCE_ADULT_KEYWORDS = {
    "adult video",
    "erotic movie",
    "hardcore",
    "porn film",
    "softcore",
}
RECOMMENDATION_EXCLUSION_KEYWORDS = {
    "adult filmmaking",
    "adult video",
    "erotic movie",
    "hardcore",
    "nudistploitation",
    "porn",
    "porn actress",
    "porn film",
    "porn industry",
    "porn star",
    "porno",
    "pornography",
    "sexploitation",
    "softcore",
}
EXPLOITATION_KEYWORDS = {"nudistploitation", "sexploitation"}
ADULT_INDUSTRY_KEYWORDS = {
    "adult filmmaking",
    "adult video",
    "porn",
    "porn actress",
    "porn film",
    "porn industry",
    "porn star",
    "porno",
    "pornography",
}
HIGH_CONFIDENCE_ADULT_TITLE_PATTERN = re.compile(
    r"\b(?:porn|porno)\b|포르노|x-rated.*adult|sexipede",
    re.IGNORECASE,
)
SAFE_CERTIFICATIONS = {
    "KR": {"ALL", "전체관람가", "전체 관람가", "12", "12세 이상 관람가", "12세이상관람가", "12세 관람가", "15", "15세 이상 관람가", "15세이상관람가", "15세 관람가", "15세관람가"},
    "US": {"G", "PG", "PG-13"},
}
ADULT_OVERVIEW_PATTERN = re.compile(
    r"\b(?:adult films?|adult film stars?|adult performers?|softcore|"
    r"porn(?:ography|ographic)?|erotic(?:a| film)?|nudists?|nudism|"
    r"nude models?|sex workers?|sex club|sex party|sexual fantasy|sexual adventure|"
    r"prostitut(?:e|es|ion)|strip club|swingers?)\b"
    r"|노골적으로.{0,30}정사를 나누|(?:몸|육체)을 탐닉|새엄마와의 금지된 사랑",
    re.IGNORECASE,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--allow-nonlocal", action="store_true")
    return parser.parse_args()


def has_verified_safe_rating(movie: Movie) -> bool:
    country = (movie.certification_country or "").strip().upper()
    certification = (movie.certification or "").strip().upper()
    return certification in SAFE_CERTIFICATIONS.get(country, set())


async def fetch_detail(
    client: httpx.AsyncClient,
    params: dict[str, str],
    semaphore: asyncio.Semaphore,
    movie: Movie,
) -> tuple[Movie, dict | None, str | None]:
    async with semaphore:
        try:
            response = await client.get(
                f"/movie/{movie.tmdb_id}",
                params={**params, "language": "en-US", "append_to_response": "keywords"},
            )
            response.raise_for_status()
            return movie, response.json(), None
        except (httpx.HTTPError, ValueError) as error:
            return movie, None, str(error)


async def main() -> None:
    args = parse_args()
    database_host = make_url(settings.DATABASE_URL).host
    if not args.allow_nonlocal and database_host not in LOCAL_DB_HOSTS:
        raise SystemExit(f"Refusing to audit non-local DB host {database_host!r}.")
    auth = get_tmdb_auth()
    if auth is None:
        raise SystemExit("TMDB authentication is missing.")
    headers, params = auth

    with SessionLocal() as session:
        review_movies = list(
            session.scalars(
                select(Movie).where(
                    Movie.tmdb_id.is_not(None),
                    or_(
                        Movie.keywords.op("&&")(list(RECOMMENDATION_EXCLUSION_KEYWORDS)),
                        Movie.certification.is_(None),
                        Movie.certification == "",
                        (Movie.certification_country == "US")
                        & (Movie.certification.in_(["R", "NR", "NC-17", "X"])),
                    ),
                )
            ).all()
        )
        suspects = [
            movie for movie in review_movies
            if TITLE_PATTERN.search(movie.title)
            or {
                str(keyword).strip().casefold()
                for keyword in (movie.keywords or [])
            } & RECOMMENDATION_EXCLUSION_KEYWORDS
        ]
        semaphore = asyncio.Semaphore(12)
        async with httpx.AsyncClient(
            base_url=TMDB_BASE_URL, headers=headers, timeout=30.0
        ) as client:
            rows = await asyncio.gather(
                *(fetch_detail(client, params, semaphore, movie) for movie in suspects)
            )

        confirmed: list[tuple[Movie, list[str], bool]] = []
        failures = 0
        for movie, detail, error in rows:
            if error or detail is None:
                failures += 1
                continue
            keyword_rows = detail.get("keywords", {}).get("keywords", [])
            keywords = {
                str(item.get("name") or "").strip().casefold()
                for item in keyword_rows
                if isinstance(item, dict)
            }
            stored_keywords = {
                str(keyword).strip().casefold()
                for keyword in (movie.keywords or [])
            }
            evidence = [
                f"stored:{value}"
                for value in sorted(stored_keywords & RECOMMENDATION_EXCLUSION_KEYWORDS)
            ]
            if HIGH_CONFIDENCE_ADULT_TITLE_PATTERN.search(movie.title):
                evidence.append("title:explicit-adult-title")
            evidence.extend(
                f"live:{value}"
                for value in sorted(keywords & RECOMMENDATION_EXCLUSION_KEYWORDS)
            )
            overview = str(detail.get("overview") or "")
            overview_matches = sorted({
                match.group(0).casefold()
                for match in ADULT_OVERVIEW_PATTERN.finditer(overview)
            })
            evidence.extend(f"overview:{value}" for value in overview_matches)
            adult = detail.get("adult") is True
            all_keywords = stored_keywords | keywords
            genres = {
                str(genre).strip().casefold()
                for genre in (movie.genres or [])
            }
            is_documentary = bool(genres & {"documentary", "다큐멘터리"})
            policy_match = (
                adult
                or bool(HIGH_CONFIDENCE_ADULT_TITLE_PATTERN.search(movie.title))
                or bool(all_keywords & HIGH_CONFIDENCE_ADULT_KEYWORDS)
                or bool(all_keywords & EXPLOITATION_KEYWORDS)
                or (is_documentary and bool(all_keywords & ADULT_INDUSTRY_KEYWORDS))
            )
            if policy_match and not has_verified_safe_rating(movie):
                confirmed.append((movie, evidence, adult))

        print(
            f"reviewed={len(review_movies)}, title_suspects={len(suspects)}, "
            f"confirmed={len(confirmed)}, failures={failures}"
        )
        for movie, evidence, adult in confirmed:
            print(
                f"  - id={movie.id}, tmdb_id={movie.tmdb_id}, title={movie.title}, "
                f"adult={adult}, keywords={evidence}"
            )
        if not args.apply:
            print("Dry-run complete. Re-run with --apply to delete confirmed movies.")
            return

        confirmed_ids = [movie.id for movie, _, _ in confirmed]
        for movie in session.scalars(select(Movie).where(Movie.id.in_(confirmed_ids))):
            session.delete(movie)
        session.commit()
        print(f"Delete complete: deleted={len(confirmed_ids)}")


if __name__ == "__main__":
    asyncio.run(main())
