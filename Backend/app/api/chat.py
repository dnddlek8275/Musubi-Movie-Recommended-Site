from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.current_user import get_current_user
from app.ai_client.chat import request_ai_chat
from app.core.dependencies import get_db
from app.models.character import Character
from app.models.chat import ChatMessage, ChatRoom
from app.schemas.chat import AutoChatRequest, SendChatMessageRequest, CharacterChatRequest, GroupChatRequest
from app.services.character_service import characters_all_active, get_active_character
from app.services.chat_service import continue_chat, start_character_chat, start_general_chat, start_group_chat
from app.services.chat_stream_service import continue_chat_stream, start_character_chat_stream


# 채팅 관련 API들을 묶는 Router /chat
router = APIRouter(
    prefix="/chat",
    tags=["Chat"]
)


# 채팅 API 경로를 만들어주는 함수
def chat_path(path: str):
    return f"/chat{path}"


# 기본 ai 채팅
@router.post("/auto")
async def chat(
    request : AutoChatRequest, 
    current_user: dict = Depends(get_current_user), 
    db:Session = Depends(get_db)
) :
    try :
        # user_id = 1 #테스트 유저
        # 토큰 내 회원 ID 꺼내기
        user_id = current_user["user_id"]
        return await start_general_chat(db, user_id, request)
    except HTTPException as e:
        db.rollback()
        return e.detail
    except Exception as e:
        db.rollback()
        return {
            "state" : "error",
            "message" : "AI 채팅 처리 중 에러났습니다.",
            "error" : str(e)
        }

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
    except Exception as e:
        return {
            "state" : "error",
            "message" : "채팅 캐릭터 조회 실패",
            "error" : str(e)
        }

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
    except Exception as e:
        return {
            "state" : "error",
            "message" : "캐릭터 정보 조회 에러",
            "error" : str(e)
        }

# 캐릭터 채팅 API
@router.post("")
async def chat_character(
    request: CharacterChatRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        # JWT 회원 정보에서 user_id를 가져온다.
        user_id = current_user["user_id"]

        return await start_character_chat_stream(db, user_id, request)
        
    except HTTPException as e:
        db.rollback()
        return e.detail
    except Exception as e:
        db.rollback()
        return {
            "state": "error",
            "message": "AI 캐릭터 채팅 처리 중 에러났습니다.",
            "error": str(e)
        }

# # 1대1 대화 스트림 모드
# @router.post("/stream")
# async def chat_character_stream(
#     request: CharacterChatRequest,
#     current_user : dict = Depends(get_current_user),
#     db : Session = Depends(get_db),
# ):
#     try:
#         user_id = current_user["user_id"]

#     except Exception as e:
#         return {
#             "state" : "error",
#             "message" : "스트림 챗 API 에러",
#             "error" : str(e)
#         }

# 그룹 채팅 API
@router.post("/group")
async def chat_group(
    request: GroupChatRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        # JWT 회원 정보에서 user_id를 가져온다.
        user_id = current_user["user_id"]
        # user_id = 1
        return await start_group_chat(db, user_id, request)
    except HTTPException as e:
        db.rollback()
        return e.detail
    except Exception as e:
        db.rollback()
        return {
            "state": "error",
            "message": "AI 그룹 채팅 처리 중 에러났습니다.",
            "error": str(e),
        }
    
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
        return {
            "state" : "success",
            "message" : "채팅방 목록 조회에 성공했습니다.",
            "data" : [
                {
                    "room_id" : room.id,
                    "room_type" : room.room_type,
                    "characters" : room.characters or [],
                    "created_at" : room.created_at,
                    "updated_at" : room.updated_at,
                }
                for room in rooms
            ]
        }

    except Exception as e:
        return {
            "state": "error",
            "message": "채팅방 목록 조회 에러",
            "error": str(e)
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
                    "created_at" : message.created_at,
                    "content" : message.content,
                    "recommended_movies" : message.recommended_movies or [],
                }
                for message in messages
            ]
        }

    except Exception as e:
        return {
            "state": "error",
            "message": "채팅 메시지 목록 조회 에러",
            "error": str(e)
        }

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
        

    except Exception as e:
        db.rollback()
        return {
            "state": "error",
            "message": "채팅 메시지 전송 에러",
            "error": str(e)
        }


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
    except Exception as e:
        db.rollback()
        return {
            "state": "error",
            "message": "채팅방 삭제 에러",
            "error": str(e)
        }
