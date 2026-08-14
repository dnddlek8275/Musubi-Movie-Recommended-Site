# 관리자 관련 API들을 묶는 Router /admin
import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import delete, func, or_
from sqlalchemy.orm import Session

from app.core.current_user import get_current_admin
from app.core.api_responses import error_response
from app.core.dependencies import get_db
from app.models.users import User
from app.models.admin import AdminAuditLog
from app.models.chat import ChatMessage, ChatRoom
from app.models.contact import ContactInquiry
from app.models.interactions import MovieRating, UserMovieInteraction
from app.models.movies import Movie, MovieStats
from app.models.actors import MovieActor
from app.models.sync import MovieVectorSyncJob
from app.models.tokens import EmailVerificationCode, RefreshToken
from app.schemas.admin import AdminInquiryReplyRequest, AdminManualMovieCreateRequest, AdminMovieUpdateRequest, AdminRoleUpdateRequest, AdminUserSuspensionRequest
from app.services.admin.manual_movie_register_service import build_manual_movie_data, get_manual_movie_duplicate
from app.services.admin.movie_delete_service import delete_admin_movie
from app.services.admin.movie_service import (
    admin_movie_to_dict,
    create_admin_movie,
    get_admin_movie,
    get_movie_by_tmdb_id,
    normalize_string_list,
    sync_admin_movie_actors,
    sync_admin_movie_genres,
)
from app.services.admin.movie_update_service import get_admin_movie_update_duplicate, update_admin_movie
from app.services.admin.role_service import change_admin_role, get_admin_role_target
from app.services.admin.tmdb_search_service import search_admin_tmdb_movies
from app.services.admin.tmdb_register_service import fetch_admin_tmdb_movie_detail
from app.services.movies.genre_relevance import sync_movie_genre_weights
from app.services.movies.vector_sync_service import enqueue_movie_vector_sync
from app.services.email.email_service import send_contact_reply_email
from app.services.user_service import delet_user_profile_image


router = APIRouter(
    prefix="/admin",
    tags=["Admin"]
)


def _iso(value):
    return value.isoformat() if value is not None else None


@router.get("/overview")
def get_admin_overview(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """관리 화면에 필요한 핵심 운영 지표와 최근 변경 이력을 반환한다."""
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)

    user_total = db.query(func.count(User.id)).scalar() or 0
    movie_total = db.query(func.count(Movie.id)).scalar() or 0
    interaction_total = db.query(func.count(UserMovieInteraction.id)).scalar() or 0

    top_movies = (
        db.query(Movie, MovieStats)
        .outerjoin(MovieStats, MovieStats.movie_id == Movie.id)
        .order_by(
            func.coalesce(MovieStats.ranking_score, 0).desc(),
            func.coalesce(MovieStats.view_count, 0).desc(),
            Movie.id.desc(),
        )
        .limit(5)
        .all()
    )
    recent_audits = (
        db.query(AdminAuditLog, User)
        .outerjoin(User, User.id == AdminAuditLog.admin_user_id)
        .order_by(AdminAuditLog.created_at.desc(), AdminAuditLog.id.desc())
        .limit(8)
        .all()
    )

    return {
        "state": "success",
        "message": "관리자 운영 현황 조회 성공",
        "data": {
            "users": {
                "total": user_total,
                "admins": db.query(func.count(User.id)).filter(User.is_admin.is_(True)).scalar() or 0,
                "onboarded": db.query(func.count(User.id)).filter(User.onboarding_completed.is_(True)).scalar() or 0,
                "new_7d": db.query(func.count(User.id)).filter(User.created_at >= seven_days_ago).scalar() or 0,
            },
            "movies": {
                "total": movie_total,
                "tmdb": db.query(func.count(Movie.id)).filter(Movie.tmdb_id.is_not(None)).scalar() or 0,
                "manual": db.query(func.count(Movie.id)).filter(Movie.tmdb_id.is_(None)).scalar() or 0,
                "missing_poster": db.query(func.count(Movie.id)).filter(or_(Movie.poster_path.is_(None), Movie.poster_path == "")).scalar() or 0,
            },
            "activity": {
                "chat_rooms": db.query(func.count(ChatRoom.id)).scalar() or 0,
                "chat_messages": db.query(func.count(ChatMessage.id)).scalar() or 0,
                "ratings": db.query(func.count(MovieRating.id)).scalar() or 0,
                "likes": db.query(func.count(UserMovieInteraction.id)).filter(UserMovieInteraction.action_type == "like").scalar() or 0,
                "interactions": interaction_total,
                "interactions_7d": db.query(func.count(UserMovieInteraction.id)).filter(UserMovieInteraction.created_at >= seven_days_ago).scalar() or 0,
                "inquiries": db.query(func.count(ContactInquiry.id)).scalar() or 0,
                "open_inquiries": db.query(func.count(ContactInquiry.id)).filter(ContactInquiry.status.in_(("received", "in_progress"))).scalar() or 0,
            },
            "vector_sync": {
                "pending": db.query(func.count(MovieVectorSyncJob.id)).filter(MovieVectorSyncJob.status == "pending").scalar() or 0,
                "processing": db.query(func.count(MovieVectorSyncJob.id)).filter(MovieVectorSyncJob.status == "processing").scalar() or 0,
                "failed": db.query(func.count(MovieVectorSyncJob.id)).filter(MovieVectorSyncJob.status == "failed").scalar() or 0,
                "completed": db.query(func.count(MovieVectorSyncJob.id)).filter(MovieVectorSyncJob.status == "completed").scalar() or 0,
            },
            "top_movies": [
                {
                    "id": movie.id,
                    "title": movie.title,
                    "year": movie.year,
                    "poster_path": movie.poster_path,
                    "view_count": stats.view_count if stats else 0,
                    "like_count": stats.like_count if stats else 0,
                    "ranking_score": stats.ranking_score if stats else 0,
                }
                for movie, stats in top_movies
            ],
            "recent_audits": [
                {
                    "id": audit.id,
                    "action": audit.action,
                    "target_table": audit.target_table,
                    "target_id": audit.target_id,
                    "admin": user.nickname if user else "삭제된 관리자",
                    "created_at": _iso(audit.created_at),
                }
                for audit, user in recent_audits
            ],
        },
    }


