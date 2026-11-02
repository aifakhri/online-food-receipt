from __future__ import annotations

from typing import Any, Literal, get_args

from pydantic import BaseModel, Field, field_validator

Category = Literal["Food", "Food & Dining", "Bar", "Cafe", "Restaurant"]
CATEGORIES = {value.casefold(): value for value in get_args(Category)}


class ReceiptItem(BaseModel):
    name: str = Field(
        description="As printed; add-on lines such as '+FRD ONION' are "
        "separate items"
    )
    quantity: float | None
    unit_price: float | None
    total_price: float | None


class Receipt(BaseModel):
    merchant_name: str | None
    merchant_address: str | None
    receipt_date: str | None = Field(
        description="YYYY-MM-DD", pattern=r"^\d{4}-\d{2}-\d{2}$"
    )
    receipt_time: str | None = Field(
        description="HH:MM, 24-hour", pattern=r"^\d{2}:\d{2}$"
    )
    receipt_number: str | None
    items: list[ReceiptItem] = Field(description="In printed order")
    subtotal: float | None
    tax: float | None
    tip: float | None
    total: float | None
    payment_method: str | None
    category: Category | None = Field(
        description="Null when the receipt fits none of the categories"
    )

    @field_validator("category", mode="before")
    @classmethod
    def drop_unknown_category(cls, value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        return CATEGORIES.get(value.strip().casefold())