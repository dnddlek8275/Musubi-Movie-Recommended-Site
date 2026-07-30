import re

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from app.models.movies import Movie, MovieGenre

# DB 컬럼/SQL 표현식을 검색용으로 정규화
# lower: 대소문자 차이 제거
# coalesce: NULL 값을 빈 문자열로 처리
# regexp_replace: 모든 공백 제거
def normalize_search_expr(column):
    return func.regexp_replace(func.lower(func.coalesce(column, "")), r"\s+", "", "g")

# 영화 검색 기능 구현
def search_movies_result(
        db : Session,
        search_keyword : str,
        page : int = 1,
        limit : int = 20,
):
    # 검색어 앞뒤 공백 빼기
    search_keyword = search_keyword.strip().lower()
    if search_keyword is None:
        return {
            "state" : "failure",
            "message" : "검색어를 입력해주세요."
        }
    
    # 검색 키워드 내부 공백을 제거한 값
    normalized_keyword = re.sub(r"\s+", "", search_keyword)
    
    # 부분 일치 검색용 패턴
    contains_pattern = f"%{search_keyword}%"
    # 앞부분 일치 검색용 패턴
    startwith_pattern = f"{search_keyword}%"

    # 보정 검색 방식 - 공백 제거 검색어 기준 부분 일치, 앞부분 일치 패턴
    normalized_contains_pattern = f"%{normalized_keyword}%"
    normalized_startwith_pattern = f"{normalized_keyword}%"

    # DB 컬럼 내부 공백을 제거한 값
    title_normalized = normalize_search_expr(Movie.title)
    director_normalized = normalize_search_expr(Movie.director)
    overview_normalized = normalize_search_expr(Movie.overview)

    # 배열 컬럼들 문자열 하나로 합친다.
    cast_text = func.array_to_string(Movie.cast, " ")
    keyword_text = func.array_to_string(Movie.keywords, " ")

    cast_text_normalized = normalize_search_expr(cast_text)
    keyword_text_normalized = normalize_search_expr(keyword_text)
    
    # 장르 테이블에 맞는 영화id 찾는 서브쿼리
    genre_movie_ids = select(MovieGenre.movie_id).where(MovieGenre.genre.ilike(contains_pattern))


    # 관련도 점수
    search_score = (
        # 제목
        case((func.lower(Movie.title) == search_keyword, 100), else_=0)
        # 내부 공백 제거 - 같은 경우
        + case((title_normalized == normalized_keyword, 95), else_=0)
        # 제목이 검색어로 시작하면 
        + case((Movie.title.ilike(startwith_pattern), 80), else_=0)
        # 시작 부분이 같은 경우
        + case((title_normalized.ilike(normalized_startwith_pattern), 75), else_=0)
        # 제목 안에 검색어가 포함 되면 
        + case((Movie.title.ilike(contains_pattern), 60), else_=0)
        + case((title_normalized.ilike(normalized_contains_pattern), 55), else_=0)
        # 감독
        + case((Movie.director.ilike(contains_pattern), 40), else_=0)
        # + case((director_normalized.ilike(normalized_contains_pattern), 35), else_=0)
        # 배우
        + case((cast_text.ilike(contains_pattern), 30), else_=0)
        # + case((cast_text_normalized.ilike(normalized_contains_pattern), 25), else_=0)
        # 장르
        + case((Movie.id.in_(genre_movie_ids), 28), else_=0)
        # 키워드
        + case((keyword_text.ilike(contains_pattern), 20), else_=0)
        # + case((keyword_text_normalized.ilike(normalized_contains_pattern), 15), else_=0)
        # 줄거리
        + case((Movie.overview.ilike(contains_pattern), 10), else_=0)
        # + case((overview_normalized.ilike(normalized_contains_pattern), 5), else_=0)
    ).label("search_score")

    # 검색 조건
    search_condition = (
        select(Movie, search_score)
        .where(
            or_(
                # 기존 검색
                Movie.title.ilike(contains_pattern),
                Movie.overview.ilike(contains_pattern),
                Movie.director.ilike(contains_pattern),
                Movie.language.ilike(contains_pattern),
                cast_text.ilike(contains_pattern),
                keyword_text.ilike(contains_pattern),
                Movie.id.in_(genre_movie_ids),

                # 공백 제거 검색
                title_normalized.ilike(normalized_contains_pattern),
                overview_normalized.ilike(normalized_contains_pattern),
                director_normalized.ilike(normalized_contains_pattern),
                cast_text_normalized.ilike(normalized_contains_pattern),
                keyword_text_normalized.ilike(normalized_contains_pattern),
            )
        )
        # 관련도 높은 순
        .order_by(search_score.desc())
        .offset((page -1 ) * limit)
        .limit(limit)
    )

    result = db.execute(search_condition).all()

    if not result:
        return {
            "state" : "failure",
            "message" : "관련 영화 정보가 없습니다.",
        }
    return {
        "state" : "success",
        "message" : "검색 성공",
        "data" : [
            get_movie_result(movie)
            for movie, score in result
        ]
    }

# 영화 결과 함수
def get_movie_result(movie):
    return {
        "movie_id" : movie.id,
        "title" : movie.title,
        "genres": movie.genres,
        "keyword" : movie.keywords,
        "cast" : movie.cast,
        "poster_path": movie.poster_path,
        "vote_average" : movie.vote_average,
    }
