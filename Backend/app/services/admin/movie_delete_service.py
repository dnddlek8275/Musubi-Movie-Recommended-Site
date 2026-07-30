import json

from sqlalchemy.orm import Session

from app.models.admin import AdminAuditLog
from app.models.movies import Movie
from app.models.users import User
from app.services.admin.movie_service import admin_movie_to_dict

# 삭제 전 영화 정보를 보존하고 영화 삭제와 감사 로그 생성을 함께 준비한다.
def delete_admin_movie(
    db: Session,
    current_admin: User,
    movie: Movie,
) -> dict:
    """영화 삭제를 준비하고 관리자 감사 로그를 같은 DB 세션에 추가한다.

    Movie 객체를 삭제하면 DB 외래키 설정에 따라 장르, 통계, 배우 관계,
    사용자 행동 기록과 일일 추천 연결 데이터가 함께 삭제된다. 캐릭터는
    삭제하지 않고 연결된 movie_id만 NULL로 변경된다.

    Returns:
        API 성공 응답과 감사 로그에 사용할 삭제 전 영화 정보 딕셔너리.

    Notes:
        이 함수에서는 commit이나 rollback을 수행하지 않는다. 추후 삭제 API가
        영화 삭제와 감사 로그를 한 번에 commit하고, 실패하면 전체 rollback해야
        일부 데이터만 변경되는 불완전한 상태를 방지할 수 있다.
    """

    # Movie 객체를 삭제한 뒤에는 응답이나 감사 로그용 값을 안정적으로
    # 읽기 어려울 수 있으므로 기존 공통 변환 함수를 사용해 먼저 복사한다.
    before_data = admin_movie_to_dict(movie)

    # 누가 어떤 영화를 삭제했는지 추적할 수 있도록 삭제 전 정보를 기록한다.
    # 감사 로그도 같은 DB 세션에 추가해 최종 commit 성공 여부를 영화 삭제와
    # 일치시키며, 기존 CREATE_MOVIE 같은 과거 감사 로그는 삭제하지 않는다.
    db.add(
        AdminAuditLog(
            admin_user_id=current_admin.id,
            target_table="movies",
            target_id=movie.id,
            action="DELETE_MOVIE",
            before_data=json.dumps(
                before_data,
                ensure_ascii=False,
                default=str,
            ),
            after_data=None,
        )
    )

    # movies 행만 직접 삭제 대기 상태로 만든다. movie_genres, movie_stats,
    # movie_actors, 사용자 행동 기록과 일일 추천 연결은 각 외래키의
    # ON DELETE CASCADE 설정에 따라 DB가 최종 commit 시 함께 정리한다.
    db.delete(movie)

    # 삭제 API가 어떤 영화를 삭제했는지 data에 담아 반환할 수 있도록
    # 삭제 전에 복사한 영화 정보를 서비스 결과로 제공한다.
    return before_data
