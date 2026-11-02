from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from langchain.agents import create_agent
from langchain.agents.middleware import ModelRequest, dynamic_prompt
from langchain_openai import ChatOpenAI
from langgraph.graph.state import CompiledStateGraph

from agents.prompts import ASSISTANT_PROMPT
from agents.tools import TOOLS


@dataclass(frozen=True)
class AssistantContext:
    today: date


@dynamic_prompt
def dated_system_prompt(request: ModelRequest) -> str:
    today = request.runtime.context.today
    return ASSISTANT_PROMPT.format(
        weekday=today.strftime("%A"),
        today=today.isoformat(),
        yesterday=(today - timedelta(days=1)).isoformat(),
        week_start=(today - timedelta(days=6)).isoformat(),
    )


def build_assistant(
    model: str, api_key: str, base_url: str | None = None
) -> CompiledStateGraph:
    return create_agent(
        ChatOpenAI(model=model, api_key=api_key, base_url=base_url),
        tools=TOOLS,
        middleware=[dated_system_prompt],
        context_schema=AssistantContext,
    )
