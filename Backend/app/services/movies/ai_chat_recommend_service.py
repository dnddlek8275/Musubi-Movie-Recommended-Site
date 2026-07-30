from sqlalchemy.orm import Session

from app.models.chat import ChatMessage, ChatRoom

# 사용자가 ai에게 추천받은 영화들
def get_chat_ai_recommended_movies_messages(
    db: Session,
    user_id : int,
    limit : int = 100,
):
    return (
        db.query(ChatMessage, ChatRoom)
        # ChatMessage 에는 user_id가 없으므로 Chatroom과 연동
        .join(ChatRoom, ChatMessage.room_id == ChatRoom.id)
        # 로그인한 사용자의 모든 채팅방 조회
        .filter(ChatRoom.user_id == user_id)
        # ai 답변 부분만
        .filter(ChatMessage.role == "assistant")
        # 영화 추천 한 부분만
        .filter(ChatMessage.recommended_movies.isnot(None))
        # 추천순
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
        .all()
    )

def get_chat_ai_recommended_movies_result(
        db: Session,
        user_id : int,
        limit : int = 100,
):
    movies_messages = get_chat_ai_recommended_movies_messages(db, user_id, limit)
    movies_result = []
    seen_movies_ids = set()
    for message, room in movies_messages:
        for movie in message.recommended_movies or []:
            tmdb_id = movie.get("tmdb_id")
            if tmdb_id is None:
                continue

            if tmdb_id in seen_movies_ids:
                continue

            seen_movies_ids.add(tmdb_id)
            movies_result.append(movie)
    
    return movies_result