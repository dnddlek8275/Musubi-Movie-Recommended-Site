# 관리자 관련 API들을 묶는 Router /admin
from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.core.current_user import get_current_admin
from app.core.dependencies import get_db
from app.models.users import User
from app.schemas.admin import AdminManualMovieCreateRequest, AdminMovieUpdateRequest, AdminRoleUpdateRequest
from app.services.admin.manual_movie_register_service import build_manual_movie_data, get_manual_movie_duplicate
from app.services.admin.movie_delete_service import delete_admin_movie
from app.services.admin.movie_service import admin_movie_to_dict, create_admin_movie, get_admin_movie, get_movie_by_tmdb_id
from app.services.admin.movie_update_service import get_admin_movie_update_duplicate, update_admin_movie
from app.services.admin.role_service import change_admin_role, get_admin_role_target
from app.services.admin.tmdb_search_service import search_admin_tmdb_movies
from app.services.admin.tmdb_register_service import fetch_admin_tmdb_movie_detail


router = APIRouter(
    prefix="/admin",
    tags=["Admin"]
)

@router.get("/check")
def check_admin(
    current_user : User = Depends(get_current_admin),
):
    return {
        "state" : "success",
        "message" : "관리자 권한 확인 성공",
        "data" : {
            "email" : current_user.email,
            "is_admin" : current_user.is_admin
        }
    }


@router.get("/tmdb-movies-search")
async def search_tmdb_movies(
    # TMDB에서 검색할 영화 제목을 query parameter로 받는다.
    query: str = Query(..., min_length=1, max_length=100),
    # TMDB 검색 결과의 페이지 번호이며 1부터 500까지만 허용한다.
    page: int = Query(1, ge=1, le=500),
    # 관리자 권한이 확인된 사용자만 검색 API를 사용할 수 있다.
    current_admin: User = Depends(get_current_admin),
    # 검색 결과의 영화가 내부 DB에 등록됐는지 확인하기 위해 사용한다.
    db: Session = Depends(get_db),
):
    try:
        # TMDB 영화 검색과 내부 DB 등록 여부 확인을 서비스에서 함께 처리한다.
        search_result = await search_admin_tmdb_movies(
            db=db,
            query=query,
            page=page,
        )

        # 검색 결과가 없는 경우 빈 영화 목록과 페이지 정보를 반환한다.
        if not search_result["movies"]:
            return {
                "state": "failure",
                "message": "TMDB 검색 결과가 없습니다.",
                "data": search_result,
            }

        return {
            "state": "success",
            "message": "TMDB 영화 검색 성공",
            "data": search_result,
        }

    except Exception as e:
        return {
            "state": "error",
            "message": "TMDB 영화 검색 에러",
            "error": str(e),
        }


