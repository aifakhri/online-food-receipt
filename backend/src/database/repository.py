from __future__ import annotations

import json
import sqlite3
from typing import Any

RECEIPT_FIELDS = (
    "merchant_name",
    "merchant_address",
    "receipt_date",
    "receipt_time",
    "receipt_number",
    "subtotal",
    "tax",
    "tip",
    "total",
    "payment_method",
    "category",
)
ITEM_FIELDS = ("name", "quantity", "unit_price", "total_price")
NOW = "strftime('%Y-%m-%dT%H:%M:%fZ', 'now')"


def get_receipt(
    conn: sqlite3.Connection, receipt_id: int
) -> dict[str, Any] | None:
    row = conn.execute(
        f"select {', '.join(RECEIPT_FIELDS)} from receipts "
        "where id = ? and status = 'extracted'",
        (receipt_id,),
    ).fetchone()
    if row is None:
        return None
    items = conn.execute(
        f"select {', '.join(ITEM_FIELDS)} from receipt_items "
        "where receipt_id = ? order by position",
        (receipt_id,),
    ).fetchall()
    return {**dict(row), "items": [dict(item) for item in items]}


def get_date_range(
    conn: sqlite3.Connection,
) -> tuple[str | None, str | None]:
    row = conn.execute(
        "select min(date(receipt_date)), max(date(receipt_date)) "
        "from purchases where date(receipt_date) is not null"
    ).fetchone()
    return row[0], row[1]


def find_extraction(
    conn: sqlite3.Connection, file_sha256: str
) -> sqlite3.Row | None:
    return conn.execute(
        "select id, model from receipts "
        "where file_sha256 = ? and status = 'extracted' "
        "order by id desc limit 1",
        (file_sha256,),
    ).fetchone()


def create_receipt(
    conn: sqlite3.Connection,
    file_name: str,
    file_path: str,
    mime_type: str,
    file_size: int,
    file_sha256: str,
) -> int:
    cursor = conn.execute(
        "insert into receipts "
        "(file_name, file_path, mime_type, file_size, file_sha256) "
        "values (?, ?, ?, ?, ?)",
        (file_name, file_path, mime_type, file_size, file_sha256),
    )
    return cursor.lastrowid


def save_extraction(
    conn: sqlite3.Connection,
    receipt_id: int,
    receipt: dict[str, Any],
    model: str | None,
    reused_from: int | None = None,
) -> None:
    assignments = ", ".join(f"{field} = :{field}" for field in RECEIPT_FIELDS)
    conn.execute(
        f"update receipts set status = 'extracted', model = :model, "
        f"reused_from = :reused_from, raw_extraction = :raw, "
        f"extracted_at = {NOW}, {assignments} where id = :id",
        {
            **{field: receipt[field] for field in RECEIPT_FIELDS},
            "model": model,
            "reused_from": reused_from,
            "raw": json.dumps(receipt, ensure_ascii=False),
            "id": receipt_id,
        },
    )
    conn.executemany(
        f"insert into receipt_items (receipt_id, position, "
        f"{', '.join(ITEM_FIELDS)}) values (?, ?, ?, ?, ?, ?)",
        [
            (receipt_id, position, *(item[field] for field in ITEM_FIELDS))
            for position, item in enumerate(receipt["items"], start=1)
        ],
    )


def mark_failed(
    conn: sqlite3.Connection, receipt_id: int, error: str
) -> None:
    conn.execute(
        "update receipts set status = 'failed', error = ? where id = ?",
        (error, receipt_id),
    )