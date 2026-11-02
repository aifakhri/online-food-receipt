from __future__ import annotations

from collections.abc import Callable
from typing import Literal

import streamlit as st

from services.api_client import BackendError, History
from utils.formatting import escape_md

Responder = Callable[[str, History], str]


def chat_panel(
    messages: History,
    placeholder: str,
    respond: Responder,
    height: int | Literal["content"] = "content",
) -> None:
    box = st.container(height=height)
    for message in messages:
        box.chat_message(message["role"]).markdown(
            escape_md(message["content"])
        )
    question = st.chat_input(placeholder)
    if not question:
        return
    box.chat_message("user").markdown(escape_md(question))
    with box.chat_message("assistant"):
        try:
            answer = respond(question, list(messages))
        except BackendError as exc:
            st.error(f"Request failed: {exc}")
            return
    messages.extend(
        [
            {"role": "user", "content": question},
            {"role": "assistant", "content": answer},
        ]
    )
