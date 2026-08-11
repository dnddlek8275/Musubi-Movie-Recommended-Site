import asyncio
from contextlib import suppress
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Depends, HTTPException
import httpx
from sqlalchemy import text
import uvicorn
from app.api.auth import router as auth_router
from app.api.movies import router as movies_router
from app.api.chat import router as chat_router
from app.api.users import router as users_router
from app.api.admin import router as admin_router
from app.api.audio import router as audio_router
from app.api.contact import router as contact_router
from sqlalchemy.orm import Session
from app.core.dependencies import SessionLocal, get_db
from app.core.config import settings
from app.core.api_responses import error_response
from fastapi.middleware.cors import CORSMiddleware
from app.services.movies.ranking_service import ensure_daily_ranking_snapshot
from app.services.movies.box_office_service import refresh_daily_box_office
from app.services.ai_usage_service import AiUsageMiddleware

app = FastAPI()
app.add_middleware(AiUsageMiddleware)

KST = ZoneInfo("Asia/Seoul")
_ranking_snapshot_task = None
_box_office_task = None


def _seconds_until_next_kst_midnight() -> float:
    now = datetime.now(KST)
    next_midnight = datetime.combine(now.date() + timedelta(days=1), time.min, tzinfo=KST)
    return max(1.0, (next_midnight - now).total_seconds())


def _seconds_until_next_box_office_refresh() -> float:
    now = datetime.now(KST)
    next_run = datetime.combine(now.date(), time(hour=6), tzinfo=KST)
    if next_run <= now:
        next_run += timedelta(days=1)
    return max(1.0, (next_run - now).total_seconds())


def _create_today_ranking_snapshot() -> None:
    db = SessionLocal()
    try:
        ensure_daily_ranking_snapshot(db)
    finally:
        db.close()


async def _daily_ranking_snapshot_loop() -> None:
    while True:
        await asyncio.sleep(_seconds_until_next_kst_midnight())
        _create_today_ranking_snapshot()


async def _refresh_yesterday_box_office() -> None:
    db = SessionLocal()
    try:
        await refresh_daily_box_office(db)
    except Exception as error:
        db.rollback()
        print(f"[KOBIS] 일일 박스오피스 갱신 실패: {error}")
    finally:
        db.close()


async def _daily_box_office_loop() -> None:
    while True:
        await asyncio.sleep(_seconds_until_next_box_office_refresh())
        await _refresh_yesterday_box_office()


@app.on_event("startup")
async def start_daily_ranking_snapshot_task():
    global _ranking_snapshot_task, _box_office_task
    _create_today_ranking_snapshot()
    await _refresh_yesterday_box_office()
    _ranking_snapshot_task = asyncio.create_task(_daily_ranking_snapshot_loop())
    _box_office_task = asyncio.create_task(_daily_box_office_loop())


@app.on_event("shutdown")
async def stop_daily_ranking_snapshot_task():
    global _ranking_snapshot_task, _box_office_task
    tasks = [task for task in (_ranking_snapshot_task, _box_office_task) if task]
    for task in tasks:
        task.cancel()
    for task in tasks:
        with suppress(asyncio.CancelledError):
            await task
    _ranking_snapshot_task = None
    _box_office_task = None

# 개인 정보 캐시 방지 목적
@app.middleware("http")
async def no_store_private_api_cache(request, call_next):
    response = await call_next(request)

    # 인증·개인정보 응답뿐 아니라 관리자 검색·권한·데이터 변경 응답에도
    # 민감한 정보가 포함될 수 있으므로 브라우저와 중간 캐시 서버가
    # 해당 API 응답을 저장하거나 재사용하지 못하도록 설정한다.
    if request.url.path.startswith(("/auth", "/chat", "/user", "/admin", "/audio", "/contact")):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"

    return response

# 프론트 서버
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# auth.py의 Router 등록
app.include_router(auth_router)

# movies.py의 Router 등록
app.include_router(movies_router)

# /chat router 등록
app.include_router(chat_router)

# /users router 등록
app.include_router(users_router)

# /admin router 등록
app.include_router(admin_router)

# /audio router 등록
app.include_router(audio_router)

# 공통 푸터 문의 접수
app.include_router(contact_router)

@app.get("/")
def index():
    return {"state": "success", "message": "Musubi API is running"}

#실행 확인 여부
@app.get("/health")
def root():
    try:
        return {
            "state" : "success",
            "message": "Musubi"
            }
    except Exception:
        return error_response("BE1 Health Check API 호출 실패")


# Kubernetes readiness용 DB 연결 검사
@app.get("/ready")
def readiness_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {
            "state": "success",
            "message": "Musubi Backend is ready",
        }
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail={
                "state": "error",
                "message": "PostgreSQL에 연결할 수 없습니다.",
            },
        )


# PostgreSQL 연결 테스트 API
@app.get("/db-test")
async def db_test(db: Session = Depends(get_db)):
    try:
        # PostgreSQL에 간단한 쿼리 실행
        db.execute(text("SELECT 1"))
        return {
            "state" : "success",
            "message": "PostgreSQL 연결 성공"
        }

    except Exception:
        return error_response("BE2 DB 연결 확인 중 에러가 발생했습니다.")
    

# 연결된 AI 서버의 상태와 응답 코드를 확인한다.
@app.get("/ai-health")
async def ai_health_check():
    ai_base_url = settings.AI_BASE_URL.rstrip("/")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{ai_base_url}/health",
                timeout=5.0,
            )
            response.raise_for_status()

        return {
            "state": "success",
            "message": "AI 서버 연결에 성공했습니다.",
            "data": {
                "ai_base_url": ai_base_url,
                "status_code": response.status_code,
            },
        }

    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail={
                "state": "error",
                "message": "AI 서버 응답 시간이 초과되었습니다.",
            },
        )

    except httpx.RequestError as e:
        raise HTTPException(
            status_code=502,
            detail={
                "state": "error",
                "message": "AI 서버에 연결할 수 없습니다.",
            },
        )

    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=502,
            detail={
                "state": "error",
                "message": "AI 서버가 정상 상태를 반환하지 않았습니다.",
                "data": {
                    "ai_base_url": ai_base_url,
                    "status_code": e.response.status_code,
                },
            },
        )

# 수행하면 바로 console창에 main:app 명령 없이 특정 포트로 바로 수행되게 처리..
if __name__ =="__main__":
    # 작성된 파일을 main.py로 저장했을 경우를 가정하고 서버를 실행합니다.
    # 포트를 8080으로 지정하여 localhost:8080에서 확인 가능하도록 설정합니다.
    # uvicorn.run("main:app", host="127.0.0.1", port=8080, reload=True)
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)
