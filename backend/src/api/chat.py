from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter

from agents.assistant import AssistantContext
from api.dependencies import Assistant
from api.schemas import AssistantRequest, ChatResponse
from core.config import TIMEZONE

router = APIRouter(tags=["assistant"])


@router.post("/chat")
async def chat(
    payload: AssistantRequest, assistant: Assistant
) -> ChatResponse:
    today = payload.as_of or datetime.now(TIMEZONE).date()
    result = await assistant.ainvoke(
        {"messages": payload.to_messages()},
        context=AssistantContext(today=today),
    )
    return ChatResponse(answer=result["messages"][-1].text)
