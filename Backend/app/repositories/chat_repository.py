from sqlalchemy.orm import Session

from app.models.chat import ChatMessage, ChatRoom

# 기본 AI 채팅방 생성
def create_room(db:Session, user_id: int, character: str | None = None) -> ChatRoom:
    # db에 저장할 room
    room = ChatRoom(
        user_id = user_id,
        # 캐릭터 지정이 있으면 character, 없으면 general
        room_type = "character" if character else "general",
        characters=[character] if character else []
    )
    # db저장
    db.add(room)

    # room.id 를 바로 사용해야하므로 flush() 사용
    # commit은 user message와 assistant 답변까지 저장
    db.flush()

    return room

# 그룹 AI 채팅방 생성
def create_group_room(db:Session, user_id:int, characters: list[str]) -> ChatRoom:
    room = ChatRoom(
        user_id = user_id,
        room_type = "group",
        characters = characters,
    )
    # db에 저장
    db.add(room)
    # room.id 를 바로 사용해야하므로 flush() 사용
    # commit은 user message와 assistant 답변까지 저장
    db.flush()

    return room


# 메시지 한줄 저장
def create_message(db:Session, room_id:int, role:str, content:str, character_name: str | None = None,recommended_movies: list[dict] | None = None) ->ChatMessage:
    message = ChatMessage(
        room_id = room_id,
        role = role,
        content = content,
        character_name = character_name,
        recommended_movies = recommended_movies,
    )
    db.add(message)

    return message

# history 형태로 변환 - 그룹 대화용 묶음으로 
def make_ai_history(messages) -> list[dict]:
    history = []

    for message in messages:
        item = {
            "role" : message.role,
            "content" : message.content
        }

        # 캐릭터가 있는 경우
        # if message.character_name:
        #     item["character"] = message.character_name
        
        history.append(item)
    return history

# 사용자의 특정 채팅방 조회
def get_room_user(db:Session, room_id:int, user_id: int, room_type: str | None = None) -> ChatRoom | None:
    return (
        db.query(ChatRoom).filter(
            ChatRoom.id == room_id,
            ChatRoom.user_id ==user_id,
            ChatRoom.room_type == room_type if room_type else True,
        ).first()
    )

# 특정 채팅방의 메시지 목록 시간순으로 조회
def get_room_messages(db: Session, room_id:int) -> list[ChatMessage]:
    return (
        db.query(ChatMessage).filter(ChatMessage.room_id == room_id).order_by(
            ChatMessage.created_at.asc()
        ).all()
    )