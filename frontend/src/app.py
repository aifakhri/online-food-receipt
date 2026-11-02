from __future__ import annotations

import streamlit as st

from views import assistant, receipt_chat

st.set_page_config(page_title="Receipt Chat", page_icon="🧾", layout="wide")

navigation = st.navigation(
    [
        st.Page(
            receipt_chat.render,
            title="Receipt",
            icon=":material/receipt_long:",
            url_path="receipt",
            default=True,
        ),
        st.Page(
            assistant.render,
            title="All receipts",
            icon=":material/forum:",
            url_path="assistant",
        ),
    ]
)
navigation.run()
