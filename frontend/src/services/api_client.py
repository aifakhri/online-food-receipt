from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from typing import Any

import httpx
import streamlit as st

from core.config import (
    BACKEND_URL,
    CONNECT_TIMEOUT_SECONDS,
    REQUEST_TIMEOUT_SECONDS,
)

History = list[dict[str, str]]


class BackendError(Exception):
    pass


def error_detail(response: httpx.Response) -> str:
    try:
        return str(response.json().get("detail", response.text))
    except ValueError:
        return response.text or response.reason_phrase


class BackendClient:
    def __init__(self, base_url: str) -> None:
        self._client = httpx.Client(
            base_url=base_url,
            timeout=httpx.Timeout(
                REQUEST_TIMEOUT_SECONDS, connect=CONNECT_TIMEOUT_SECONDS
            ),
        )

    def upload_receipt(
        self, file_name: str, data: bytes, mime_type: str
    ) -> dict[str, Any]:
        files = {"file": (file_name, data, mime_type)}
        return self._request("POST", "/receipts", files=files).json()

    def stream_receipt_answer(
        self, receipt_id: int, question: str, history: History
    ) -> Iterator[str]:
        payload = {"question": question, "history": history}
        path = f"/receipts/{receipt_id}/chat"
        try:
            with self._client.stream("POST", path, json=payload) as response:
                if response.is_error:
                    response.read()
                    raise BackendError(error_detail(response))
                yield from response.iter_text()
        except httpx.HTTPError as exc:
            raise BackendError(f"Backend unreachable: {exc}") from exc

    def get_date_range(self) -> tuple[date | None, date | None]:
        body = self._request("GET", "/receipts/date-range").json()
        earliest, latest = (
            date.fromisoformat(body[key]) if body[key] else None
            for key in ("earliest", "latest")
        )
        return earliest, latest

    def ask_assistant(
        self, question: str, history: History, as_of: date | None = None
    ) -> str:
        payload: dict[str, Any] = {"question": question, "history": history}
        if as_of:
            payload["as_of"] = as_of.isoformat()
        return self._request("POST", "/chat", json=payload).json()["answer"]

    def _request(
        self, method: str, path: str, **kwargs: Any
    ) -> httpx.Response:
        try:
            response = self._client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise BackendError(f"Backend unreachable: {exc}") from exc
        if response.is_error:
            raise BackendError(error_detail(response))
        return response


@st.cache_resource
def get_backend() -> BackendClient:
    return BackendClient(BACKEND_URL)