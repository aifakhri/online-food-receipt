from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from agents.assistant import build_assistant
from agents.receipt_graph import build_receipt_graph
from api import chat, receipts
from core import config
from database.connection import init_db


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    init_db(config.DB_PATH)
    llm_settings = (
        config.MODEL_NAME, config.OPENAI_API_KEY, config.OPENAI_BASE_URL
    )
    app.state.receipt_graph = build_receipt_graph(*llm_settings)
    app.state.assistant = build_assistant(*llm_settings)
    yield


app = FastAPI(title="Online Food Receipt API", lifespan=lifespan)
app.include_router(receipts.router)
app.include_router(chat.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