@router.post("/tmdb-movies-register/{tmdb_id}")
async def register_tmdb_movie(
    # 검색 결과에서 관리자가 선택한 TMDB 영화 ID를 URL 경로로 받는다.
    # Path 검증을 통해 0 이하의 잘못된 ID는 서비스 호출 전에 차단한다.
    tmdb_id: int = Path(
        ...,
        gt=0,
        description="등록할 TMDB 영화 ID",
    ),
    # 관리자 권한이 확인된 사용자만 영화 등록 API를 사용할 수 있다.
    # 등록 성공 시 감사 로그의 admin_user_id에도 이 사용자 ID가 기록된다.
    current_admin: User = Depends(get_current_admin),
    # 영화, 장르, 통계와 감사 로그를 하나의 트랜잭션으로 저장할 DB 세션이다.
    db: Session = Depends(get_db),
):
    try:
        # 이미 등록된 영화는 TMDB 상세 API를 다시 호출하지 않는다.
        # 외부 요청 전에 DB를 먼저 확인해 응답 시간을 줄이고 호출량을 아낀다.
        existing_movie = get_movie_by_tmdb_id(
            db=db,
            tmdb_id=tmdb_id,
        )

        if existing_movie is not None:
            return {
                "state": "failure",
                "message": "이미 등록된 TMDB 영화입니다.",
                "data": admin_movie_to_dict(existing_movie),
            }

        # 검색 응답을 그대로 저장하지 않고 선택한 tmdb_id로 상세정보를
        # 다시 조회해 감독, 출연진, 키워드와 장르 이름까지 가져온다.
        movie_data = await fetch_admin_tmdb_movie_detail(
            tmdb_id=tmdb_id,
        )

        # 공통 영화 저장 서비스가 movies, movie_genres, movie_stats와
        # admin_audit_logs를 같은 DB 세션에 추가한다.
        movie = create_admin_movie(
            db=db,
            current_admin=current_admin,
            movie_data=movie_data,
        )

        # 관련 데이터가 모두 준비된 후 한 번만 commit한다.
        # 이 방식은 중간 단계만 저장되는 불완전한 영화 데이터를 방지한다.
        db.commit()

        # DB에서 생성한 ID와 생성·수정 시각을 최종 응답에 반영한다.
        db.refresh(movie)

        return {
            "state": "success",
            "message": "TMDB 영화 등록 성공",
            "data": admin_movie_to_dict(movie),
        }

    except Exception as e:
        # TMDB 조회 또는 영화·장르·통계·감사 로그 저장 중 하나라도
        # 실패하면 트랜잭션 전체를 되돌려 일부 데이터가 남지 않게 한다.
        db.rollback()

        return {
            "state": "error",
            "message": "TMDB 영화 등록 에러",
            "error": str(e),
        }


@router.post("/movie")
def register_manual_movie(
    # TMDB에서 찾을 수 없는 영화 정보를 JSON 요청 본문으로 받는다.
    # 영화 제목은 필수이며 나머지 값은 스키마 규칙에 따라 생략할 수 있다.
    request: AdminManualMovieCreateRequest,
    # 관리자 권한이 확인된 사용자만 영화를 직접 등록할 수 있다.
    # 현재 관리자의 ID는 영화 생성 감사 로그에도 기록된다.
    current_admin: User = Depends(get_current_admin),
    # 영화, 장르, 초기 통계와 감사 로그를 하나의 트랜잭션으로 저장한다.
    db: Session = Depends(get_db),
):
    try:
        # TMDB 등록 영화와 직접 입력 영화를 모두 대상으로 동일한 제목과
        # 개봉 연도의 영화가 있는지 먼저 확인해 중복 등록을 줄인다.
        existing_movie = get_manual_movie_duplicate(
            db=db,
            title=request.title,
            year=request.year,
        )

        if existing_movie is not None:
            # 중복은 서버 예외가 아니라 처리 가능한 요청 실패이므로
            # state는 error가 아닌 failure를 사용하고 기존 영화를 반환한다.
            return {
                "state": "failure",
                "message": "동일한 제목과 개봉 연도의 영화가 이미 등록되어 있습니다.",
                "data": admin_movie_to_dict(existing_movie),
            }

        # 검증이 끝난 직접 입력 요청을 기존 공통 영화 저장 함수가 처리할
        # 딕셔너리로 변환한다. TMDB 영화가 아니므로 변환 과정에서
        # tmdb_id와 last_synced_at은 None, cast_credits는 빈 리스트가 된다.
        movie_data = build_manual_movie_data(request)

        # 기존 TMDB 등록에서도 사용하는 공통 저장 함수를 재사용한다.
        # movies, movie_genres, movie_stats와 admin_audit_logs가 모두
        # 같은 DB 세션에 추가되며 서비스 내부에서는 commit하지 않는다.
        movie = create_admin_movie(
            db=db,
            current_admin=current_admin,
            movie_data=movie_data,
        )

        # 관련 데이터가 모두 준비된 후 한 번만 commit해 일부 테이블만
        # 저장되는 불완전한 상태를 방지한다.
        db.commit()

        # DB가 생성한 영화 ID와 생성·수정 시각을 최종 응답에 반영한다.
        db.refresh(movie)

        return {
            "state": "success",
            "message": "직접 입력 영화 등록 성공",
            "data": admin_movie_to_dict(movie),
        }

    except Exception as e:
        # 영화, 장르, 초기 통계 또는 감사 로그 처리 중 하나라도 실패하면
        # 현재 트랜잭션의 모든 DB 변경을 되돌려 일부 데이터가 남지 않게 한다.
        db.rollback()

        return {
            "state": "error",
            "message": "직접 입력 영화 등록 에러",
            "error": str(e),
        }


