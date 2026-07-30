

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class SendChatMessageRequest(BaseModel):
    # 사용자가 입력한 채팅 내용
    content: str = Field(..., min_length=1)
    character : Optional[str] = None
    # stream : bool = False


class AutoChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    character : Optional[str] = None


class CharacterChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    character: str = Field(..., min_length=1)
    # stream : bool = True

class GroupChatRequest(BaseModel):
    # conversation_id: Optional[int] = None   # 기존 대화 이어가기 (없으면 새 대화)
    characters: list[str]                   # 2~5명
    message: str


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
