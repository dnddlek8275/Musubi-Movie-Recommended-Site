from pathlib import Path

from fastapi import FastAPI, Depends
from fastapi.staticfiles import StaticFiles
import httpx
from sqlalchemy import text
import uvicorn
from app.api.auth import router as auth_router
from app.api.movies import router as movies_router
from app.api.chat import router as chat_router
from app.api.users import router as users_router
from app.api.admin import router as admin_router
from app.api.audio import router as audio_router
from sqlalchemy.orm import Session
from app.core.dependencies import get_db
from app.core.config import settings
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# 개인 정보 캐시 방지 목적
@app.middleware("http")
async def no_store_private_api_cache(request, call_next):
    response = await call_next(request)

    # 인증·개인정보 응답뿐 아니라 관리자 검색·권한·데이터 변경 응답에도
    # 민감한 정보가 포함될 수 있으므로 브라우저와 중간 캐시 서버가
    # 해당 API 응답을 저장하거나 재사용하지 못하도록 설정한다.
    if request.url.path.startswith(("/auth", "/chat", "/user", "/admin", "/audio")):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"

    return response

# 사용자 프로필, 영화 포스터, 배우 프로필처럼 서비스에서 업로드하는 파일을
# 한 경로에서 관리할 수 있도록 app/uploads 폴더 전체를 정적 파일 경로로 사용한다.
# Path(__file__).resolve().parent는 현재 main.py가 위치한 app 폴더를 의미한다.
UPLOAD_DIR = Path(__file__).resolve().parent / "uploads"

# 실행 환경에 uploads 폴더가 없으면 StaticFiles 연결 과정에서 오류가 발생할 수 있다.
# 필요한 상위 폴더까지 생성하되, 이미 폴더가 있는 경우에는 그대로 사용한다.
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# 브라우저에서 /uploads로 시작하는 URL을 요청하면 app/uploads 내부 파일을 반환한다.
# 예: /uploads/images/user_profiles/profile.jpg
#     -> app/uploads/images/user_profiles/profile.jpg
app.mount(
    "/uploads",
    StaticFiles(directory=UPLOAD_DIR),
    name="uploads",
)


# 프론트 서버
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        # "http://192.168.45.103:5173",
    ],
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

@app.get("/")
def index():
    return {"state": "success", "message": "CineVerse API is running"}

#실행 확인 여부
@app.get("/health")
def root():
    try:
        return {
            "state" : "success",
            "message": "CineVerse"
            }
    except Exception as e:
        return {
            "state" : "error",
            "message": "BE1 Health Check API 호출 실패", 
            "error": str(e)
            }


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

    except Exception as e:
        return {
            "state" : "error",
            "message": "BE2 DB 연결 확인 중 에러가 발생했습니다.",
            "error": str(e)
        }
    

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

        return {
            "state": "success",
            "message": "AI 서버 연결에 성공했습니다.",
            "data": {
                "ai_base_url": ai_base_url,
                "status_code": response.status_code,
            },
        }

    except httpx.TimeoutException as e:
        return {
            "state": "error",
            "message": "AI 서버 응답 시간이 초과되었습니다.",
            "error": str(e),
        }

    except httpx.RequestError as e:
        return {
            "state": "error",
            "message": "AI 서버에 연결할 수 없습니다.",
            "error": str(e),
        }

# 수행하면 바로 console창에 main:app 명령 없이 특정 포트로 바로 수행되게 처리..
if __name__ =="__main__":
    # 작성된 파일을 main.py로 저장했을 경우를 가정하고 서버를 실행합니다.
    # 포트를 8080으로 지정하여 localhost:8080에서 확인 가능하도록 설정합니다.
    # uvicorn.run("main:app", host="127.0.0.1", port=8080, reload=True)
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)
