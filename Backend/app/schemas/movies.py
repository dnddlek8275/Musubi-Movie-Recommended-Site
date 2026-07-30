
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field


class RecommendRequest(BaseModel):
    user_id: int
    prompt: Optional[str] = None
    genres: List[str] = Field(default_factory=list)


class PreferenceRequest(BaseModel):
    user_id: int

class MovieDetailData(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tmdb_id: int | None = None
    title: str
    overview: str | None = None
    # 예고편이 없거나 TMDB 호출에 실패하면 None이 된다.
    trailer_url: str | None = None

    genres: list[str] | None = None
    director: str | None = None
    cast: list[str] | None = None
    keywords: list[str] | None = None
    year: int | None = None
    language: str | None = None
    vote_average: float | None = None
    vote_count: int | None = None
    audience_count: int | None = None
    poster_path: str | None = None
    last_synced_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def movie_id(self) -> int:
        # 프론트에서 movie_id라는 이름을 쓰고 있다면 같이 내려준다.
        return self.id

class MovieDetailResponse(BaseModel):
    # 상세 조회 API 전체 응답 구조
    state: str
    message: str
    data: MovieDetailData | None = None
    error: str | None = None

class ShowMovie(BaseModel):
    movie_id: int
    title: str
    poster_path: str | None = None
    genres: list[str] | None = None
    vote_average: float | None = None

class RecommendMovie(ShowMovie):
    recommendation_score: float
    reason: str

class RecommendResponse(BaseModel):
    state: str
    message: str
    data: list[RecommendMovie]

# 영화 목록 API의 공통 성공·실패·예외 응답 구조를 정의한다.
class ShowMovies(BaseModel):
    state : str
    message : str
    data : list[ShowMovie] | None = None
    error : str | None = None
