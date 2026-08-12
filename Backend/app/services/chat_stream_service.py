import json
import re

from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.ai_client.chat import CharacterChatStream, open_character_chat_stream
from app.repositories.chat_repository import create_message, create_room, get_room_messages, get_room_user, make_ai_history
from app.schemas.chat import CharacterChatRequest, SendChatMessageRequest
from app.services.character_service import get_active_character
from app.services.chat_service import process_chat_message
from app.services.chat_context_service import build_chat_user_context
from app.services.movies.chat_movie_link_service import enrich_recommended_movies


# AI 서버가 답변 앞에 보내는 내부 제어 문자열을 찾는 정규식
# 사용자에게 보여줄 실제 답변이 아니므로 스트림 시작 부분에서 제거
# AI_CONTROL_PREFIX = re.compile(
#     # <|channel>과 <|channel|> 형식을 모두 허용
#     # 그 뒤에는 thought, analysis, final
#     r"^[ \t]*<\|channel\|?>[ \t]*(?:thought|analysis|final)[ \t]*"
#     # 채널 표시 뒤의 실제 개행, 문자열 형태의 \n,
#     # 또는 <|message|> 제어 토큰까지 함께 제거
#     r"(?:(?:\\n)|\r?\n|<\|message\|>)+[ \t]*",
#     re.IGNORECASE,
# )

# # 아직 완성되지 않은 AI 제어 토큰인지 확인
# def is_control_prefix_candidate(text: str) -> bool:
#     value = text.lstrip()
#     return (
#         # "<", "<|", "<|channel"처럼 제어 토큰의 일부만 받은 경우
#         "<|channel".startswith(value)
#         # "<|channel>thought"처럼 제어 토큰으로 시작하는 경우
#         or value.startswith("<|channel")
#     )

# stream 끝난 캐릭터 답변 저장
async def stream_and_save_character_answer(
        db:Session,
        room_id : int,
        message : str,
        history : list[dict],
        character : str,
        ai_stream: CharacterChatStream,
):
    answer_parts = []
    response_metadata = {}
    # 제어 토큰이 여러 조각으로 들어오는 경우를 위한 시작 버퍼
    leading_buffer = ""
    prefix_checked = False

    try:
        async for line in ai_stream.iter_lines():
            chunk = f"{line}\n\n"
            yield chunk

            if chunk.startswith("data: "):
                data = chunk.removeprefix("data: ").strip()

                if data == "[DONE]":
                    continue

                try:
                    parsed = json.loads(data)
                    text = ""
                    if isinstance(parsed, str):
                        answer_parts.append(parsed)
                        text = parsed
                    elif isinstance(parsed, dict) and "error" not in parsed:
                        answer_parts.append(parsed.get("answer", ""))
                        text = parsed.get("answer", "")
                        response_metadata.update(parsed)
                except json.JSONDecodeError:
                    answer_parts.append(data)
                    text = data

                if not text:
                    continue

                # 첫 조각들만 합쳐 제어 토큰 검사
                # if not prefix_checked:
                #     leading_buffer += text
                #     match = AI_CONTROL_PREFIX.match(leading_buffer)

                #     if match:
                #         text = leading_buffer[match.end():]
                #         prefix_checked = True
                #     # 제어 토큰이 아직 완성되지 않았으므로 다음 조각 대기
                #     elif is_control_prefix_candidate(leading_buffer):
                #         continue
                #     else:
                #         text = leading_buffer
                #         prefix_checked = True

                # if not text:
                #     continue

                # answer_parts.append(text)
                # # 정제한 조각만 정상 SSE 형식으로 전달
                # yield f"data: {json.dumps(text, ensure_ascii=False)}\n\n"

    except HTTPException as exc:
        yield (
            "data: "
            + json.dumps(exc.detail, ensure_ascii=False)
            + "\n\n"
        )
    finally :
        await ai_stream.aclose()
        # 스트림 정상 종료시 모아둔 답변 assistant 메시지로 저장
        answer = "".join(answer_parts).strip()
        if answer:
            create_message(
                db,
                room_id,
                "assistant",
                answer,
                response_metadata.get("character") or character,
                recommended_movies=enrich_recommended_movies(db, response_metadata.get("movies")) or None,
                emotion=response_metadata.get("emotion"),
            )
            db.commit()

