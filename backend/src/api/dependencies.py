from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from langgraph.graph.state import CompiledStateGraph


def get_receipt_graph(request: Request) -> CompiledStateGraph:
    return request.app.state.receipt_graph


def get_assistant(request: Request) -> CompiledStateGraph:
    return request.app.state.assistant


ReceiptGraph = Annotated[CompiledStateGraph, Depends(get_receipt_graph)]
Assistant = Annotated[CompiledStateGraph, Depends(get_assistant)]
