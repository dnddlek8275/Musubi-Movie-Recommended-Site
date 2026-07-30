import httpx

from app.core.config import settings
from app.ai_client.base import post_ai


# AI 서버의 POST /chat/auto API 호출
# 기본 AI 채팅, 캐릭터 AI 채팅, 그룹 AI 채팅 모두 자동 분류용
async def request_ai_chat(
    message: str,
    history: list[dict],
    character: str | None = None,
) -> dict:
    payload = {
        "message" : message,
        "history" : history
    }
    # 캐릭터가 있는 경우
    if character: payload["character"] = character
    return await post_ai("/chat/auto", payload)

# 특정 캐릭터와 1:1 대화용
async def request_character_chat(
    message: str,
    history: list[dict],
    character: str,
) -> dict:
    payload = {
        "message" : message,
        "history" : history,
        "character" : character
    }
    return await post_ai("/chat/auto", payload)

# 1대1대화 전용 stream챗
async def stream_character_chat(
    message : str,
    history : list[dict],
    character : str,
    use_rag : bool = True,
):
    payload = {
        "character" : character,
        "message" : message,
        "history" : history,
        "use_rag" : use_rag,
    }

    # AI 서버 주소
    ai_base_url = settings.AI_BASE_URL.rstrip("/")

    # 스트리밍은 오래 열려 있을 수 있음 - timeout=None
    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream("POST", f"{ai_base_url}/chat/stream", json=payload) as response:
            response.raise_for_status()

            # AI 서버가 보내는 SSE 라인을 한줄씩 읽음
            async for line in response.aiter_lines():
                if not line:
                    continue

                yield f"{line}\n\n"


# 그룹 채팅용
async def request_group_chat(
    characters: list[str],
    message: str,
    history: list[dict],
) -> dict:
    payload = {
        "characters": characters,
        "message": message,
        "history": history,
    }
    return await post_ai("/chat/group/auto", payload)