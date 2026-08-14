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
def create_message(
    db: Session,
    room_id: int,
    role: str,
    content: str,
    character_name: str | None = None,
    recommended_movies: list[dict] | None = None,
    emotion: str | None = None,
) -> ChatMessage:
    message = ChatMessage(
        room_id = room_id,
        role = role,
        content = content,
        character_name = character_name,
        emotion = emotion,
        recommended_movies = recommended_movies,
    )
    db.add(message)

    return message

# 현재 LLM 슬롯당 실제 컨텍스트는 4,096 tokens이므로 DB의 전체 대화를
# 무제한 전송하지 않는다. 최근 대화를 우선하고 긴 메시지 하나가 예산을
# 독점하지 않도록 메시지별 길이도 제한한다.
def make_ai_history(
    messages,
    *,
    include_character_labels: bool = False,
    max_messages: int = 10,
    max_chars: int = 5000,
    max_chars_per_message: int = 1000,
) -> list[dict]:
    selected = []
    used_chars = 0
    for message in reversed(messages):
        if len(selected) >= max_messages:
            break
        content = str(message.content or "")[-max_chars_per_message:]
        if selected and used_chars + len(content) > max_chars:
            break
        selected.append((message, content))
        used_chars += len(content)

    history = []
    for message, content in reversed(selected):
        if include_character_labels and message.role == "assistant" and message.character_name:
            content = f"[{message.character_name}] {content}"
        item = {
            "role" : message.role,
            "content" : content
        }

        # 후속 추천에서 직전 추천작을 다시 노출하지 않도록 AI 서버에도
        # 구조화된 영화 목록을 함께 전달합니다.
        if message.recommended_movies:
            item["recommended_movies"] = message.recommended_movies

        if message.character_name:
            item["character"] = message.character_name
        
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
