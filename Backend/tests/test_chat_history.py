from types import SimpleNamespace

from app.repositories.chat_repository import make_ai_history


def test_make_ai_history_preserves_recommended_movies():
    movies = [{"id": 1, "title": "너의 결혼식"}]
    messages = [
        SimpleNamespace(role="user", content="로맨스 영화 추천해줘", recommended_movies=None),
        SimpleNamespace(role="assistant", content="이 영화를 추천해요.", recommended_movies=movies),
    ]

    history = make_ai_history(messages)

    assert "recommended_movies" not in history[0]
    assert history[1]["recommended_movies"] == movies
