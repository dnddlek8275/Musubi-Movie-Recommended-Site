from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.current_user import get_current_user, get_optional_current_user
from app.core.api_responses import error_response
from app.ai_client.chat import request_ai_chat, request_chat_title
from app.core.dependencies import get_db
from app.models.character import Character
from app.models.chat import ChatMessage, ChatRoom
from app.schemas.chat import AutoChatRequest, ChatRoomTitleUpdate, ChatTitleRequest, SendChatMessageRequest, CharacterChatRequest, CharacterGreetingRequest, GroupChatRequest
from app.services.character_service import characters_all_active, get_active_character
from app.services.chat_service import continue_chat, start_character_chat, start_general_chat, start_group_chat
from app.services.chat_stream_service import continue_chat_stream, start_character_chat_stream
from app.services.movies.chat_movie_link_service import enrich_recommended_movies
from app.services.guest_chat_service import (
    start_guest_character_chat,
    start_guest_general_chat,
    start_guest_group_chat,
)


# 채팅 관련 API들을 묶는 Router /chat
router = APIRouter(
    prefix="/chat",
    tags=["Chat"]
)


def _fallback_chat_title(message: str) -> str:
    title = " ".join(message.split()).strip()
    for ending in (
        "영화를 찾고 있어", "영화 찾고 있어", "영화를 추천해줘", "영화 추천해줘",
        "추천해 주세요", "추천해주세요", "추천해줘", "찾아 주세요", "찾아줘",
        "보고 싶어", "알려 주세요", "알려줘",
    ):
        if title.endswith(ending):
            title = title[:-len(ending)].rstrip(" ,.!?")
            break
    return (title[:24].rstrip() or "새 영화 대화")


# 채팅 API 경로를 만들어주는 함수
def chat_path(path: str):
    return f"/chat{path}"


# 기본 ai 채팅
@router.post("/auto")
async def chat(
    request : AutoChatRequest,
    http_request: Request,
    current_user: dict | None = Depends(get_optional_current_user),
    db:Session = Depends(get_db)
) :
    try :
        if current_user is None:
            return await start_guest_general_chat(db, http_request, request)
        # user_id = 1 #테스트 유저
        # 토큰 내 회원 ID 꺼내기
        user_id = current_user["user_id"]
        return await start_general_chat(db, user_id, request)
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail={
                "state": "error",
                "message": "AI 채팅 처리 중 오류가 발생했습니다.",
            },
        )

# 채팅할 수 있는 캐릭터 조회
@router.post("/title")
async def create_chat_title(request: ChatTitleRequest):
    try:
        result = await request_chat_title(request.message.strip())
        title = str(result.get("title") or "").splitlines()[0].strip().strip("`'\"")
        for prefix in ("제목:", "대화 제목:", "요약:"):
            if title.startswith(prefix):
                title = title[len(prefix):].strip()
        invalid_title = (
            len(title) > 30
            or any(
                phrase in title
                for phrase in ("추천합니다", "추천해요", "추천드려요", "영화는", "이라는 영화", "이 작품은")
            )
        )
        if invalid_title:
            title = _fallback_chat_title(request.message)
        return {
            "state": "success",
            "message": "대화 제목 생성에 성공했습니다.",
            "data": {"title": title[:30].rstrip() or "새 영화 대화"},
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=500,
            detail={"state": "error", "message": "대화 제목 생성 중 오류가 발생했습니다."},
        )


# 채팅할 수 있는 캐릭터 조회
@router.get("/characters")
async def get_chat_characters(
    db : Session = Depends(get_db)
):
    try:
        characters = characters_all_active(db)
        if not characters :
            return {
                "state" : "failure",
                "message" : "채팅할 수 있는 캐릭터가 없습니다."
            }
        return {
            "state" : "success",
            "message" : "채팅 캐릭터 조회 성공",
            "data" : characters
        }
    except Exception:
        return error_response("채팅 캐릭터 조회 실패")