# 관리자가 내부 movie_id에 해당하는 영화 정보를 부분 수정한다.
@router.patch("/movie/{movie_id}")
def update_movie(
    request: AdminMovieUpdateRequest,
    # 수정 대상은 TMDB의 tmdb_id가 아니라 movies 테이블의 내부 기본키이다.
    # 0 이하의 ID는 FastAPI 요청 검증 단계에서 HTTP 422로 차단한다.
    movie_id: int = Path(..., gt=0, description="수정할 내부 영화 ID"),
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    try:
        # 수정과 삭제에서 같은 내부 movie_id 조회 기준을 사용하도록
        # 공통 관리자 영화 조회 함수를 재사용한다.
        movie = get_admin_movie(db=db, movie_id=movie_id)

        if movie is None:
            # 존재하지 않는 영화는 예상 가능한 요청 실패이므로
            # 예외를 발생시키지 않고 failure 응답을 반환한다.
            return {
                "state": "failure",
                "message": "수정할 영화를 찾을 수 없습니다.",
            }

        # 클라이언트가 실제 요청에 포함한 필드만 수정 서비스에 전달한다.
        # 생략한 필드는 제외하고 명시적으로 전달한 null은 유지한다.
        update_data = request.model_dump(exclude_unset=True)

        # TMDB 영화의 movies.cast만 변경하면 actors 및 movie_actors 관계와
        # 내용이 달라지므로 빈 배열을 포함한 모든 cast 변경을 차단한다.
        if movie.tmdb_id is not None and "cast" in update_data:
            return {
                "state": "failure",
                "message": "TMDB에서 등록한 영화의 배우 정보는 직접 수정할 수 없습니다.",
            }

        # 제목 또는 개봉 연도가 실제 요청에 포함된 경우에만 중복을 검사한다.
        # 생략한 값은 현재 DB 값을 사용해 수정 후 최종 상태를 계산한다.
        if "title" in update_data or "year" in update_data:
            final_title = update_data.get("title", movie.title)
            final_year = update_data["year"] if "year" in update_data else movie.year

            duplicate_movie = get_admin_movie_update_duplicate(
                db=db,
                movie_id=movie.id,
                title=final_title,
                year=final_year,
            )

            if duplicate_movie is not None:
                # 중복은 서버 예외가 아니라 처리 가능한 요청 실패이며,
                # 관리자가 확인할 수 있도록 기존 영화 정보를 함께 반환한다.
                return {
                    "state": "failure",
                    "message": "동일한 제목과 개봉 연도의 영화가 이미 등록되어 있습니다.",
                    "data": admin_movie_to_dict(duplicate_movie),
                }

        # 영화 존재 여부, TMDB 배우 변경과 중복 검사를 통과한 요청만
        # 실제 영화 수정 서비스로 전달한다.
        updated_movie_data = update_admin_movie(
            db=db,
            current_admin=current_admin,
            movie=movie,
            update_data=update_data,
        )

        if updated_movie_data is None:
            # 모든 요청값이 기존 데이터와 같다면 수정 시각과
            # 관리자 감사 로그를 만들지 않고 failure로 처리한다.
            return {
                "state": "failure",
                "message": "변경된 영화 정보가 없습니다.",
            }

        # 영화, 장르와 UPDATE_MOVIE 감사 로그를 하나의 트랜잭션으로
        # 최종 저장해 일부 데이터만 변경되는 것을 방지한다.
        db.commit()
        db.refresh(movie)

        return {
            "state": "success",
            "message": "영화 수정 성공",
            "data": admin_movie_to_dict(movie),
        }

    except Exception as e:
        # 영화, 장르 또는 감사 로그 처리 중 하나라도 실패하면 현재
        # 트랜잭션 전체를 되돌려 일부 데이터만 변경되는 것을 방지한다.
        db.rollback()

        return {
            "state": "error",
            "message": "영화 수정 중 에러가 발생했습니다.",
            "error": str(e),
        }


# 내부 movie_id로 영화를 삭제하고 삭제 전 정보를 관리자 감사 로그에 기록한다.
@router.delete("/movie/{movie_id}")
def delete_movie(
    # 삭제 대상은 TMDB의 tmdb_id가 아니라 movies 테이블의 내부 기본키이다.
    # 0 이하의 잘못된 ID는 서비스 함수 호출 전에 422 오류로 차단한다.
    movie_id: int = Path(..., gt=0, description="삭제할 내부 영화 ID"),
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    try:
        # 수정과 삭제에서 같은 내부 movie_id 조회 기준을 사용하도록
        # 공통 관리자 영화 조회 함수를 재사용한다.
        movie = get_admin_movie(
            db=db,
            movie_id=movie_id,
        )

        if movie is None:
            # 존재하지 않는 영화는 예상 가능한 요청 실패이므로
            # 예외가 아닌 failure 응답을 반환하고 DB 변경은 수행하지 않는다.
            return {
                "state": "failure",
                "message": "삭제할 영화를 찾을 수 없습니다.",
            }

        # 삭제 전 영화 정보를 복사하고 DELETE_MOVIE 감사 로그를 추가한 뒤
        # Movie 객체를 현재 DB 세션에서 삭제 대기 상태로 만든다.
        deleted_movie_data = delete_admin_movie(
            db=db,
            current_admin=current_admin,
            movie=movie,
        )

        # 영화 삭제와 감사 로그가 모두 준비된 후 한 번만 commit한다.
        # 관련 장르, 통계, 배우 관계와 사용자 행동 기록은 외래키의
        # ON DELETE 설정에 따라 같은 트랜잭션에서 함께 처리된다.
        db.commit()

        return {
            "state": "success",
            "message": "영화 삭제 성공",
            "data": deleted_movie_data,
        }

    except Exception as e:
        # 영화 삭제나 감사 로그 저장 중 하나라도 실패하면 현재 트랜잭션의
        # 모든 변경을 되돌려 일부 데이터만 삭제되는 상황을 방지한다.
        db.rollback()

        return {
            "state": "error",
            "message": "영화 삭제 중 에러가 발생했습니다.",
            "error": str(e),
        }


@router.patch("/users/admin-role")
def update_admin_role(
    request : AdminRoleUpdateRequest,
    current_admin : User = Depends(get_current_admin),
    db : Session = Depends(get_db),
):
    try:
        # 이메일 조회와 권한 변경 가능 여부 검사는 서비스 함수에서 처리한다.
        target_user = get_admin_role_target(
            db=db,
            current_admin=current_admin,
            email=str(request.email),
            requested_is_admin=request.is_admin,
        )

        # 실제 권한을 변경하고 같은 트랜잭션에 감사 로그를 추가한다.
        change_admin_role(
            db=db,
            current_admin=current_admin,
            target_user=target_user,
            is_admin=request.is_admin,
        )

        # 권한 변경과 감사 로그를 한 번에 저장한다.
        db.commit()
        db.refresh(target_user)
        return {
            "state": "success",
            "message": (
                "관리자 권한을 부여했습니다."
                if target_user.is_admin
                else "관리자 권한을 회수했습니다."
            ),
            "data": {
                "user_id": target_user.id,
                "email": target_user.email,
                "nickname": target_user.nickname,
                "is_admin": target_user.is_admin,
            },
        }
    except Exception as e:
        # 권한 변경 중 오류가 발생하면 저장 전 상태로 되돌린다.
        db.rollback()
        return {
            "state": "error",
            "message": "관리자 부여 에러",
            "error": str(e),
        }
