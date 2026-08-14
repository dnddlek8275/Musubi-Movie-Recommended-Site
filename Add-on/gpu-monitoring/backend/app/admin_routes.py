import math
import sqlite3
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from .admin_dependencies import current_user, database, require_admin, settings
from .admin_schemas import AdminUser, ApiResponse, LoginRequest, RefreshRequest
from .auth import TokenError, create_token, decode_token, verify_password
from .gpu_service import GpuService, GpuUnavailableError


def user_data(row: sqlite3.Row) -> dict:
    return AdminUser(**{key: row[key] for key in AdminUser.model_fields}).model_dump()


def tokens_for(user: sqlite3.Row) -> dict:
    return {
        "access_token": create_token(user["id"], user["role"], "access", settings.admin_secret_key, settings.admin_access_minutes * 60),
        "refresh_token": create_token(user["id"], user["role"], "refresh", settings.admin_secret_key, settings.admin_refresh_days * 86400),
        "token_type": "bearer",
        "expires_in": settings.admin_access_minutes * 60,
    }


def create_admin_router(gpu_service: GpuService) -> APIRouter:
    router = APIRouter(prefix="/api/admin", tags=["Admin"])

    @router.post("/auth/login", response_model=ApiResponse)
    def login(payload: LoginRequest, request: Request) -> ApiResponse:
        user = database.user_by_email(payload.identifier.strip().lower())
        if not user or not verify_password(payload.password, user["password_hash"]):
            database.add_log(admin=user if user and user["role"] in ("ADMIN", "SUPER_ADMIN") else None, action="LOGIN_FAILED", request=request, description="관리자 로그인 실패")
            raise HTTPException(status_code=401, detail="이메일 또는 비밀번호가 올바르지 않습니다")
        if user["role"] not in ("ADMIN", "SUPER_ADMIN"):
            database.add_log(admin=user, action="LOGIN_FORBIDDEN", request=request, description="관리자 권한이 없는 계정의 접근")
            raise HTTPException(status_code=403, detail="관리자 권한이 없습니다")
        if user["status"] != "ACTIVE":
            raise HTTPException(status_code=403, detail="비활성화되거나 정지된 계정입니다")
        database.update_login(user["id"])
        refreshed = database.user_by_id(user["id"])
        assert refreshed is not None
        database.add_log(admin=refreshed, action="LOGIN", request=request, description="관리자 로그인")
        return ApiResponse(message="로그인되었습니다.", data={"user": user_data(refreshed), **tokens_for(refreshed)})

    @router.post("/auth/logout", response_model=ApiResponse)
    def logout(request: Request, user: sqlite3.Row = Depends(require_admin)) -> ApiResponse:
        database.add_log(admin=user, action="LOGOUT", request=request, description="관리자 로그아웃")
        return ApiResponse(message="로그아웃되었습니다.", data={})

    @router.get("/auth/me", response_model=ApiResponse)
    def me(user: sqlite3.Row = Depends(require_admin)) -> ApiResponse:
        return ApiResponse(data=user_data(user))

    @router.post("/auth/refresh", response_model=ApiResponse)
    def refresh(payload: RefreshRequest) -> ApiResponse:
        try:
            token = decode_token(payload.refresh_token, settings.admin_secret_key, "refresh")
        except TokenError as exc:
            raise HTTPException(status_code=401, detail="Refresh token has expired or is invalid") from exc
        user = database.user_by_id(int(token["sub"]))
        if not user or user["status"] != "ACTIVE" or user["role"] not in ("ADMIN", "SUPER_ADMIN"):
            raise HTTPException(status_code=401, detail="Account is unavailable")
        return ApiResponse(data=tokens_for(user))

    @router.get("/dashboard/summary", response_model=ApiResponse)
    def dashboard_summary(_: sqlite3.Row = Depends(require_admin)) -> ApiResponse:
        with database.connect() as connection:
            row = connection.execute(
                """SELECT COUNT(*) total_users,
                SUM(CASE WHEN status='ACTIVE' THEN 1 ELSE 0 END) active_users,
                SUM(CASE WHEN status!='ACTIVE' THEN 1 ELSE 0 END) inactive_users,
                SUM(CASE WHEN date(created_at)=date('now') THEN 1 ELSE 0 END) today_users,
                SUM(CASE WHEN role IN ('ADMIN','SUPER_ADMIN') THEN 1 ELSE 0 END) admins
                FROM users WHERE deleted_at IS NULL"""
            ).fetchone()
        return ApiResponse(data={
            "total_users": row["total_users"] or 0, "active_users": row["active_users"] or 0,
            "inactive_users": row["inactive_users"] or 0, "today_users": row["today_users"] or 0,
            "admins": row["admins"] or 0, "registered_servers": 1, "connected_servers": 1 if gpu_service.nvml_available else 0,
            "disconnected_servers": 0 if gpu_service.nvml_available else 1, "unconfirmed_alerts": 0, "pending_inquiries": 0,
        })

    @router.get("/dashboard/gpu-summary", response_model=ApiResponse)
    def gpu_summary(_: sqlite3.Row = Depends(require_admin)) -> ApiResponse:
        try:
            gpus = gpu_service.list_gpus()
        except GpuUnavailableError:
            return ApiResponse(message="NVIDIA GPU or NVML is not available", data={"state": "unavailable", "total_gpus": 0, "average_gpu_usage": None, "average_memory_usage": None, "average_temperature": None, "process_count": 0, "danger_gpu_count": 0})
        def average(values: list[float | None]) -> float | None:
            present = [value for value in values if value is not None]
            return round(sum(present) / len(present), 1) if present else None
        return ApiResponse(data={
            "state": "success", "total_gpus": len(gpus),
            "average_gpu_usage": average([gpu.gpu_usage_percent for gpu in gpus]),
            "average_memory_usage": average([gpu.memory_usage_percent for gpu in gpus]),
            "average_temperature": average([gpu.temperature_celsius for gpu in gpus]),
            "process_count": sum(len(gpu.processes) for gpu in gpus),
            "danger_gpu_count": sum(1 for gpu in gpus if (gpu.gpu_usage_percent or 0) >= 90 or (gpu.memory_usage_percent or 0) >= 90 or (gpu.temperature_celsius or 0) >= 85),
        })

    @router.get("/dashboard/recent-users", response_model=ApiResponse)
    def recent_users(_: sqlite3.Row = Depends(require_admin)) -> ApiResponse:
        with database.connect() as connection:
            rows = connection.execute("SELECT * FROM users WHERE deleted_at IS NULL ORDER BY created_at DESC LIMIT 5").fetchall()
        return ApiResponse(data=[user_data(row) for row in rows])

    @router.get("/dashboard/recent-alerts", response_model=ApiResponse)
    def recent_alerts(_: sqlite3.Row = Depends(require_admin)) -> ApiResponse:
        return ApiResponse(message="경고 저장 기능은 2차 구현 범위입니다.", data=[])

    @router.get("/dashboard/recent-inquiries", response_model=ApiResponse)
    def recent_inquiries(_: sqlite3.Row = Depends(require_admin)) -> ApiResponse:
        return ApiResponse(message="문의 기능은 3차 구현 범위입니다.", data=[])

    @router.get("/dashboard/recent-logs", response_model=ApiResponse)
    def recent_logs(_: sqlite3.Row = Depends(require_admin)) -> ApiResponse:
        with database.connect() as connection:
            rows = connection.execute("SELECT * FROM admin_activity_logs ORDER BY created_at DESC LIMIT 5").fetchall()
        return ApiResponse(data=[dict(row) for row in rows])

    @router.get("/users", response_model=ApiResponse)
    def users(
        page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100), search: str = "",
        sort: Literal["created_at", "last_login_at", "name", "id"] = "created_at",
        order: Literal["asc", "desc"] = "desc", status: str | None = None, role: str | None = None,
        _: sqlite3.Row = Depends(require_admin),
    ) -> ApiResponse:
        conditions = ["deleted_at IS NULL"]
        parameters: list[object] = []
        if search:
            conditions.append("(name LIKE ? OR nickname LIKE ? OR email LIKE ? OR CAST(id AS TEXT) LIKE ?)")
            term = f"%{search.strip()}%"
            parameters.extend([term, term, term, term])
        if status:
            conditions.append("status = ?")
            parameters.append(status.upper())
        if role:
            conditions.append("role = ?")
            parameters.append(role.upper())
        where = " AND ".join(conditions)
        with database.connect() as connection:
            total = connection.execute(f"SELECT COUNT(*) FROM users WHERE {where}", parameters).fetchone()[0]
            rows = connection.execute(f"SELECT * FROM users WHERE {where} ORDER BY {sort} {order.upper()} LIMIT ? OFFSET ?", [*parameters, size, (page - 1) * size]).fetchall()
        return ApiResponse(data={"items": [user_data(row) for row in rows], "page": page, "size": size, "total": total, "total_pages": math.ceil(total / size) if total else 0})

    @router.get("/users/{user_id}", response_model=ApiResponse)
    def user_detail(user_id: int, _: sqlite3.Row = Depends(require_admin)) -> ApiResponse:
        user = database.user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User was not found")
        return ApiResponse(data=user_data(user))

    @router.get("/logs", response_model=ApiResponse)
    def logs(page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100), search: str = "", action: str | None = None, _: sqlite3.Row = Depends(require_admin)) -> ApiResponse:
        conditions = ["1=1"]
        parameters: list[object] = []
        if search:
            conditions.append("(admin_name LIKE ? OR description LIKE ? OR target_id LIKE ?)")
            term = f"%{search.strip()}%"
            parameters.extend([term, term, term])
        if action:
            conditions.append("action = ?")
            parameters.append(action)
        where = " AND ".join(conditions)
        with database.connect() as connection:
            total = connection.execute(f"SELECT COUNT(*) FROM admin_activity_logs WHERE {where}", parameters).fetchone()[0]
            rows = connection.execute(f"SELECT * FROM admin_activity_logs WHERE {where} ORDER BY created_at DESC LIMIT ? OFFSET ?", [*parameters, size, (page - 1) * size]).fetchall()
        return ApiResponse(data={"items": [dict(row) for row in rows], "page": page, "size": size, "total": total, "total_pages": math.ceil(total / size) if total else 0})

    return router
