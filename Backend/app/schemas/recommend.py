from pydantic import BaseModel, Field


class RecommendRequest(BaseModel):
    # 사용자가 입력한 추천 요청 문장
    message: str = Field(..., min_length=1)
    # 캐릭터
    character: str | None = None
    # 장르
    genre: str | None = None
    # 배우
    actor: str | None = None
    # 감독
    director: str | None = None
    # 언어
    language: str | None = None
    # 개봉연도
    year_from: int | None = None
    # 개봉연도
    year_to: int | None = None
    # 최소 평점
    min_rating: float | None = None
    # 추천받을 영화 개수
    limit: int = Field(default=3, ge=1, le=10)


class RecommendedMovie(BaseModel):
    # DB 내부 영화 ID
    movie_id: int
    # 영화 제목
    title: str
    # 개봉연도
    year: int | None = None
    # 대표 장르
    genre: str | None = None
    # 평점
    rating: float | None = None
    # 영화 설명
    description: str | None = None
    # 프론트 카드에 보여줄 포스터 전체 URL
    poster_url: str | None = None
    # 왜 추천했는지 보여줄 짧은 이유
    reason: str | None = None

class TodayRecommendationData(BaseModel):
    # 카드 상단에 보여줄 AI 추천 문장입니다.
    answer: str
    # 추천 영화 목록입니다. 메인은 기본 1개만 쓰면 됩니다.
    movies: list[RecommendedMovie] = Field(default_factory=list)
