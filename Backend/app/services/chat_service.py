import json

from sqlalchemy.orm import Session

from app.ai_client.chat import request_ai_chat, request_character_chat, request_group_chat
from app.repositories.chat_repository import create_group_room, create_message, create_room, get_room_messages, get_room_user, make_ai_history
from app.schemas.chat import AutoChatRequest, CharacterChatRequest, GroupChatRequest, SendChatMessageRequest
from app.services.character_service import get_active_character


# AI 대화 처리 함수
async def process_chat_message(db : Session, room, message:str, character : str | None = None):
    # 빈 문자열 character가 들어오면 None처럼 처리합니다.
    character = character.strip() if character else None

    # 방의 기존 대화 기록 조회
    previous_messages = get_room_messages(db, room.id)

    # general 방에서 전달된 캐릭터는 이번 요청에만 사용한다.
    if room.room_type == "general" and character:
        character = get_active_character(db, character)

        if not character:
            return {
                "state" : "failure",
                "message" : "지원하지 않는 캐릭터입니다.",
            }

    # AI 요청에 넣을 history
    history = make_ai_history(previous_messages)

    if character :
        ai_result = await request_character_chat(
            message=message,
            history=history,
            character= character
        )
    else :
        # AI 서버에 요청 - 캐릭터가 없으면 기본 채팅으로 요청
        ai_result = await request_ai_chat(
            message=message,
            history=history,
            character= character
        )

    # AI 서버에서 답변 반환
    answer = ai_result.get("answer")
    if not answer:
        return {
            "state" : "error",
            "message" : "AI 서버에서 답변이 없습니다.",
            "data" : ai_result
        }
    
    # AI가 자동 또는 요청에 따라 실제 사용한 캐릭터
    ai_auto_character = ai_result.get("character") or character

    # general 유형은 유지하고 마지막으로 응답한 캐릭터만 방에 기록한다.
    if room.room_type == "general" and ai_auto_character:
        room.characters = [ai_auto_character]
    
    # 추천한 영화 리스트
    movies = ai_result.get("movies", [])
    
    # 사용자 메시지 저장
    create_message(
        db = db,
        room_id = room.id,
        role = "user",
        content= message,
    )

    create_message(
        db=db,
        room_id=room.id,
        role="assistant",
        content=answer,
        character_name=ai_auto_character,
        recommended_movies=movies or None,
    )

    # 방, user_message, assistant_answer 한번에 저장 확정
    db.commit()
    return {
        "state" : "success",
        "message" : "채팅 응답에 성공했습니다.",
        "data" : {
            "room_id" : room.id,
            "answer" : answer,
            "character" : ai_auto_character,
            "intent" : ai_result.get("intent"),
            "movies" : ai_result.get("movies", [])
        }
    }

# 그룹 채팅 이어서 대화
async def process_group_chat_message(db: Session, room, message: str):
    # 방의 기존 대화 기록 조회
    privious_messages = get_room_messages(db, room.id)

    # DB 메세지 목록을 history 형태로 변환
    history = make_ai_history(privious_messages)

    # 그룹 채팅 API 요청
    ai_result = await request_group_chat(
        characters= room.characters,
        message=message,
        history=history,
    )
    # AI 응답, 의도, 추천 영화, 라운드
    intent = ai_result.get("intent")
    movies = ai_result.get("movies", [])
    rounds = ai_result.get("rounds", [])
    if not rounds:
        return {
            "state" : "error",
            "message" : "AI 서버에서 그룹 답변이 없습니다.",
            "data" : ai_result,
        }
    
    # 사용자 보낸 메시지
    create_message(
        db = db,
        room_id=room.id,
        role = "user",
        content=message,
    )

    movies_saved = False
    # AI 캐릭터별 답변 저장
    for round in rounds:
        responses = round.get("responses", [])
        for response in responses:
            recommend_movies = movies if movies and movies_saved else None
            create_message(
                db=db,
                room_id=room.id,
                role = "assistant",
                content= response.get("answer", ""),
                character_name=response.get("character"),
                recommended_movies= recommend_movies or None,
            )

    # 사용자 메시지 + 캐릭터별 답변 저장
    db.commit()

    return {
        "state" : "success",
        "message" : "그룹 채팅 응답에 성공했습니다.",
        "data" : {
            "room_id" : room.id,
            "intent" : intent,
            "rounds" : rounds,
            # "responses" : responses,
            "movies" : movies,
        },
    }

