from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class CreateBookRequest(BaseModel):
    source_book_id: int | None = None
    book_code: str | None = None
    category_id: int | None = None
    category_code: str | None = None
    subcategory_id: int | None = None
    subcategory_code: str | None = None
    clc_hint: str | None = None
    title: str
    author: str = ""
    publisher: str = ""
    publish_year: int | None = None
    isbn: str = ""
    language: str | None = "中文"
    edition: str | None = None
    pages: int | None = None
    price_yuan: float | None = None
    copy_count: int | None = None
    primary_zone_id: int | None = None
    primary_zone_code: str | None = None
    recommended_reader: str | None = None
    keywords: str = ""
    introduction: str = ""
    circulation_type: str = "普通"
    data_note: str | None = None
    clc_code: str | None = None
    call_number: str | None = None
    isbn_status: str | None = None
    bibliographic_status: str | None = None
    book_source_class: str | None = None
    cover_url: str | None = None
    cover_source: str | None = None
    cover_status: str | None = None
    status: str | None = None
    is_active: bool = True
    initial_copies: int = Field(default=0, ge=0, le=100)


class UpdateBookRequest(BaseModel):
    category_id: int | None = None
    category_code: str | None = None
    subcategory_id: int | None = None
    subcategory_code: str | None = None
    clc_hint: str | None = None
    title: str | None = None
    author: str | None = None
    publisher: str | None = None
    publish_year: int | None = None
    isbn: str | None = None
    language: str | None = None
    edition: str | None = None
    pages: int | None = None
    price_yuan: float | None = None
    copy_count: int | None = None
    primary_zone_id: int | None = None
    primary_zone_code: str | None = None
    recommended_reader: str | None = None
    introduction: str | None = None
    keywords: str | None = None
    circulation_type: str | None = None
    data_note: str | None = None
    clc_code: str | None = None
    call_number: str | None = None
    isbn_status: str | None = None
    bibliographic_status: str | None = None
    book_source_class: str | None = None
    cover_url: str | None = None
    cover_source: str | None = None
    cover_status: str | None = None
    status: str | None = None
    is_active: bool | None = None


class CreateCopiesRequest(BaseModel):
    count: int = Field(ge=1, le=100)
    copy_code: str | None = None
    barcode: str | None = None
    copy_no: int | None = None
    current_position_id: int | None = None
    home_position_id: int | None = None
    copy_status: str = "available"
    collection_type: str | None = "普通外借"
    can_borrow_outside_library: bool | None = None
    status_code: str | None = None
    status_name: str | None = None
    acquisition_date: date | None = None
    acquisition_source: str | None = None
    condition_level: str | None = None
    asset_price_yuan: float | None = None
    remark: str = ""


class UpdateCopyStatusRequest(BaseModel):
    new_status: str
    reason: str = "manual_update"


class UpdateCopyLocationRequest(BaseModel):
    current_position_id: int
    reason: str = "manual_location_update"
