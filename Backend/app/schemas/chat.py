

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class ChatHistoryItem(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=1000)
    character: Optional[str] = Field(default=None, max_length=100)
    recommended_movies: list[dict] = Field(default_factory=list, max_length=3)


class SendChatMessageRequest(BaseModel):
    # 사용자가 입력한 채팅 내용
    content: str = Field(..., min_length=1, max_length=500)
    character : Optional[str] = Field(default=None, max_length=100)
    # stream : bool = False


class AutoChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=500)
    character : Optional[str] = Field(default=None, max_length=100)
    history: list[ChatHistoryItem] = Field(default_factory=list, max_length=10)


class ChatTitleRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=500)


class ChatRoomTitleUpdate(BaseModel):
    title: str = Field(..., min_length=1, max_length=30)


class CharacterChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=500)
    character: str = Field(..., min_length=1, max_length=100)
    history: list[ChatHistoryItem] = Field(default_factory=list, max_length=10)
    # stream : bool = True


class CharacterGreetingRequest(BaseModel):
    character: str = Field(..., min_length=1, max_length=100)

class GroupChatRequest(BaseModel):
    # conversation_id: Optional[int] = None   # 기존 대화 이어가기 (없으면 새 대화)
    characters: list[str] = Field(..., min_length=2, max_length=5)
    message: str = Field(..., min_length=1, max_length=500)
    history: list[ChatHistoryItem] = Field(default_factory=list, max_length=10)


class GroupChatResponseItem(BaseModel):
    character: str
    answer: str


class GroupChatRound(BaseModel):
    round: int
    label: str
    responses: list[GroupChatResponseItem]


class GroupChatResponse(BaseModel):
    conversation_id: int
    intent: str
    movies: list[dict] = []
    rounds: list[GroupChatRound]