# 기본 AI 채팅방에서 대화 시작
async def start_general_chat(db: Session, user_id:int, request: AutoChatRequest):
    # 사용자가 보낸 메시지 공백 제거
    message = request.message.strip()

    # 내용 없으면 다시 입력하라고 전송
    if not message :
        return {
            "state" : "failure",
            "message" : "내용을 입력해주세요."
        }
    
    if request.character is not None:
        character = get_active_character(db, request.character)

        if character is None:
            return {
                "state" : "failure",
                "message" : "지원하지 않는 캐릭터입니다.",
                "data" : {
                    "character" : request.character
                }
            }
    
    # 기본 AI 채팅방 생성
    room = create_room (db, user_id)

    return await process_chat_message(db, room, message, request.character)

# 캐릭터 채팅방에서 대화 시작
async def start_character_chat(db: Session, user_id:int, request:CharacterChatRequest) :
    # 사용자가 보낸 메시지 공백 제거
    message = request.message.strip()

    # 내용 없으면 다시 입력하라고 전송
    if not message :
        return {
            "state" : "failure",
            "message" : "내용을 입력해주세요."
        }

    character = get_active_character(db, request.character)

    if character is None:
        return {
            "state" : "failure",
            "message" : "지원하지 않는 캐릭터입니다.",
            "data" : {
                "character" : request.character
            }
        }
    
    # 캐릭터 채팅방 생성
    room = create_room (db, user_id, character)

    return await process_chat_message(db, room, message, character)


async def start_group_chat(db: Session, user_id: int, request: GroupChatRequest):
    # 사용자가 보낸 메시지 공백 제거
    message = request.message.strip()

    if not 2 <= len(request.characters) <= 5:
        return {
            "state": "failure",
            "message": "그룹 채팅은 2~5명의 캐릭터가 필요합니다.",
        }
    characters = []
    for character in request.characters:
        character = get_active_character(db, character)

        if character is None:
            return {
                "state" : "failure",
                "message" : "그룹 채팅 - 채팅할 수 없는 캐릭터가 있습니다."
            }
        characters.append(character)

    if characters is None:
        return {
            "state" : "failure",
            "message" : "그룹 채팅 - 지원하지 않는 캐릭터가 포함되어 있습니다.",
        }

    # 내용 없으면 다시 입력하라고 전송
    if not message:
        return {
            "state": "failure",
            "message": "내용을 입력해주세요.",
        }
    
    room = create_group_room(db, user_id, characters)

    return await process_group_chat_message(db, room, message)

# 기본 채팅방에서 이어서 대화하는 함수
async def continue_chat(db:Session, user_id:int, room_id:int, request : SendChatMessageRequest):
    # 사용자가 보낸 메시지 공백 제거
    message = request.content.strip()

    # 내용 없으면 다시 입력하라고 전송
    if not message :
        return {
            "state" : "failure",
            "message" : "내용을 입력해주세요."
        }
    
    # 해당 방 조회
    room = get_room_user(db, room_id, user_id)
    # 해당 방이 없는 경우
    if not room:
        return {
            "state" : "failure",
            "message" : "채팅방을 찾을 수 없습니다."
        }
    
    if room.room_type == "group":
        return await process_group_chat_message(db, room, message)
    if request.character :
        character = request.character.strip()
    else :
        character = room.characters[0] if room.characters else None
    return await process_chat_message(db, room, message, character)


# async def _call_ai_group_auto(characters: list[str], message: str, history: list[dict]) -> dict:
#     """AI API POST /chat/group/auto 호출."""
#     async with httpx.AsyncClient(timeout=AI_API_TIMEOUT) as client:
#         resp = await client.post(
#             f"{AI_API_BASE}/chat/group/auto",
#             json={"characters": characters, "message": message, "history": history},
#         )
#     if resp.status_code == 400:
#         raise HTTPException(status_code=400, detail=resp.json().get("detail", "잘못된 요청입니다."))
#     resp.raise_for_status()
#     return resp.json()
