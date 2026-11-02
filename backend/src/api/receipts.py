from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from api.dependencies import ReceiptGraph
from api.schemas import ChatRequest, DateRangeResponse, ReceiptResponse
from core.config import DB_PATH
from database import repository
from database.connection import connect_readonly
from services.ingestion import SUFFIXES, ExtractionError, ingest

MAX_UPLOAD_BYTES = 20 * 1024 * 1024

router = APIRouter(prefix="/receipts", tags=["receipts"])


@router.post("", status_code=201)
async def upload_receipt(
    file: UploadFile, graph: ReceiptGraph
) -> ReceiptResponse:
    if file.content_type not in SUFFIXES:
        raise HTTPException(415, f"Unsupported file type: {file.content_type}")
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if not data:
        raise HTTPException(400, "The uploaded file is empty")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "The uploaded file is larger than 20 MB")
    try:
        result = await ingest(
            graph, data, file.filename or "receipt", file.content_type
        )
    except ExtractionError as exc:
        raise HTTPException(502, f"Extraction failed: {exc}") from exc
    return ReceiptResponse(
        id=result.id, reused=result.reused, receipt=result.receipt
    )


@router.get("/date-range")
async def receipt_date_range() -> DateRangeResponse:
    with connect_readonly(DB_PATH) as conn:
        earliest, latest = repository.get_date_range(conn)
    return DateRangeResponse(earliest=earliest, latest=latest)


@router.post("/{receipt_id}/chat")
async def chat_about_receipt(
    receipt_id: int, payload: ChatRequest, graph: ReceiptGraph
) -> StreamingResponse:
    with connect_readonly(DB_PATH) as conn:
        receipt = repository.get_receipt(conn, receipt_id)
    if receipt is None:
        raise HTTPException(404, "Receipt not found or not extracted")

    async def stream() -> AsyncIterator[str]:
        async for chunk, metadata in graph.astream(
            {"receipt": receipt, "messages": payload.to_messages()},
            stream_mode="messages",
        ):
            if metadata.get("langgraph_node") == "chat" and chunk.text:
                yield chunk.text

    return StreamingResponse(stream(), media_type="text/plain; charset=utf-8")