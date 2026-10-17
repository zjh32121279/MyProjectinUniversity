from __future__ import annotations
from pydantic import BaseModel


class BorrowRequest(BaseModel):
    reader_code: str
    copy_code: str


class CompleteBorrowRequest(BaseModel):
    voucher_code: str | None = None


class ReturnRequest(BaseModel):
    copy_code: str


class RenewRequest(BaseModel):
    loan_id: int


class ReservationRequest(BaseModel):
    reader_code: str
    book_code: str


class CreateReaderRequest(BaseModel):
    reader_code: str
    name: str
    reader_type_code: str
    phone_masked: str = ""
    email: str = ""

class UpdateReaderRequest(BaseModel):
    name: str | None = None
    reader_type_code: str | None = None
    phone_masked: str | None = None
    email: str | None = None
    status: str | None = None

# --- 新通知中心 Schema ---

class MessageDeliveryRecipient(BaseModel):
    recipient_type: str
    recipient_id: int | str | None = None


class CreateMessageWithDeliveriesRequest(BaseModel):
    title: str
    content: str
    notification_type: str = "general"
    source_type: str = "manual"
    source_task_code: str | None = None
    related_entity_type: str | None = None
    related_entity_id: str | None = None
    target_scope_json: str | None = None
    lifecycle_status: str = "queued"
    scheduled_at: str | None = None
    recipients: list[MessageDeliveryRecipient] = []
    idempotency_key: str | None = None

class TaskRequest(BaseModel):
    title: str
    description: str = ""
    priority: str = "normal"
    task_group: str | None = None
    source_type: str = "system"
    related_entity_type: str = ""
    related_entity_id: str = ""
    risk_warning_code: str = ""
    requires_human_confirmation: bool = False
    auto_start_ai: bool = False
    source_payload: dict | None = None
    execution_context: dict | None = None
    queue_name: str | None = None
    max_attempts: int | None = None

class ClaimTaskRequest(BaseModel):
    admin_code: str

class TakeoverTaskRequest(BaseModel):
    admin_code: str | None = None
    reason: str = "admin_takeover"

class ResolveTaskRequest(BaseModel):
    resolution: str = "resolved"

class CancelTaskRequest(BaseModel):
    reason: str = "cancelled"

class AITaskStartRequest(BaseModel):
    run_id: int | None = None

class AITaskCompleteRequest(BaseModel):
    run_id: int | None = None
    result: str = "resolved"

class AITaskFailRequest(BaseModel):
    run_id: int | None = None
    error: str = ""
    confidence: float | None = None

class AIChatRequest(BaseModel):
    conversation_id: str
    text: str

class SetAdminStatusRequest(BaseModel):
    status: str


class UpdateLibraryProfileRequest(BaseModel):
    library_name: str | None = None
    library_type: str | None = None
    service_population: str | None = None
    building_area_sqm: float | None = None
    open_floors: str | None = None


class UpdateLibrarySpaceConfigRequest(BaseModel):
    zone_count: int | None = None
    shelf_count: int | None = None
    reservation_shelf_count: int | None = None
    turnover_shelf_count: int | None = None


class BatchUpdateSettingsRequest(BaseModel):
    settings: dict[str, str] = {}


class CreateAdminRequest(BaseModel):
    admin_code: str
    name: str
    email: str = ""
    password: str
    is_super_admin: bool = False
    status: str = "active"


class UpdateAdminRequest(BaseModel):
    name: str | None = None
    email: str | None = None
    is_super_admin: bool | None = None
    status: str | None = None


class ResetAdminPasswordRequest(BaseModel):
    password: str
