from __future__ import annotations

from pydantic import BaseModel


class CreateReaderReservationRequest(BaseModel):
    book_id: int | None = None
    copy_id: int | None = None


class UpdateNotificationSettingsRequest(BaseModel):
    borrow_due_enabled: bool | None = None
    reservation_arrival_enabled: bool | None = None
    system_notice_enabled: bool | None = None
    email_enabled: bool | None = None


class ToggleNotificationSettingRequest(BaseModel):
    key: str
    enabled: bool


class UpdateReaderContactRequest(BaseModel):
    phone: str | None = None
    email: str | None = None


class ChangeReaderPasswordRequest(BaseModel):
    old_password: str
    new_password: str
    confirm_password: str


class SubmitReaderFeedbackRequest(BaseModel):
    category: str | None = None
    content: str


class UpdateReaderPreferencesRequest(BaseModel):
    favorite_category_codes: list[str] | None = None
    recommendation_source: str | None = None  # "popular" | "preference" | "both"
