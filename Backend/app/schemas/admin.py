from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, model_validator


# 장르명은 movie_genres.genre 컬럼 크기에 맞춰 최대 50자로 제한한다.
# 앞뒤 공백을 제거하고 공백만 있는 값은 허용하지 않는다.
GenreName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=50),
]

# 배우 또는 성우 이름의 앞뒤 공백을 제거하고 최대 100자로 제한한다.
CastName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
]

# 검색과 추천에 사용하는 키워드도 빈 값과 지나치게 긴 값을 차단한다.
KeywordName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
]


# 관리자 부여
class AdminRoleUpdateRequest(BaseModel):
    email : EmailStr
    is_admin: bool


class AdminManualMovieCreateRequest(BaseModel):
    """TMDB에서 찾을 수 없는 영화를 관리자가 직접 등록하는 요청 형식이다.

    TMDB 영화가 아니므로 TMDB ID, TMDB 평점, TMDB 투표 수와 마지막
    동기화 시각은 요청받지 않는다. 포스터도 별도 업로드 API를 통해
    등록할 예정이므로 현재 요청 스키마에서는 제외한다.
    """

    # 스키마에 정의하지 않은 tmdb_id, vote_average, poster_path 같은 필드가
    # 들어오면 무시하지 않고 422 오류로 처리해 임의 데이터 저장을 막는다.
    model_config = ConfigDict(extra="forbid")

    # 제목의 앞뒤 공백을 제거한 뒤 1자 이상, 300자 이하인지 검사한다.
    title: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=300),
    ] = Field(description="영화 제목")

    # 줄거리를 모르는 경우 생략할 수 있으며 지나치게 큰 요청을 제한한다.
    overview: str | None = Field(default=None, max_length=10_000, description="영화 줄거리")

    # 장르가 없거나 요청에서 생략하면 자동으로 빈 리스트를 사용한다.
    genres: list[GenreName] = Field(default_factory=list, max_length=10, description="영화 장르 목록")

    # 감독 정보를 확인할 수 없는 경우에는 생략할 수 있다.
    director: str | None = Field(default=None, max_length=200, description="감독 이름")

    # 배우나 성우가 없으면 필드를 생략할 수 있으며 자동으로 빈 리스트가 된다.
    cast: list[CastName] = Field(default_factory=list, max_length=30, description="출연 배우 또는 성우 이름 목록")

    # 키워드가 없으면 빈 리스트를 사용하며 최대 30개까지 허용한다.
    keywords: list[KeywordName] = Field(default_factory=list, max_length=30, description="영화 키워드 목록")

    # 개봉 연도를 모르는 경우 생략할 수 있으며 잘못된 범위는 차단한다.
    year: int | None = Field(default=None, ge=1800, le=2100, description="영화 개봉 연도")

    # 가능하면 ko, en, ja와 같은 언어 코드를 입력한다.
    language: str | None = Field(default=None, max_length=10, description="영화 원어 코드")

    # 관객 수를 모르면 생략할 수 있으며 음수는 허용하지 않는다.
    audience_count: int | None = Field(default=None, ge=0, description="확인 가능한 관객 수")


# 관리자 영화 수정 API가 전달받는 요청 데이터의 형식과 기본 수정 규칙을 검증한다.
class AdminMovieUpdateRequest(BaseModel):
    """관리자가 기존 영화에서 변경할 필드만 전달하는 PATCH 요청 형식이다.

    모든 필드는 생략할 수 있지만 빈 요청은 허용하지 않는다. 생략된 필드는
    기존 값을 유지하고, 요청에 실제로 포함된 필드만 서비스에서 수정한다.
    """

    # 스키마에 정의되지 않은 필드를 허용하지 않아 수정 가능한 범위를 제한한다.
    # FastAPI는 여기서 발생한 Pydantic 검증 오류를 HTTP 422 응답으로 변환한다.
    model_config = ConfigDict(extra="forbid")

    # 제목은 생략하면 기존 값을 유지하지만 명시적인 null은 아래 검증에서 차단한다.
    # 실제 제목을 수정할 때는 앞뒤 공백을 제거한 1~300자의 문자열만 허용한다.
    title: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=300),
    ] | None = Field(default=None, description="수정할 영화 제목")

    # 일반 선택 필드는 생략하면 기존 값을 유지하고 null을 보내면 기존 값을 제거한다.
    overview: str | None = Field(default=None, max_length=10_000, description="수정할 영화 줄거리")
    director: str | None = Field(default=None, max_length=200, description="수정할 감독 이름")
    year: int | None = Field(default=None, ge=1800, le=2100, description="수정할 영화 개봉 연도")
    language: str | None = Field(default=None, max_length=10, description="수정할 영화 원어 코드")
    audience_count: int | None = Field(default=None, ge=0, description="수정할 관객 수")

    # 목록 필드는 생략하면 기존 목록을 유지하고 빈 배열을 보내면 전체 목록을 제거한다.
    # null은 '생략'과 '전체 제거'의 의미를 모호하게 만들기 때문에 아래 검증에서 차단한다.
    genres: list[GenreName] | None = Field(default=None, max_length=10, description="수정할 영화 장르 목록")
    cast: list[CastName] | None = Field(default=None, max_length=30, description="수정할 출연 배우 또는 성우 이름 목록")
    keywords: list[KeywordName] | None = Field(default=None, max_length=30, description="수정할 영화 키워드 목록")

    # 빈 수정 요청과 필수·목록 데이터의 잘못된 null 사용을 요청 단계에서 차단한다.
    @model_validator(mode="after")
    def validate_update_fields(self):
        """요청에 실제 변경값이 있는지 확인하고 필드별 null 사용 규칙을 적용한다."""

        # model_fields_set에는 클라이언트가 JSON 본문에 실제로 넣은 필드만 들어간다.
        # 이를 이용하면 필드 생략과 명시적인 null 전달을 정확하게 구분할 수 있다.
        requested_fields = self.model_fields_set

        # 빈 JSON은 변경할 데이터가 없으므로 서비스까지 전달하지 않고 검증 오류로 처리한다.
        if not requested_fields:
            raise ValueError("수정할 영화 정보를 하나 이상 입력해야 합니다.")

        # 제목은 DB의 필수 정보이므로 생략은 허용하지만 null로 제거하는 것은 허용하지 않는다.
        if "title" in requested_fields and self.title is None:
            raise ValueError("영화 제목은 null로 변경할 수 없습니다.")

        # 목록 전체를 제거하려면 null 대신 빈 배열을 사용하도록 입력 규칙을 통일한다.
        list_fields = {
            "genres": self.genres,
            "cast": self.cast,
            "keywords": self.keywords,
        }

        for field_name, field_value in list_fields.items():
            if field_name in requested_fields and field_value is None:
                raise ValueError(
                    f"{field_name}을 비우려면 null이 아니라 빈 배열을 입력해야 합니다."
                )

        return self
