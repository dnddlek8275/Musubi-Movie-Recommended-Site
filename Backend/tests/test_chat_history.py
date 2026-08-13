from types import SimpleNamespace

from app.repositories.chat_repository import make_ai_history


def test_make_ai_history_preserves_recommended_movies():
    movies = [{"id": 1, "title": "너의 결혼식"}]
    messages = [
        SimpleNamespace(role="user", content="로맨스 영화 추천해줘", character_name=None, recommended_movies=None),
        SimpleNamespace(role="assistant", content="이 영화를 추천해요.", character_name="무무", recommended_movies=movies),
    ]

    history = make_ai_history(messages)

    assert "recommended_movies" not in history[0]
    assert history[1]["recommended_movies"] == movies


def test_make_ai_history_labels_group_speakers():
    messages = [SimpleNamespace(
        role="assistant",
        content="내가 먼저 답하지.",
        character_name="간달프",
        recommended_movies=None,
    )]

    history = make_ai_history(messages, include_character_labels=True)

    assert history == [{
        "role": "assistant",
        "content": "[간달프] 내가 먼저 답하지.",
        "character": "간달프",
    }]


def test_make_ai_history_keeps_only_recent_messages_within_budget():
    messages = [SimpleNamespace(
        role="user",
        content=f"message-{index}",
        character_name=None,
        recommended_movies=None,
    ) for index in range(12)]

    history = make_ai_history(messages, max_messages=4, max_chars=100)

    assert [item["content"] for item in history] == [
        "message-8", "message-9", "message-10", "message-11",
    ]
