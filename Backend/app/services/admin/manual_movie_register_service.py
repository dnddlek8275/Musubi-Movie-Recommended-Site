from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.movies import Movie
from app.schemas.admin import AdminManualMovieCreateRequest


def get_manual_movie_duplicate(
    db: Session,
    title: str,
    year: int | None,
) -> Movie | None:
    """제목과 개봉 연도가 같은 영화가 이미 등록됐는지 조회한다.

    TMDB로 등록한 영화와 관리자가 직접 입력한 영화를 모두 조회한다.
    관리자가 TMDB에 이미 등록된 영화를 직접 등록 방식으로 다시 추가하는
    상황도 줄이기 위해 tmdb_id 조건은 사용하지 않는다.

    Args:
        db: 영화 데이터를 조회할 SQLAlchemy 세션.
        title: 직접 등록하려는 영화 제목.
        year: 영화 개봉 연도. 입력하지 않았다면 None.

    Returns:
        동일한 영화가 있으면 Movie 객체를 반환하고, 없으면 None을 반환한다.
    """

    # 스키마에서도 제목의 공백을 제거하지만, 이 함수를 다른 코드에서 직접
    # 호출할 가능성까지 고려해 서비스에서도 한 번 더 정규화한다.
    normalized_title = title.strip().lower()

    # DB 제목에도 trim과 lower를 적용해 "Movie", "movie", " Movie "가
    # 서로 다른 영화로 중복 등록되는 가능성을 줄인다.
    query = select(Movie).where(
        func.lower(func.trim(Movie.title)) == normalized_title
    )

    if year is None:
        # 요청에 개봉 연도가 없다면 DB에서도 연도가 없는 동명 영화만 찾는다.
        # 연도가 있는 다른 동명 영화를 무조건 중복으로 판단하지 않기 위해서다.
        query = query.where(Movie.year.is_(None))
    else:
        # 동명 영화가 존재할 수 있으므로 개봉 연도를 입력했다면 제목과
        # 연도가 모두 같은 영화만 중복으로 판단한다.
        query = query.where(Movie.year == year)

    # 이 함수는 중복 조회만 담당하며 commit이나 rollback은 수행하지 않는다.
    return db.scalar(query)


def build_manual_movie_data(
    request: AdminManualMovieCreateRequest,
) -> dict:
    """직접 영화 등록 요청을 공통 저장 서비스가 사용할 형식으로 변환한다.

    기존 create_admin_movie()가 TMDB 영화와 직접 입력 영화를 모두 저장할 수
    있으므로, 이 함수에서는 직접 입력 영화에 필요한 값만 준비한다.

    Args:
        request: Pydantic 검증이 완료된 관리자 직접 영화 등록 요청.

    Returns:
        create_admin_movie()에 전달할 영화 정보 딕셔너리.
    """

    # Pydantic 요청 객체를 일반 딕셔너리로 변환한다. 입력하지 않은
    # overview, director, year 같은 선택값은 제외하며, 해당 Movie 컬럼은
    # nullable이므로 저장 시 자연스럽게 NULL을 사용할 수 있다.
    movie_data = request.model_dump(exclude_none=True)

    # 제목은 유일한 필수값이며 스키마에서 이미 공백이 제거된다.
    # 저장 직전에도 정리된 값을 명시적으로 사용해 데이터 형식을 통일한다.
    movie_data["title"] = request.title.strip()

    # 직접 입력 영화는 TMDB에서 가져온 데이터가 아니므로 외부 영화 ID와
    # 마지막 동기화 시각을 서버에서 None으로 고정해 데이터 출처를 구분한다.
    movie_data["tmdb_id"] = None
    movie_data["last_synced_at"] = None

    # 직접 입력한 배우나 성우에게는 신뢰할 수 있는 TMDB 배우 ID가 없다.
    # 이름은 movies.cast 배열에 저장하되, actors와 movie_actors 관계 생성은
    # 건너뛰도록 TMDB 상세 배우 정보인 cast_credits를 빈 리스트로 설정한다.
    movie_data["cast_credits"] = []

    # 이 함수는 저장용 데이터 변환만 담당한다. 실제 DB 추가는 기존
    # create_admin_movie()가, commit과 rollback은 이후 관리자 API가 담당한다.
    return movie_data
