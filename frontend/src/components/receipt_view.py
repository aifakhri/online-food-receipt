from __future__ import annotations

from typing import Any

import streamlit as st

from utils.formatting import amount_decimals, fmt, fmt_quantity


def render_preview(data: bytes) -> None:
    st.image(data)


def render_receipt(receipt: dict[str, Any]) -> None:
    decimals = amount_decimals(receipt)
    number = receipt["receipt_number"]
    st.subheader(receipt["merchant_name"] or "Receipt")
    meta = [
        receipt["category"],
        receipt["merchant_address"],
        " ".join(
            filter(None, [receipt["receipt_date"], receipt["receipt_time"]])
        ),
        number and f"#{number}",
    ]
    st.caption(" · ".join(filter(None, meta)))

    total_col, items_col, payment_col = st.columns(3)
    total_col.metric("Total", fmt(receipt["total"], decimals))
    items_col.metric("Items", len(receipt["items"]))
    payment_col.metric("Payment", receipt["payment_method"] or "-")

    st.dataframe(
        [
            {
                "Item": item["name"],
                "Qty": fmt_quantity(item["quantity"]),
                "Unit price": fmt(item["unit_price"], decimals),
                "Total": fmt(item["total_price"], decimals),
            }
            for item in receipt["items"]
        ],
        hide_index=True,
    )

    breakdown = {
        "Subtotal": receipt["subtotal"],
        "Tax": receipt["tax"],
        "Tip": receipt["tip"],
        "Total": receipt["total"],
    }
    st.dataframe(
        [
            {"Component": label, "Amount": fmt(amount, decimals)}
            for label, amount in breakdown.items()
            if amount is not None
        ],
        hide_index=True,
    )

    with st.expander("Raw extraction"):
        st.json(receipt)