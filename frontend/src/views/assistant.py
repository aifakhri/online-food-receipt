from __future__ import annotations

from datetime import date

import streamlit as st

from components.chat_panel import chat_panel
from services.api_client import (
    BackendClient,
    BackendError,
    History,
    get_backend,
)
from utils.formatting import escape_md


@st.cache_data(ttl=60, show_spinner=False)
def load_date_range() -> tuple[date | None, date | None]:
    return get_backend().get_date_range()


def receipt_date_range() -> tuple[date | None, date | None]:
    try:
        return load_date_range()
    except BackendError:
        return None, None


def answer_from_receipts(
    backend: BackendClient,
    as_of: date | None,
    question: str,
    history: History,
) -> str:
    with st.spinner("Searching your receipts..."):
        answer = backend.ask_assistant(question, history, as_of)
    st.markdown(escape_md(answer))
    return answer


def render() -> None:
    backend = get_backend()
    messages = st.session_state.setdefault("assistant_messages", [])
    earliest, latest = receipt_date_range()
    today = date.today()

    with st.sidebar:
        as_of = st.date_input(
            "Answer as of",
            value=latest,
            min_value=earliest,
            max_value=max(latest, today) if latest else today,
            key="assistant_as_of",
            help='Treated as "today" when resolving "yesterday" or '
            '"last 7 days". Defaults to your most recent receipt date.',
        )
        if st.button("Clear conversation", disabled=not messages):
            messages.clear()
            st.rerun()

    st.header("Ask about all your receipts")
    if earliest and latest:
        st.caption(
            f"Receipts on file: {earliest:%d %b %Y} to {latest:%d %b %Y}"
        )
    st.caption(
        'e.g. "What food did I buy yesterday?", "Total spent on 20 June", '
        '"Where did I buy a burger in the last 7 days?"'
    )
    chat_panel(
        messages,
        "Ask about your purchases",
        lambda question, history: answer_from_receipts(
            backend, as_of, question, history
        ),
    )