# 캐릭터 정보 가져오기 API
@router.get("character/{character_name}")
async def get_chat_character_detail(
    character_name : str,
    db : Session = Depends(get_db),
):
    try:
        character_name = get_active_character(db, character_name)
        if character_name is None:
            return {
                "state" : "failure",
                "message" : "관련 캐릭터 정보가 없습니다."
            }
        
        character = db.scalar(
            select(Character)
            .where(
                Character.name == character_name,
                Character.is_active.is_(True)
            )
        )
        
        if character is None:
            return {
                "state" : "failure",
                "message" : "DB에 캐릭터 관련 정보가 없습니다."
            }
        return {
            "state" : "success",
            "message" : "캐릭터 정보 조회 성공",
            "data" : {
                "id" : character.id,
                "name" : character.name,
                "profile_image" : character.profile_image,
            }
        }
    except Exception:
        return error_response("캐릭터 정보 조회 에러")

# 캐릭터 채팅 API
@router.post("/greeting")
async def create_character_greeting(
    request: CharacterGreetingRequest,
    db: Session = Depends(get_db),
):
    """캐릭터별로 검수해 DB에 저장한 첫인사를 반환한다."""
    try:
        character = get_active_character(db, request.character)
        if character is None:
            return {
                "state": "failure",
                "message": "지원하지 않는 캐릭터입니다.",
            }

        answer = str(db.scalar(
            select(Character.greeting_message).where(Character.name == character)
        ) or "").strip()
        if not answer:
            return {
                "state": "failure",
                "message": "등록된 첫인사가 없습니다.",
            }

        return {
            "state": "success",
            "message": "캐릭터 첫인사 생성에 성공했습니다.",
            "data": {
                "answer": answer[:2000],
                "character": character,
                "emotion": "default",
            },
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=500,
            detail={
                "state": "error",
                "message": "캐릭터 첫인사 생성 중 오류가 발생했습니다.",
            },
        )


@router.post("")
async def chat_character(
    request: CharacterChatRequest,
    http_request: Request,
    current_user: dict | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    try:
        if current_user is None:
            return await start_guest_character_chat(db, http_request, request)
        # JWT 회원 정보에서 user_id를 가져온다.
        user_id = current_user["user_id"]

        return await start_character_chat_stream(db, user_id, request)
        
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail={
                "state": "error",
                "message": "AI 캐릭터 채팅 처리 중 오류가 발생했습니다.",
            },
        )

# 그룹 채팅 API
@router.post("/group")
async def chat_group(
    request: GroupChatRequest,
    http_request: Request,
    current_user: dict | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    try:
        if current_user is None:
            return await start_guest_group_chat(db, http_request, request)
        # JWT 회원 정보에서 user_id를 가져온다.
        user_id = current_user["user_id"]
        # user_id = 1
        return await start_group_chat(db, user_id, request)
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail={
                "state": "error",
                "message": "AI 그룹 채팅 처리 중 오류가 발생했습니다.",
            },
        )
    
# 사용자 채팅방 목록 조회 GET /chat/rooms?user_id=1
@router.get("/rooms")
async def get_chat_rooms(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
    ):
    try:
        # JWT 회원 정보에서 user_id를 가져온다.
        user_id = current_user["user_id"]
        # user_id = 1

        # 최신 수정순으로 가져오기
        rooms = db.query(ChatRoom).filter(ChatRoom.user_id == user_id).order_by(ChatRoom.updated_at.desc()).all()
        first_user_messages = {
            room.id: db.query(ChatMessage)
                .filter(ChatMessage.room_id == room.id, ChatMessage.role == "user")
                .order_by(ChatMessage.created_at.asc())
                .first()
            for room in rooms
            if room.room_type == "general" and not room.title
        }
        return {
            "state" : "success",
            "message" : "채팅방 목록 조회에 성공했습니다.",
            "data" : [
                {
                    "room_id" : room.id,
                    "room_type" : room.room_type,
                    "title" : room.title,
                    "title_seed" : (
                        first_user_messages[room.id].content
                        if room.id in first_user_messages and first_user_messages[room.id]
                        else None
                    ),
                    "characters" : room.characters or [],
                    "created_at" : room.created_at,
                    "updated_at" : room.updated_at,
                }
                for room in rooms
            ]
        }

    except Exception:
        return error_response("채팅방 목록 조회 에러")


