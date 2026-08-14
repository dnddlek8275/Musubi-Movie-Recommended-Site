import httpx
from fastapi import HTTPException

from app.core.config import settings
from app.ai_client.base import post_ai


AI_STREAM_TIMEOUT = httpx.Timeout(
    connect=5.0,
    read=60.0,
    write=30.0,
    pool=5.0,
)


class CharacterChatStream:
    def __init__(self, client: httpx.AsyncClient, response: httpx.Response):
        self.client = client
        self.response = response

    async def iter_lines(self):
        try:
            async for line in self.response.aiter_lines():
                if line:
                    yield line
        except httpx.TimeoutException as exc:
            raise HTTPException(
                status_code=504,
                detail={
                    "state": "error",
                    "message": "AI 스트리밍 응답 시간이 초과되었습니다.",
                },
            ) from exc
        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=502,
                detail={
                    "state": "error",
                    "message": "AI 스트리밍 연결이 중단되었습니다.",
                },
            ) from exc

    async def aclose(self):
        await self.response.aclose()
        await self.client.aclose()


# AI 서버의 POST /chat/auto API 호출
# 기본 AI 채팅, 캐릭터 AI 채팅, 그룹 AI 채팅 모두 자동 분류용
async def request_ai_chat(
    message: str,
    history: list[dict],
    character: str | None = None,
    user_context: str | None = None,
) -> dict:
    payload = {
        "message" : message,
        "history" : history
    }
    # 캐릭터가 있는 경우
    if character: payload["character"] = character
    if user_context: payload["user_context"] = user_context
    return await post_ai("/chat/auto", payload)


async def request_chat_title(message: str) -> dict:
    try:
        return await post_ai("/chat/title", {"message": message})
    except HTTPException as exc:
        # 현재 운영 AI 서버가 제목 전용 경로를 아직 배포하지 않은 경우에만
        # 기존 LLM 경로를 사용한다. 전용 경로 배포 후에는 이 fallback을 타지 않는다.
        if exc.status_code != 502:
            raise

    prompt = (
        "아래 사용자 문장의 핵심을 대화 기록용 한국어 제목 하나로 요약하세요. "
        "8~20자 내외로 쓰고 따옴표, 설명, 답변 없이 제목만 출력하세요.\n\n"
        f"사용자 문장: {message}"
    )
    result = await post_ai("/chat/auto", {"message": prompt, "history": []})
    return {"title": result.get("answer") or ""}


# 특정 캐릭터와 1:1 대화용
async def request_character_chat(
    message: str,
    history: list[dict],
    character: str,
    user_context: str | None = None,
) -> dict:
    payload = {
        "message" : message,
        "history" : history,
        "character" : character
    }
    if user_context: payload["user_context"] = user_context
    return await post_ai("/chat/auto", payload)

# 1대1 대화용 AI stream을 미리 연결한다.
# StreamingResponse의 HTTP 200 헤더를 보내기 전에 연결 오류를 판별하기 위함이다.
async def open_character_chat_stream(
    message : str,
    history : list[dict],
    character : str,
    use_rag : bool = True,
    user_context: str | None = None,
):
    payload = {
        "character" : character,
        "message" : message,
        "history" : history,
        "use_rag" : use_rag,
    }
    if user_context: payload["user_context"] = user_context

    # AI 서버 주소
    ai_base_url = settings.AI_BASE_URL.rstrip("/")

    client = httpx.AsyncClient(timeout=AI_STREAM_TIMEOUT)
    request = client.build_request(
        "POST",
        f"{ai_base_url}/chat/stream",
        json=payload,
    )

    try:
        response = await client.send(request, stream=True)
        response.raise_for_status()
        return CharacterChatStream(client, response)
    except httpx.TimeoutException as exc:
        await client.aclose()
        raise HTTPException(
            status_code=504,
            detail={
                "state": "error",
                "message": "AI 스트리밍 연결 시간이 초과되었습니다.",
            },
        ) from exc
    except httpx.RequestError as exc:
        await client.aclose()
        raise HTTPException(
            status_code=502,
            detail={
                "state": "error",
                "message": "AI 스트리밍 서버에 연결할 수 없습니다.",
            },
        ) from exc
    except httpx.HTTPStatusError as exc:
        await exc.response.aclose()
        await client.aclose()
        raise HTTPException(
            status_code=502,
            detail={
                "state": "error",
                "message": "AI 스트리밍 서버가 에러 응답을 반환했습니다.",
                "data": {
                    "upstream_status_code": exc.response.status_code,
                },
            },
        ) from exc


# 그룹 채팅용
async def request_group_chat(
    characters: list[str],
    message: str,
    history: list[dict],
    user_context: str | None = None,
) -> dict:
    payload = {
        "characters": characters,
        "message": message,
        "history": history,
    }
    if user_context: payload["user_context"] = user_context
    return await post_ai("/chat/group/auto", payload)
