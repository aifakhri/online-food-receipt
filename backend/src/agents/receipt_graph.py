from __future__ import annotations

import json
from typing import Annotated, Any, Literal, TypedDict

from langchain_core.messages import AnyMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph

from agents.prompts import EXTRACTION_PROMPT, RECEIPT_CHAT_PROMPT
from models.receipt import Receipt


class ReceiptState(TypedDict, total=False):
    images: list[str]
    receipt: dict[str, Any]
    messages: Annotated[list[AnyMessage], add_messages]


def build_receipt_graph(
    model: str, api_key: str, base_url: str | None = None
) -> CompiledStateGraph:
    extractor = ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=base_url,
        use_responses_api=True,
        reasoning={"effort": "low"},
    ).with_structured_output(Receipt)
    llm = ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=base_url,
        use_responses_api=True,
        reasoning={"effort": "none"},
    )

    def route(state: ReceiptState) -> Literal["extract", "chat"]:
        return "extract" if state.get("images") else "chat"

    def extract(state: ReceiptState) -> ReceiptState:
        content = [{"type": "text", "text": EXTRACTION_PROMPT}]
        content += [
            {"type": "image_url", "image_url": {"url": url, "detail": "high"}}
            for url in state["images"]
        ]
        receipt = extractor.invoke([HumanMessage(content=content)])
        return {"receipt": receipt.model_dump()}

    def chat(state: ReceiptState) -> ReceiptState:
        receipt = json.dumps(state["receipt"], ensure_ascii=False, indent=2)
        system = SystemMessage(RECEIPT_CHAT_PROMPT.format(receipt=receipt))
        return {"messages": [llm.invoke([system, *state["messages"]])]}

    graph = StateGraph(ReceiptState)
    graph.add_node("extract", extract)
    graph.add_node("chat", chat)
    graph.add_conditional_edges(START, route)
    graph.add_edge("extract", END)
    graph.add_edge("chat", END)
    return graph.compile()