@router.patch("/rooms/{room_id}/title")
async def update_chat_room_title(
    room_id: int,
    request: ChatRoomTitleUpdate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    room = db.query(ChatRoom).filter(
        ChatRoom.id == room_id,
        ChatRoom.user_id == current_user["user_id"],
        ChatRoom.room_type == "general",
    ).first()
    if not room:
        raise HTTPException(status_code=404, detail="일반 채팅방을 찾을 수 없습니다.")

    room.title = request.title.strip()[:30]
    db.commit()
    return {
        "state": "success",
        "message": "대화 제목을 저장했습니다.",
        "data": {"room_id": room.id, "title": room.title},
    }


# 채팅 메시지 목록 조회 GET /chat/rooms/{room_id}/messages
@router.get("/rooms/{room_id}/messages")
async def get_chat_messages(
    room_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
    ):
    try:
        # JWT 회원 정보에서 user_id를 가져온다.
        user_id = current_user["user_id"]
        # user_id = 1

        # 사용자의 방인지 확인
        room = db.query(ChatRoom).filter(ChatRoom.id == room_id, ChatRoom.user_id == user_id).first()

        if not room:
            return {
                "state" : "failure",
                "message" : "해당 채팅방이 존재하지 않습니다."
            }
        
        # 채팅방의 메시지 생성 시간 순서대로 조회
        messages = db.query(ChatMessage).filter(ChatMessage.room_id == room_id).order_by(ChatMessage.created_at.asc()).all()
        return {
            "state" : "success",
            "message" : "채팅 메시지 목록 조회에 성공했습니다.",
            "data" : [
                {
                    "room_id" : message.room_id,
                    "role" : message.role,
                    "character" : message.character_name,
                    "emotion" : message.emotion or "default",
                    "created_at" : message.created_at,
                    "content" : message.content,
                    "recommended_movies" : enrich_recommended_movies(db, message.recommended_movies),
                }
                for message in messages
            ]
        }

    except Exception:
        return error_response("채팅 메시지 목록 조회 에러")

# 기존 채팅방에서 이어서 대화하는 API
# 채팅 메시지 전송 POST /chat/rooms/{room_id}/messages
@router.post("/rooms/{room_id}/messages")
async def send_chat_message(
    room_id: int, 
    request: SendChatMessageRequest, 
    current_user : dict = Depends(get_current_user), 
    db : Session = Depends(get_db)
    ):
    try:
        # 회원 JWT 조회
        user_id = current_user["user_id"]
        # user_id = 1
        return await continue_chat_stream(db, user_id, room_id, request)
        

    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail={
                "state": "error",
                "message": "채팅 메시지 전송 중 오류가 발생했습니다.",
            },
        )


# 채팅방 삭제 DELETE /chat/rooms/{room_id}?user_id=1
@router.delete("/rooms/{room_id}")
async def delete_chat_room(
    room_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
    ):
    try:
        # JWT 회원 정보에서 user_id를 가져온다.
        user_id = current_user["user_id"]

        # 사용자의 방인지 확인
        room = db.query(ChatRoom).filter(ChatRoom.id == room_id, ChatRoom.user_id == user_id).first()

        # 해당 방이 없을 경우
        if not room:
            return {
                "state" : "failure",
                "message" : "해당 채팅방이 존재하지 않습니다."
            }
        
        # 채팅방 삭제
        db.delete(room)
        # 저장
        db.commit()

        return {
            "state" : "success",
            "message" : "채팅방 삭제에 성공했습니다."
        }
    except Exception:
        db.rollback()
        return error_response("채팅방 삭제 에러")
