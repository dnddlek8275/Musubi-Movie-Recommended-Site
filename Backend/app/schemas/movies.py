
from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field


class RecommendRequest(BaseModel):
    user_id: int
    prompt: Optional[str] = None
    genres: List[str] = Field(default_factory=list)


class PreferenceRequest(BaseModel):
    user_id: int


class MovieReviewData(BaseModel):
    id: int
    user_id: int
    nickname: str
    score: float
    comment: str
    is_spoiler: bool = False
    updated_at: datetime
    is_mine: bool = False


class TrailerVideoData(BaseModel):
    url: str
    name: str
    type: str
    official: bool = False


class MovieCastData(BaseModel):
    actor_id: int
    name: str
    character_name: str | None = None
    profile_path: str | None = None


class PersonFilmographyMovieData(BaseModel):
    id: int
    title: str
    poster_path: str | None = None
    genres: list[str] = Field(default_factory=list)
    year: int | None = None
    release_date: date | None = None
    vote_average: float | None = None
    character_name: str | None = None


class PersonFilmographyData(BaseModel):
    id: int | None = None
    name: str
    role: str
    profile_path: str | None = None
    is_liked: bool = False
    movie_count: int = 0
    movies: list[PersonFilmographyMovieData] = Field(default_factory=list)


class PersonFilmographyResponse(BaseModel):
    state: str
    message: str
    data: PersonFilmographyData | None = None
    error: str | None = None


class MovieDetailData(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tmdb_id: int | None = None
    title: str
    overview: str | None = None
    # 예고편이 없거나 TMDB 호출에 실패하면 None이 된다.
    trailer_url: str | None = None
    trailer_videos: list[TrailerVideoData] = Field(default_factory=list)

    genres: list[str] | None = None
    director: str | None = None
    cast: list[str] | None = None
    # 기존 cast 문자열 배열은 추천 로직 호환을 위해 유지하고,
    # 상세 화면에는 이미지·배역명을 포함한 구조화된 출연진 정보를 함께 제공한다.
    cast_details: list[MovieCastData] = Field(default_factory=list)
    keywords: list[str] | None = None
    year: int | None = None
    release_date: date | None = None
    runtime: int | None = None
    production_countries: list[str] | None = None
    certification: str | None = None
    certification_country: str | None = None
    language: str | None = None
    vote_average: float | None = None
    vote_count: int | None = None
    audience_count: int | None = None
    poster_path: str | None = None
    last_synced_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    musubi_rating: float | None = None
    rating_count: int = 0
    my_rating: float | None = None
    my_comment: str | None = None
    my_is_spoiler: bool = False
    reviews: list[MovieReviewData] = Field(default_factory=list)

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


class MovieIdentityRequest(BaseModel):
    expected_movie_id: int = Field(gt=0)
    expected_tmdb_id: int | None = Field(default=None, gt=0)
    expected_title: str = Field(min_length=1, max_length=300)


class MovieRatingRequest(MovieIdentityRequest):
    score: float = Field(ge=0.5, le=5, multiple_of=0.5)
    comment: str | None = Field(default=None, max_length=500)
    is_spoiler: bool = False

class ShowMovie(BaseModel):
    movie_id: int
    title: str
    poster_path: str | None = None
    genres: list[str] | None = None
    vote_average: float | None = None
    year: int | None = None
    release_date: date | None = None

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
