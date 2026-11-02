from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from typing import Any

from langgraph.graph.state import CompiledStateGraph

from core.config import DB_PATH, MODEL_NAME, UPLOAD_DIR
from database import repository
from database.connection import connect

SUFFIXES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
}


class ExtractionError(Exception):
    def __init__(self, receipt_id: int, message: str) -> None:
        super().__init__(message)
        self.receipt_id = receipt_id


@dataclass(frozen=True)
class IngestedReceipt:
    id: int
    reused: bool
    receipt: dict[str, Any]


def to_data_url(data: bytes, mime_type: str) -> str:
    return f"data:{mime_type};base64,{base64.b64encode(data).decode()}"


def store_file(data: bytes, file_sha256: str, mime_type: str) -> str:
    stored_name = f"{file_sha256}{SUFFIXES[mime_type]}"
    path = UPLOAD_DIR / stored_name
    if not path.exists():
        path.write_bytes(data)
    return stored_name


async def ingest(
    graph: CompiledStateGraph, data: bytes, file_name: str, mime_type: str
) -> IngestedReceipt:
    file_sha256 = hashlib.sha256(data).hexdigest()
    stored_name = store_file(data, file_sha256, mime_type)
    with connect(DB_PATH) as conn:
        previous = repository.find_extraction(conn, file_sha256)
        reusable = (
            repository.get_receipt(conn, previous["id"]) if previous else None
        )
        receipt_id = repository.create_receipt(
            conn,
            file_name=file_name,
            file_path=stored_name,
            mime_type=mime_type,
            file_size=len(data),
            file_sha256=file_sha256,
        )

    try:
        if reusable is not None:
            receipt = reusable
            model, reused_from = previous["model"], previous["id"]
        else:
            images = [to_data_url(data, mime_type)]
            receipt = (await graph.ainvoke({"images": images}))["receipt"]
            model, reused_from = MODEL_NAME, None
        with connect(DB_PATH) as conn:
            repository.save_extraction(
                conn, receipt_id, receipt, model, reused_from
            )
    except Exception as exc:
        with connect(DB_PATH) as conn:
            repository.mark_failed(conn, receipt_id, str(exc))
        raise ExtractionError(receipt_id, str(exc)) from exc
    return IngestedReceipt(receipt_id, reusable is not None, receipt)