def make_streaming_response(generator):
    return StreamingResponse(
        generator,
        media_type = "text/event-stream",
        headers ={
            "Cache-Control" : "no-cache",
            "X-Accel-Buffering" : "no",
        },
    )


async def commit_before_streaming(db: Session, ai_stream: CharacterChatStream):
    try:
        db.commit()
    except Exception:
        await ai_stream.aclose()
        raise


async def start_character_chat_stream(db: Session, user_id: int, request: CharacterChatRequest):
    # 새 1대1 캐릭터 스트림 채팅방 생성
    message = request.message.strip()

    if not message:
        return {
            "state": "failure",
            "message": "내용을 입력해주세요.",
        }

    # 별칭을 정식 캐릭터명으로 변환
    character = get_active_character(db, request.character)

    if character is None:
        return {
            "state": "failure",
            "message": "지원하지 않는 캐릭터입니다.",
            "data": {
                "character": request.character,
            },
        }

    # 스트림은 캐릭터 대화 전용이므로 character 방으로 생성
    room = create_room(db, user_id, character)

    # 새 방이라 이전 히스토리는 없음
    history = []

    # 사용자 메시지는 먼저 저장
    create_message(
        db=db,
        room_id=room.id,
        role="user",
        content=message,
    )

    ai_stream = await open_character_chat_stream(
        message=message,
        history=history,
        character=character,
        user_context=build_chat_user_context(db, user_id),
    )
    await commit_before_streaming(db, ai_stream)

    return make_streaming_response(
        stream_and_save_character_answer(
            db=db,
            room_id=room.id,
            message=message,
            history=history,
            character=character,
            ai_stream=ai_stream,
        )
    )

# 방 유형에 따라 일반 JSON 채팅 또는 캐릭터 스트리밍 대화를 이어간다.
async def continue_chat_stream(db: Session, user_id: int, room_id: int, request: SendChatMessageRequest):
    message = request.content.strip()

    if not message:
        return {
            "state": "failure",
            "message": "내용을 입력해주세요.",
        }

    room = get_room_user(db, room_id, user_id)

    if not room:
        return {
            "state": "failure",
            "message": "채팅방을 찾을 수 없습니다.",
        }

    # general 방은 저장된 마지막 캐릭터에 고정하지 않고 일반 AI 흐름을 유지한다.
    if room.room_type == "general":
        return await process_chat_message(
            db=db,
            room=room,
            message=message,
            character=request.character,
        )

    # AI /chat/stream은 그룹 채팅 미지원
    if room.room_type == "group":
        return {
            "state": "failure",
            "message": "그룹 채팅은 스트리밍을 지원하지 않습니다.",
        }

    # 요청에 캐릭터가 있으면 그 캐릭터로 변경
    if request.character:
        character = get_active_character(db, request.character)

        if character is None:
            return {
                "state": "failure",
                "message": "지원하지 않는 캐릭터입니다.",
                "data": {
                    "character": request.character,
                },
            }

        current_character = room.characters[0] if room.characters else None

        if character != current_character:
            room.characters = [character]
    else:
        character = room.characters[0] if room.characters else None

    # 스트림은 character 필수
    if not character:
        return {
            "state": "failure",
            "message": "스트리밍 채팅은 캐릭터가 필요합니다.",
        }

    previous_messages = get_room_messages(db, room.id)
    history = make_ai_history(previous_messages)

    create_message(
        db=db,
        room_id=room.id,
        role="user",
        content=message,
    )

    ai_stream = await open_character_chat_stream(
        message=message,
        history=history,
        character=character,
        user_context=build_chat_user_context(db, user_id),
    )
    await commit_before_streaming(db, ai_stream)

    return make_streaming_response(
        stream_and_save_character_answer(
            db=db,
            room_id=room.id,
            message=message,
            history=history,
            character=character,
            ai_stream=ai_stream,
        )
    )
