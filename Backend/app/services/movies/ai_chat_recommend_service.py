from sqlalchemy.orm import Session

from app.models.chat import ChatMessage, ChatRoom
from app.services.movies.chat_movie_link_service import enrich_recommended_movies

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
    # limit은 최종 영화 수 기준이다. 한 메시지에 최대 3편이 들어가므로
    # 충분한 최근 메시지를 읽고 중복·미연결 항목을 제거한 뒤 자른다.
    movies_messages = get_chat_ai_recommended_movies_messages(db, user_id, max(limit, 100))
    movies_result = []
    seen_movie_ids = set()
    for message, room in movies_messages:
        for movie in enrich_recommended_movies(db, message.recommended_movies):
            movie_id = movie.get("movie_id")
            # 상세 페이지는 PostgreSQL 내부 ID만 사용한다. 현재 DB에 연결할
            # 수 없는 과거 추천은 클릭 불가능한 카드로 노출하지 않는다.
            if movie_id is None:
                continue
            if movie_id in seen_movie_ids:
                continue
            seen_movie_ids.add(movie_id)
            movies_result.append(movie)
            if len(movies_result) >= limit:
                return movies_result
    
    return movies_result
