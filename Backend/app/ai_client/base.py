from fastapi import HTTPException
import httpx

from app.core.config import settings


# AI 서버에 POST 요청을 보내는 공통 함수입니다.
# 실제 AI API 경로는 app/ai_client/chat.py 같은 파일에서 넘겨줍니다.
async def post_ai(path: str, payload: dict) -> dict:
    # settings.AI_BASE_URL 예: "http://210.109.15.251"
    # 주소 끝의 "/"를 제거해서 "/chat"과 합칠 때 중복 슬래시가 생기지 않게 합니다.
    ai_base_url = settings.AI_BASE_URL.rstrip("/")
    ai_path = path if path.startswith("/") else f"/{path}"

    try:
        # FastAPI async 함수 안에서 외부 서버를 호출하므로 비동기 클라이언트를 사용합니다.
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{ai_base_url}{ai_path}",
                json=payload,
                # AI 서버 응답 생성 시간이 길 수 있으므로 30초 이상으로 설정합니다.
                timeout=30.0,
            )

        # 4xx, 5xx 응답이면 HTTPStatusError가 발생합니다.
        response.raise_for_status()
        return response.json()

    except httpx.TimeoutException:
        # AI 서버가 제한 시간 안에 응답하지 않은 경우입니다.
        raise HTTPException(
            status_code=504,
            detail={
                "state": "error",
                "message": "AI 서버 응답 시간이 초과되었습니다.",
            }
        )

    except httpx.RequestError as e:
        # AI 서버까지 요청이 도달하지 못한 경우입니다.
        # 예: 서버 꺼짐, 네트워크 연결 실패, 잘못된 주소 등
        raise HTTPException(
            status_code=502,
            detail={
                "state": "error",
                "message": "AI 서버에 연결할 수 없습니다.",
                "error": str(e),
            }
        )

    except httpx.HTTPStatusError as e:
        # AI 서버에는 연결됐지만 400, 422, 500 같은 실패 응답을 받은 경우입니다.
        raise HTTPException(
            status_code=e.response.status_code,
            detail={
                "state": "error",
                "message": "AI 서버가 에러 응답을 반환했습니다.",
                "error": e.response.text,
            }
        )
