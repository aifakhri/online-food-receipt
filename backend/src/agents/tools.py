from __future__ import annotations

import json
from datetime import date
from itertools import groupby
from typing import Any, Literal

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from core.config import DB_PATH
from database.connection import connect_readonly
from models.receipt import Category

MAX_RECEIPTS = 50
GROUP_COLUMNS = {
    "day": "p.receipt_date",
    "merchant": "p.merchant_name",
    "category": "p.category",
}


class ReceiptFilter(BaseModel):
    start_date: date | None = Field(
        None, description="Inclusive start date; omit for no lower bound"
    )
    end_date: date | None = Field(
        None, description="Inclusive end date; omit for no upper bound"
    )
    category: Category | None = Field(
        None, description="Only when the user explicitly names a category"
    )
    merchant: str | None = Field(
        None, description="Part of the merchant name, case-insensitive"
    )


class PurchaseQuery(ReceiptFilter):
    keywords: list[str] | None = Field(
        None,
        description="Item name fragments matched case-insensitively; an item "
        "matches if it contains any of them",
    )


class SpendingQuery(ReceiptFilter):
    group_by: Literal["day", "merchant", "category"] | None = Field(
        None, description="Break the totals down by this dimension"
    )


def like_pattern(value: str) -> str:
    escaped = (
        value.strip()
        .replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )
    return f"%{escaped}%"


def receipt_conditions(
    start_date: date | None,
    end_date: date | None,
    category: str | None,
    merchant: str | None,
) -> tuple[list[str], dict[str, Any]]:
    conditions: list[str] = []
    params: dict[str, Any] = {}
    if start_date:
        conditions.append("date(p.receipt_date) >= :start_date")
        params["start_date"] = start_date.isoformat()
    if end_date:
        conditions.append("date(p.receipt_date) <= :end_date")
        params["end_date"] = end_date.isoformat()
    if category:
        conditions.append("p.category = :category")
        params["category"] = category
    if merchant:
        conditions.append("p.merchant_name like :merchant escape '\\'")
        params["merchant"] = like_pattern(merchant)
    return conditions, params


def where_clause(conditions: list[str]) -> str:
    return f"where {' and '.join(conditions)}" if conditions else ""


@tool(
    args_schema=PurchaseQuery,
    description="Find purchased items with the merchant, address, date and "
    "time of each receipt. Use for what was bought, where, or when.",
)
def find_purchases(
    start_date: date | None = None,
    end_date: date | None = None,
    category: str | None = None,
    merchant: str | None = None,
    keywords: list[str] | None = None,
) -> str:
    conditions, params = receipt_conditions(
        start_date, end_date, category, merchant
    )
    terms = [term for term in keywords or [] if term.strip()]
    if terms:
        conditions.append(
            "("
            + " or ".join(
                f"i.name like :keyword{n} escape '\\'"
                for n in range(len(terms))
            )
            + ")"
        )
        params |= {f"keyword{n}": like_pattern(t) for n, t in enumerate(terms)}

    sql = f"""
        select p.id, p.merchant_name, p.merchant_address, p.receipt_date,
               p.receipt_time, p.category, p.total, p.payment_method,
               i.name, i.quantity, i.unit_price, i.total_price
        from purchases p
        left join receipt_items i on i.receipt_id = p.id
        {where_clause(conditions)}
        order by p.receipt_date desc, p.receipt_time desc, p.id desc,
                 i.position
    """
    with connect_readonly(DB_PATH) as conn:
        rows = conn.execute(sql, params).fetchall()

    receipts = []
    for _, group in groupby(rows, key=lambda row: row["id"]):
        lines = list(group)
        first = lines[0]
        receipts.append(
            {
                "merchant": first["merchant_name"],
                "address": first["merchant_address"],
                "date": first["receipt_date"],
                "time": first["receipt_time"],
                "category": first["category"],
                "receipt_total": first["total"],
                "payment_method": first["payment_method"],
                "items": [
                    {
                        "name": line["name"],
                        "quantity": line["quantity"],
                        "unit_price": line["unit_price"],
                        "total_price": line["total_price"],
                    }
                    for line in lines
                    if line["name"] is not None
                ],
            }
        )
    return json.dumps(
        {
            "matched_receipts": len(receipts),
            "truncated": len(receipts) > MAX_RECEIPTS,
            "receipts": receipts[:MAX_RECEIPTS],
        },
        ensure_ascii=False,
    )


@tool(
    args_schema=SpendingQuery,
    description="Total spending, tax, tip and receipt count, optionally "
    "broken down by day, merchant or category. Use for any sum of money.",
)
def summarize_spending(
    start_date: date | None = None,
    end_date: date | None = None,
    category: str | None = None,
    merchant: str | None = None,
    group_by: str | None = None,
) -> str:
    conditions, params = receipt_conditions(
        start_date, end_date, category, merchant
    )
    column = GROUP_COLUMNS.get(group_by or "")
    group_select = f"{column} as {group_by}, " if column else ""
    group_sql = f"group by {column} order by {column}" if column else ""
    sql = f"""
        select {group_select}count(*) as receipts,
               count(p.total) as receipts_with_total,
               round(sum(p.total), 2) as total,
               round(sum(p.tax), 2) as tax,
               round(sum(p.tip), 2) as tip
        from purchases p
        {where_clause(conditions)}
        {group_sql}
    """
    with connect_readonly(DB_PATH) as conn:
        rows = [dict(row) for row in conn.execute(sql, params).fetchall()]
    return json.dumps(
        {"groups": rows} if column else rows[0], ensure_ascii=False
    )


TOOLS = [find_purchases, summarize_spending]
