from app.services.ai_usage_service import classify_ai_request


def test_classify_ai_request_tracks_public_chat_entrypoints():
    assert classify_ai_request("POST", "/chat/auto") == "general_chat"
    assert classify_ai_request("POST", "/chat/character") == "character_chat"
    assert classify_ai_request("POST", "/chat/group") == "group_chat"
    assert classify_ai_request("POST", "/chat/rooms/123/messages") == "chat_continue"


def test_classify_ai_request_ignores_non_ai_or_read_requests():
    assert classify_ai_request("GET", "/chat/rooms") is None
    assert classify_ai_request("POST", "/chat/title") is None
    assert classify_ai_request("POST", "/auth/login") is None
