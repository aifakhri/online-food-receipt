from __future__ import annotations

from collections.abc import Iterator

import streamlit as st
from streamlit.runtime.uploaded_file_manager import UploadedFile

from components.chat_panel import chat_panel
from components.receipt_view import render_preview, render_receipt
from core.config import ACCEPTED_TYPES
from services.api_client import (
    BackendClient,
    BackendError,
    History,
    get_backend,
)
from utils.formatting import escape_md


def process_upload(backend: BackendClient, uploaded: UploadedFile) -> None:
    data = uploaded.getvalue()
    st.session_state.update(
        receipt_file_id=uploaded.file_id,
        receipt_preview=data,
        receipt_id=None,
        receipt=None,
        receipt_error=None,
        receipt_messages=[],
    )
    try:
        with st.spinner("Extracting receipt..."):
            body = backend.upload_receipt(uploaded.name, data, uploaded.type)
    except BackendError as exc:
        st.session_state.receipt_error = str(exc)
        return
    st.session_state.update(receipt_id=body["id"], receipt=body["receipt"])


def answer_about_receipt(
    backend: BackendClient, receipt_id: int, question: str, history: History
) -> str:
    parts: list[str] = []

    def chunks() -> Iterator[str]:
        for text in backend.stream_receipt_answer(
            receipt_id, question, history
        ):
            parts.append(text)
            yield escape_md(text)

    st.write_stream(chunks())
    return "".join(parts)


def render() -> None:
    backend = get_backend()
    with st.sidebar:
        uploaded = st.file_uploader(
            "Upload a receipt image", type=ACCEPTED_TYPES
        )
        if uploaded and uploaded.file_id != st.session_state.get(
            "receipt_file_id"
        ):
            process_upload(backend, uploaded)
        if preview := st.session_state.get("receipt_preview"):
            render_preview(preview)

    if "receipt_preview" not in st.session_state:
        st.info("Upload a receipt image to start.")
        return
    if error := st.session_state.receipt_error:
        st.error(f"Extraction failed: {error}")
        return

    receipt_id = st.session_state.receipt_id
    receipt_col, chat_col = st.columns(2, gap="large")
    with receipt_col:
        render_receipt(st.session_state.receipt)
    with chat_col:
        st.subheader("Ask about this receipt")
        chat_panel(
            st.session_state.receipt_messages,
            "e.g. How much did I pay for tax?",
            lambda question, history: answer_about_receipt(
                backend, receipt_id, question, history
            ),
            height=520,
        )