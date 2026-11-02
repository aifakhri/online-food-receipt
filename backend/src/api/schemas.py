from __future__ import annotations

from datetime import date
from typing import Any, Literal

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage
from pydantic import BaseModel, Field


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    question: str = Field(min_length=1)
    history: list[Message] = Field(default_factory=list)

    def to_messages(self) -> list[AnyMessage]:
        history = [
            HumanMessage(m.content) if m.role == "user"
            else AIMessage(m.content)
            for m in self.history
        ]
        return [*history, HumanMessage(self.question)]


class AssistantRequest(ChatRequest):
    as_of: date | None = Field(
        None, description="Overrides today's date when resolving dates"
    )


class ChatResponse(BaseModel):
    answer: str


class DateRangeResponse(BaseModel):
    earliest: date | None
    latest: date | None


class ReceiptResponse(BaseModel):
    id: int
    reused: bool
    receipt: dict[str, Any]