@router.get("/inquiries")
def list_admin_inquiries(
    status_filter: str = Query("all", alias="status", max_length=20),
    query: str = Query("", max_length=120),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    inquiry_query = db.query(ContactInquiry, User).outerjoin(User, User.id == ContactInquiry.user_id)
    if status_filter != "all":
        inquiry_query = inquiry_query.filter(ContactInquiry.status == status_filter)
    normalized = query.strip()
    if normalized:
        inquiry_query = inquiry_query.filter(or_(
            ContactInquiry.email.ilike(f"%{normalized}%"),
            ContactInquiry.subject.ilike(f"%{normalized}%"),
            ContactInquiry.message.ilike(f"%{normalized}%"),
        ))
    total = inquiry_query.count()
    rows = inquiry_query.order_by(ContactInquiry.created_at.desc(), ContactInquiry.id.desc()).offset((page - 1) * limit).limit(limit).all()
    return {
        "state": "success",
        "message": "관리자 문의 목록 조회 성공",
        "data": {
            "items": [
                {
                    "id": inquiry.id,
                    "category": inquiry.category,
                    "email": inquiry.email,
                    "subject": inquiry.subject,
                    "message": inquiry.message,
                    "status": inquiry.status,
                    "delivery_status": inquiry.delivery_status,
                    "reply_body": inquiry.reply_body,
                    "reply_delivery_status": inquiry.reply_delivery_status,
                    "replied_by_admin_id": inquiry.replied_by_admin_id,
                    "replied_at": _iso(inquiry.replied_at),
                    "member": inquiry.user_id is not None,
                    "nickname": user.nickname if user else None,
                    "created_at": _iso(inquiry.created_at),
                }
                for inquiry, user in rows
            ],
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": max(1, (total + limit - 1) // limit),
        },
    }


@router.patch("/inquiries/{inquiry_id}/status")
def update_admin_inquiry_status(
    inquiry_id: int = Path(..., gt=0),
    status_value: str = Query(..., alias="status", max_length=20),
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    allowed = {"received", "in_progress", "replied", "closed"}
    if status_value not in allowed:
        raise HTTPException(status_code=422, detail={"message": "지원하지 않는 문의 상태입니다."})
    inquiry = db.get(ContactInquiry, inquiry_id)
    if inquiry is None:
        return {"state": "failure", "message": "문의를 찾을 수 없습니다."}
    inquiry.status = status_value
    db.add(AdminAuditLog(
        admin_user_id=current_admin.id,
        target_table="contact_inquiries",
        target_id=inquiry.id,
        action="UPDATE_INQUIRY_STATUS",
        before_data=None,
        after_data=status_value,
    ))
    db.commit()
    return {"state": "success", "message": "문의 처리 상태를 변경했습니다.", "data": {"id": inquiry.id, "status": inquiry.status}}


@router.post("/inquiries/{inquiry_id}/reply")
async def reply_admin_inquiry(
    request: AdminInquiryReplyRequest,
    inquiry_id: int = Path(..., gt=0),
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    inquiry = db.get(ContactInquiry, inquiry_id)
    if inquiry is None:
        return {"state": "failure", "message": "문의를 찾을 수 없습니다."}
    try:
        await send_contact_reply_email(
            email=inquiry.email,
            inquiry_id=inquiry.id,
            subject=inquiry.subject,
            body=request.body,
        )
    except Exception:
        inquiry.reply_delivery_status = "failed"
        db.commit()
        raise HTTPException(status_code=502, detail={"message": "답변 메일 전송에 실패했습니다. SMTP 설정과 연결 상태를 확인해 주세요."})

    inquiry.reply_body = request.body
    inquiry.reply_delivery_status = "sent"
    inquiry.replied_by_admin_id = current_admin.id
    inquiry.replied_at = datetime.now(timezone.utc)
    inquiry.status = "replied"
    db.add(AdminAuditLog(
        admin_user_id=current_admin.id,
        target_table="contact_inquiries",
        target_id=inquiry.id,
        action="REPLY_INQUIRY",
        after_data=f"delivery=sent; length={len(request.body)}",
    ))
    db.commit()
    return {
        "state": "success",
        "message": "답변 메일을 전송하고 문의 기록에 저장했습니다.",
        "data": {"id": inquiry.id, "status": inquiry.status, "replied_at": _iso(inquiry.replied_at)},
    }


@router.get("/movies")
def list_admin_movies(
    query: str = Query("", max_length=100),
    source: str = Query("all", pattern="^(all|tmdb|manual)$"),
    poster: str = Query("all", pattern="^(all|present|missing)$"),
    sync_status: str = Query("all", pattern="^(all|pending|processing|completed|failed|unknown|not_applicable)$"),
    sort: str = Query("updated_desc", pattern="^(updated_desc|release_desc|views_desc|likes_desc|title_asc)$"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    movie_query = (
        db.query(Movie, MovieStats, MovieVectorSyncJob)
        .outerjoin(MovieStats, MovieStats.movie_id == Movie.id)
        .outerjoin(MovieVectorSyncJob, MovieVectorSyncJob.tmdb_id == Movie.tmdb_id)
    )
    normalized = query.strip()
    if normalized:
        filters = [Movie.title.ilike(f"%{normalized}%")]
        if normalized.isdigit():
            filters.extend([Movie.id == int(normalized), Movie.tmdb_id == int(normalized)])
        movie_query = movie_query.filter(or_(*filters))

    if source == "tmdb":
        movie_query = movie_query.filter(Movie.tmdb_id.is_not(None))
    elif source == "manual":
        movie_query = movie_query.filter(Movie.tmdb_id.is_(None))

    if poster == "present":
        movie_query = movie_query.filter(Movie.poster_path.is_not(None), Movie.poster_path != "")
    elif poster == "missing":
        movie_query = movie_query.filter(or_(Movie.poster_path.is_(None), Movie.poster_path == ""))

    if sync_status == "not_applicable":
        movie_query = movie_query.filter(Movie.tmdb_id.is_(None))
    elif sync_status == "unknown":
        movie_query = movie_query.filter(Movie.tmdb_id.is_not(None), MovieVectorSyncJob.id.is_(None))
    elif sync_status != "all":
        movie_query = movie_query.filter(MovieVectorSyncJob.status == sync_status)

    total = movie_query.count()
    order_map = {
        "updated_desc": (Movie.updated_at.desc(), Movie.id.desc()),
        "release_desc": (Movie.release_date.desc().nullslast(), Movie.id.desc()),
        "views_desc": (func.coalesce(MovieStats.view_count, 0).desc(), Movie.id.desc()),
        "likes_desc": (func.coalesce(MovieStats.like_count, 0).desc(), Movie.id.desc()),
        "title_asc": (Movie.title.asc(), Movie.id.asc()),
    }
    rows = movie_query.order_by(*order_map[sort]).offset((page - 1) * limit).limit(limit).all()
    return {
        "state": "success",
        "message": "관리자 영화 목록 조회 성공",
        "data": {
            "items": [
                {
                    **admin_movie_to_dict(movie),
                    "poster_path": movie.poster_path,
                    "view_count": stats.view_count if stats else 0,
                    "like_count": stats.like_count if stats else 0,
                    "vector_sync": (
                        {
                            "status": sync_job.status,
                            "attempts": sync_job.attempts,
                            "last_error": sync_job.last_error,
                            "updated_at": _iso(sync_job.updated_at),
                        }
                        if sync_job is not None
                        else {"status": "not_applicable" if movie.tmdb_id is None else "unknown"}
                    ),
                }
                for movie, stats, sync_job in rows
            ],
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": max(1, (total + limit - 1) // limit),
        },
    }


@router.post("/movie/{movie_id}/tmdb-refresh")
async def refresh_admin_tmdb_movie(
    movie_id: int = Path(..., gt=0),
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """선택한 TMDB 영화의 메타데이터를 다시 가져오고 벡터 갱신을 예약한다."""
    movie = get_admin_movie(db=db, movie_id=movie_id)
    if movie is None:
        return {"state": "failure", "message": "영화를 찾을 수 없습니다."}
    if movie.tmdb_id is None:
        return {"state": "failure", "message": "직접 등록 영화는 TMDB 동기화를 사용할 수 없습니다."}

    before_data = admin_movie_to_dict(movie)
    try:
        movie_data = await fetch_admin_tmdb_movie_detail(tmdb_id=movie.tmdb_id)
        cast_credits = movie_data.pop("cast_credits", [])
        genres = normalize_string_list(movie_data.pop("genres", []))
        for key in (
            "title", "overview", "director", "cast", "keywords", "year", "release_date",
            "runtime", "production_countries", "certification", "certification_country",
            "language", "vote_average", "vote_count", "poster_path", "last_synced_at",
        ):
            if key in movie_data:
                setattr(movie, key, movie_data[key])
        sync_admin_movie_genres(db, movie, genres)
        db.execute(delete(MovieActor).where(MovieActor.movie_id == movie.id))
        sync_admin_movie_actors(db, movie, cast_credits)
        sync_movie_genre_weights(db=db, movie=movie)
        enqueue_movie_vector_sync(db, tmdb_id=movie.tmdb_id, movie_id=movie.id, operation="upsert")
        db.add(AdminAuditLog(
            admin_user_id=current_admin.id,
            target_table="movies",
            target_id=movie.id,
            action="REFRESH_TMDB_MOVIE",
            before_data=str(before_data),
            after_data=str(admin_movie_to_dict(movie)),
        ))
        db.commit()
        db.refresh(movie)
        return {"state": "success", "message": "TMDB 최신 정보와 벡터 동기화 작업을 반영했습니다.", "data": admin_movie_to_dict(movie)}
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        return error_response("TMDB 영화 재동기화 에러")


@router.post("/movie/{movie_id}/vector-sync-retry")
def retry_admin_movie_vector_sync(
    movie_id: int = Path(..., gt=0),
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    movie = get_admin_movie(db=db, movie_id=movie_id)
    if movie is None:
        return {"state": "failure", "message": "영화를 찾을 수 없습니다."}
    if movie.tmdb_id is None:
        return {"state": "failure", "message": "직접 등록 영화는 벡터 동기화 대상이 아닙니다."}
    enqueue_movie_vector_sync(db, tmdb_id=movie.tmdb_id, movie_id=movie.id, operation="upsert")
    db.add(AdminAuditLog(
        admin_user_id=current_admin.id,
        target_table="movie_vector_sync_jobs",
        target_id=movie.id,
        action="RETRY_VECTOR_SYNC",
        after_data=f"tmdb_id={movie.tmdb_id}",
    ))
    db.commit()
    return {"state": "success", "message": "벡터 동기화를 다시 예약했습니다."}


@router.get("/users")
def list_admin_users(
    query: str = Query("", max_length=100),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    user_query = db.query(User)
    normalized = query.strip()
    if normalized:
        user_query = user_query.filter(or_(User.email.ilike(f"%{normalized}%"), User.nickname.ilike(f"%{normalized}%")))
    total = user_query.count()
    users = user_query.order_by(User.created_at.desc(), User.id.desc()).offset((page - 1) * limit).limit(limit).all()
    return {
        "state": "success",
        "message": "관리자 사용자 목록 조회 성공",
        "data": {
            "items": [
                {
                    "id": user.id,
                    "email": user.email,
                    "nickname": user.nickname,
                    "is_admin": user.is_admin,
                    "is_suspended": user.is_suspended,
                    "suspended_at": _iso(user.suspended_at),
                    "suspended_reason": user.suspended_reason,
                    "onboarding_completed": user.onboarding_completed,
                    "created_at": _iso(user.created_at),
                }
                for user in users
            ],
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": max(1, (total + limit - 1) // limit),
        },
    }


@router.get("/audit-logs")
def list_admin_audit_logs(
    query: str = Query("", max_length=120),
    action: str = Query("all", max_length=50),
    page: int = Query(1, ge=1),
    limit: int = Query(30, ge=1, le=100),
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    audit_query = db.query(AdminAuditLog, User).outerjoin(User, User.id == AdminAuditLog.admin_user_id)
    normalized = query.strip()
    if normalized:
        conditions = [
            AdminAuditLog.action.ilike(f"%{normalized}%"),
            AdminAuditLog.target_table.ilike(f"%{normalized}%"),
            User.email.ilike(f"%{normalized}%"),
            User.nickname.ilike(f"%{normalized}%"),
        ]
        if normalized.isdigit():
            conditions.extend((AdminAuditLog.id == int(normalized), AdminAuditLog.target_id == int(normalized)))
        audit_query = audit_query.filter(or_(*conditions))
    if action != "all":
        audit_query = audit_query.filter(AdminAuditLog.action == action)

    total = audit_query.count()
    rows = (
        audit_query
        .order_by(AdminAuditLog.created_at.desc(), AdminAuditLog.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    actions = [row[0] for row in db.query(AdminAuditLog.action).distinct().order_by(AdminAuditLog.action).all()]
    return {
        "state": "success",
        "message": "감사 로그 조회 성공",
        "data": {
            "items": [
                {
                    "id": audit.id,
                    "action": audit.action,
                    "target_table": audit.target_table,
                    "target_id": audit.target_id,
                    "before_data": audit.before_data,
                    "after_data": audit.after_data,
                    "admin_id": audit.admin_user_id,
                    "admin_email": admin.email if admin else None,
                    "admin_nickname": admin.nickname if admin else "삭제된 관리자",
                    "created_at": _iso(audit.created_at),
                }
                for audit, admin in rows
            ],
            "actions": actions,
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": max(1, (total + limit - 1) // limit),
        },
    }


def _get_admin_user_target(db: Session, user_id: int) -> User:
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail={"state": "failure", "message": "사용자를 찾을 수 없습니다."})
    return target


def _ensure_destructive_user_action_allowed(db: Session, current_admin: User, target: User) -> None:
    if target.id == current_admin.id:
        raise HTTPException(
            status_code=409,
            detail={"state": "failure", "message": "현재 로그인한 관리자 계정에는 이 작업을 수행할 수 없습니다."},
        )
    if target.is_admin and not target.is_suspended:
        active_admin_count = db.query(func.count(User.id)).filter(
            User.is_admin.is_(True),
            User.is_suspended.is_(False),
        ).scalar() or 0
        if active_admin_count <= 1:
            raise HTTPException(
                status_code=409,
                detail={"state": "failure", "message": "마지막 활성 관리자 계정은 정지하거나 삭제할 수 없습니다."},
            )


@router.patch("/users/{user_id}/suspension")
def update_admin_user_suspension(
    request: AdminUserSuspensionRequest,
    user_id: int = Path(..., gt=0),
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    target = _get_admin_user_target(db, user_id)
    if target.is_suspended == request.is_suspended:
        return {"state": "failure", "message": "이미 요청한 계정 상태입니다."}
    if request.is_suspended:
        _ensure_destructive_user_action_allowed(db, current_admin, target)

    before = {
        "email": target.email,
        "is_suspended": target.is_suspended,
        "suspended_reason": target.suspended_reason,
    }
    now = datetime.now(timezone.utc)
    target.is_suspended = request.is_suspended
    target.suspended_at = now if request.is_suspended else None
    target.suspended_reason = request.reason if request.is_suspended else None
    if request.is_suspended:
        db.query(RefreshToken).filter(
            RefreshToken.user_id == target.id,
            RefreshToken.revoked_at.is_(None),
        ).update({RefreshToken.revoked_at: now}, synchronize_session=False)
    db.add(AdminAuditLog(
        admin_user_id=current_admin.id,
        target_table="users",
        target_id=target.id,
        action="SUSPEND_USER" if request.is_suspended else "UNSUSPEND_USER",
        before_data=json.dumps(before, ensure_ascii=False, default=str),
        after_data=json.dumps({
            "email": target.email,
            "is_suspended": target.is_suspended,
            "suspended_reason": target.suspended_reason,
        }, ensure_ascii=False, default=str),
    ))
    db.commit()
    return {
        "state": "success",
        "message": "계정을 정지하고 로그인 토큰을 폐기했습니다." if request.is_suspended else "계정 정지를 해제했습니다.",
        "data": {"user_id": target.id, "is_suspended": target.is_suspended},
    }


@router.delete("/users/{user_id}")
def delete_admin_user(
    user_id: int = Path(..., gt=0),
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    target = _get_admin_user_target(db, user_id)
    _ensure_destructive_user_action_allowed(db, current_admin, target)
    target_data = {
        "id": target.id,
        "email": target.email,
        "nickname": target.nickname,
        "is_admin": target.is_admin,
        "is_suspended": target.is_suspended,
    }
    profile_image = target.profile_image
    db.query(EmailVerificationCode).filter(func.lower(EmailVerificationCode.email) == target.email.strip().lower()).delete(synchronize_session=False)
    db.add(AdminAuditLog(
        admin_user_id=current_admin.id,
        target_table="users",
        target_id=target.id,
        action="DELETE_USER",
        before_data=json.dumps(target_data, ensure_ascii=False, default=str),
        after_data=None,
    ))
    db.delete(target)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail={"state": "error", "message": "계정 삭제 처리에 실패했습니다."})
    if profile_image:
        delet_user_profile_image(profile_image)
    return {"state": "success", "message": "계정과 관련 사용자 데이터를 삭제했습니다.", "data": target_data}

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

    except HTTPException:
        raise
    except Exception:
        return error_response("TMDB 영화 검색 에러")


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

    except HTTPException:
        db.rollback()
        raise
    except Exception:
        # TMDB 조회 또는 영화·장르·통계·감사 로그 저장 중 하나라도
        # 실패하면 트랜잭션 전체를 되돌려 일부 데이터가 남지 않게 한다.
        db.rollback()

        return error_response("TMDB 영화 등록 에러")


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

    except HTTPException:
        db.rollback()
        raise
    except Exception:
        # 영화, 장르, 초기 통계 또는 감사 로그 처리 중 하나라도 실패하면
        # 현재 트랜잭션의 모든 DB 변경을 되돌려 일부 데이터가 남지 않게 한다.
        db.rollback()

        return error_response("직접 입력 영화 등록 에러")


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
        if "title" in update_data or "year" in update_data or "release_date" in update_data:
            final_title = update_data.get("title", movie.title)
            if update_data.get("release_date") is not None:
                final_year = update_data["release_date"].year
            else:
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

    except HTTPException:
        db.rollback()
        raise
    except Exception:
        # 영화, 장르 또는 감사 로그 처리 중 하나라도 실패하면 현재
        # 트랜잭션 전체를 되돌려 일부 데이터만 변경되는 것을 방지한다.
        db.rollback()

        return error_response("영화 수정 중 에러가 발생했습니다.")


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

    except HTTPException:
        db.rollback()
        raise
    except Exception:
        # 영화 삭제나 감사 로그 저장 중 하나라도 실패하면 현재 트랜잭션의
        # 모든 변경을 되돌려 일부 데이터만 삭제되는 상황을 방지한다.
        db.rollback()

        return error_response("영화 삭제 중 에러가 발생했습니다.")


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
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        # 권한 변경 중 오류가 발생하면 저장 전 상태로 되돌린다.
        db.rollback()
        return error_response("관리자 부여 에러")
