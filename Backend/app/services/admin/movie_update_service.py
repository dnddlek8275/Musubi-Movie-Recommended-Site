import json
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.admin import AdminAuditLog
from app.models.movies import Movie
from app.models.users import User
from app.services.admin.movie_service import admin_movie_to_dict, normalize_string_list, sync_admin_movie_genres


# 수정 중인 영화를 제외하고 동일한 제목과 개봉 연도의 영화가 있는지 확인한다.
def get_admin_movie_update_duplicate(
    db: Session,
    movie_id: int,
    title: str,
    year: int | None,
) -> Movie | None:
    """수정 결과가 다른 영화와 중복되는지 조회한다.

    Args:
        db: 중복 영화를 조회할 SQLAlchemy 세션.
        movie_id: 중복 검사에서 제외할 현재 영화의 내부 ID.
        title: 수정 후 영화에 저장될 최종 제목.
        year: 수정 후 영화에 저장될 최종 개봉 연도.

    Returns:
        동일한 제목과 연도의 다른 영화가 있으면 Movie 객체를 반환하고,
        중복 영화가 없으면 None을 반환한다.
    """

    # 제목의 앞뒤 공백과 영문 대소문자 차이만으로 중복 검사를
    # 피하지 못하도록 요청 제목과 DB 제목을 같은 기준으로 정리한다.
    normalized_title = title.strip().lower()

    query = select(Movie).where(
        # 수정 중인 영화 자기 자신은 중복 검사에서 제외한다.
        Movie.id != movie_id,
        func.lower(func.trim(Movie.title)) == normalized_title,
    )

    if year is None:
        # 수정 후 개봉 연도가 없다면 DB에서도 연도가 없는 동명 영화만 찾는다.
        query = query.where(Movie.year.is_(None))
    else:
        # 동명 영화가 존재할 수 있으므로 제목과 개봉 연도가
        # 모두 같은 경우에만 중복으로 판단한다.
        query = query.where(Movie.year == year)

    # 이 함수는 조회만 담당하며 commit이나 rollback을 수행하지 않는다.
    return db.scalar(query)


# 요청에 포함된 영화 정보만 변경하고 수정 전후 데이터를 감사 로그에 기록한다.
def update_admin_movie(
    db: Session,
    current_admin: User,
    movie: Movie,
    update_data: dict,
) -> dict | None:
    """영화 수정 요청을 반영하고 관리자 감사 로그를 추가한다.

    Args:
        db: 영화, 장르와 감사 로그를 함께 처리할 SQLAlchemy 세션.
        current_admin: 영화 수정 작업을 수행한 관리자 사용자.
        movie: 수정할 Movie 객체.
        update_data: 클라이언트가 실제 요청에 포함한 수정값 딕셔너리.

    Returns:
        실제 변경이 있으면 수정 후 영화 정보 딕셔너리를 반환한다.
        모든 요청값이 기존 값과 같으면 None을 반환한다.

    Notes:
        이 함수에서는 commit이나 rollback을 수행하지 않는다. API가 모든
        변경을 한 번에 commit하고 실패하면 전체 rollback해야 한다.
    """

    # API에서 전달받은 원본 딕셔너리를 직접 변경하지 않도록 복사한다.
    data = update_data.copy()

    # 데이터를 변경하기 전에 현재 영화 정보를 복사해 감사 로그에 보관한다.
    before_data = admin_movie_to_dict(movie)
    has_changes = False

    # 장르는 movies.genres와 movie_genres에 함께 저장되므로
    # 일반 필드와 분리하고 공통 장르 동기화 함수를 사용한다.
    if "genres" in data:
        genres = data.pop("genres")

        if sync_admin_movie_genres(db=db, movie=movie, genres=genres):
            has_changes = True

    # 직접 등록 영화의 배우 또는 성우 목록에서 공백과 중복을 제거한다.
    # TMDB 영화의 cast 수정 요청은 API에서 서비스 호출 전에 차단한다.
    if "cast" in data:
        data["cast"] = normalize_string_list(data["cast"])

    # 키워드도 영화 등록과 같은 기준으로 공백과 중복을 제거한다.
    if "keywords" in data:
        data["keywords"] = normalize_string_list(data["keywords"])

    # 관리자 수정 API에서 변경할 수 있는 Movie 컬럼만 허용한다.
    # tmdb_id, 평점, 포스터와 동기화 시각 같은 서버 관리 값은 제외한다.
    allowed_fields = {
        "title",
        "overview",
        "director",
        "cast",
        "keywords",
        "year",
        "language",
        "audience_count",
    }

    for field_name, field_value in data.items():
        # 스키마에서 추가 필드를 차단하지만, 서비스에서도 허용 목록을 사용해
        # 서버가 관리하는 컬럼이 임의로 변경되지 않도록 한 번 더 보호한다.
        if field_name not in allowed_fields:
            continue

        # 현재 DB 값과 새로운 값이 다른 필드만 변경한다.
        # 같은 값을 다시 보낸 요청으로 불필요한 UPDATE가 실행되는 것을 막는다.
        if getattr(movie, field_name) != field_value:
            setattr(movie, field_name, field_value)
            has_changes = True

    # 요청 필드는 있었지만 모든 값이 기존 데이터와 같다면
    # 수정 시각과 감사 로그를 만들지 않고 None을 반환한다.
    if not has_changes:
        return None

    # Movie 모델에는 updated_at 자동 갱신 설정이 없으므로
    # 실제 영화 데이터가 변경된 경우 한국 시간 기준으로 직접 갱신한다.
    movie.updated_at = datetime.now(ZoneInfo("Asia/Seoul"))

    # 영화와 장르 변경 SQL을 현재 트랜잭션에서 DB에 전달한다.
    # flush는 최종 확정이 아니므로 이후 실패하면 API에서 rollback할 수 있다.
    db.flush()

    # 수정된 Movie 객체를 API 응답과 감사 로그가 사용하는 형식으로 변환한다.
    after_data = admin_movie_to_dict(movie)

    # 어떤 관리자가 어떤 영화를 어떻게 수정했는지 확인할 수 있도록
    # 영화 정보의 변경 전후 데이터를 감사 로그에 기록한다.
    db.add(
        AdminAuditLog(
            admin_user_id=current_admin.id,
            target_table="movies",
            target_id=movie.id,
            action="UPDATE_MOVIE",
            before_data=json.dumps(before_data, ensure_ascii=False, default=str),
            after_data=json.dumps(after_data, ensure_ascii=False, default=str),
        )
    )

    # 실제 commit은 API에서 처리하도록 수정 결과만 반환한다.
    return after_data
