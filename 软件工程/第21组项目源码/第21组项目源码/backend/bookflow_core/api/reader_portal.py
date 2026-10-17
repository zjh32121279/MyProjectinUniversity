from __future__ import annotations

from uuid import uuid4
from typing import Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.orm import Session

from bookflow_core.api.deps import require_reader
from bookflow_core.core.config import project_root
from bookflow_core.core.database import get_db
from bookflow_core.core.exceptions import BookFlowError
from bookflow_core.core.time import now
from bookflow_core.models import ReaderAccount
from bookflow_core.schemas.reader_portal import ChangeReaderPasswordRequest, CreateReaderReservationRequest, SubmitReaderFeedbackRequest, UpdateReaderContactRequest, UpdateReaderPreferencesRequest
from bookflow_core.services.circulation_request_service import create_borrow_request, create_return_request
import bookflow_core.services.reader_portal_service as service

router = APIRouter(prefix="/reader", tags=["reader"])
AVATAR_UPLOAD_DIR = project_root() / "data" / "uploads" / "reader-avatars"
MAX_AVATAR_UPLOAD_BYTES = 5 * 1024 * 1024


class CreateBorrowRequest(BaseModel):
    book_id: Optional[int] = None
    copy_id: Optional[int] = None
    hold_hours: int = Field(default=24, ge=1, le=168)


def _response(data, message: str | None = None):
    return {"success": True, "data": data, "message": message}


def _validate_avatar_bytes(body: bytes) -> str:
    if not body:
        raise BookFlowError("头像图片为空。", code="VALIDATION_ERROR")
    if len(body) > MAX_AVATAR_UPLOAD_BYTES:
        raise BookFlowError("头像图片不能超过 5MB。", code="VALIDATION_ERROR", details={"max_bytes": MAX_AVATAR_UPLOAD_BYTES})
    if body.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if body.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if len(body) >= 12 and body[:4] == b"RIFF" and body[8:12] == b"WEBP":
        return ".webp"
    raise BookFlowError("头像图片仅支持 JPG、PNG 或 WebP。", code="VALIDATION_ERROR")


def _local_avatar_path(avatar_url: str | None):
    if not avatar_url or not avatar_url.startswith("/uploads/reader-avatars/"):
        return None
    filename = avatar_url.rsplit("/", 1)[-1]
    if not filename or "/" in filename or "\\" in filename:
        return None
    return AVATAR_UPLOAD_DIR / filename


@router.get("/home")
def home(db: Session = Depends(get_db), current_reader: ReaderAccount = Depends(require_reader)):
    return _response(service.reader_home(db, current_reader))


@router.get("/me")
def me(db: Session = Depends(get_db), current_reader: ReaderAccount = Depends(require_reader)):
    return _response(service.reader_profile(current_reader, db))


@router.get("/profile-center")
def profile_center(db: Session = Depends(get_db), current_reader: ReaderAccount = Depends(require_reader)):
    return _response(service.profile_center(db, current_reader))


@router.put("/profile/contact")
def update_contact(req: UpdateReaderContactRequest, db: Session = Depends(get_db), current_reader: ReaderAccount = Depends(require_reader)):
    return _response(service.update_reader_contact(db, current_reader, phone=req.phone, email=req.email))


@router.post("/profile/avatar")
async def upload_avatar(file: UploadFile = File(...), db: Session = Depends(get_db), current_reader: ReaderAccount = Depends(require_reader)):
    body = await file.read(MAX_AVATAR_UPLOAD_BYTES + 1)
    suffix = _validate_avatar_bytes(body)
    AVATAR_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    old_path = _local_avatar_path(current_reader.avatar_url)
    filename = f"reader-{current_reader.id}-{uuid4().hex}{suffix}"
    target = AVATAR_UPLOAD_DIR / filename
    target.write_bytes(body)
    current_reader.avatar_url = f"/uploads/reader-avatars/{filename}"
    current_reader.updated_at = now()
    db.add(current_reader)
    db.commit()
    db.refresh(current_reader)
    if old_path and old_path.exists() and old_path != target:
        old_path.unlink(missing_ok=True)
    return _response(service.reader_profile(current_reader, db))


@router.put("/profile/password")
def change_password(req: ChangeReaderPasswordRequest, db: Session = Depends(get_db), current_reader: ReaderAccount = Depends(require_reader)):
    return _response(service.change_reader_password(db, current_reader, old_password=req.old_password, new_password=req.new_password, confirm_password=req.confirm_password))


@router.post("/profile/feedback")
def submit_feedback(req: SubmitReaderFeedbackRequest, db: Session = Depends(get_db), current_reader: ReaderAccount = Depends(require_reader)):
    return _response(service.submit_reader_feedback(db, current_reader, category=req.category, content=req.content))


@router.get("/stats")
def stats(db: Session = Depends(get_db), current_reader: ReaderAccount = Depends(require_reader)):
    return _response(service.reader_stats(db, current_reader))


@router.get("/borrows")
def borrows(status: str | None = None, limit: int = Query(20, le=100), offset: int = 0, db: Session = Depends(get_db), current_reader: ReaderAccount = Depends(require_reader)):
    data = service.borrows(db, current_reader, status=status, limit=limit, offset=offset)
    return _response(data, "暂无数据" if data.get("empty_state") else None)


@router.get("/borrows/summary")
def borrows_summary(db: Session = Depends(get_db), current_reader: ReaderAccount = Depends(require_reader)):
    return _response(service.borrow_summary(db, current_reader))


@router.get("/borrows/due-reminders")
def borrows_due_reminders(db: Session = Depends(get_db), current_reader: ReaderAccount = Depends(require_reader)):
    return _response(service.due_reminders(db, current_reader))


@router.post("/borrows/{loan_id}/renew")
def renew_borrow(loan_id: int, db: Session = Depends(get_db), current_reader: ReaderAccount = Depends(require_reader)):
    return _response(service.renew_reader_borrow(db, current_reader, loan_id))


@router.post("/borrows/{loan_id}/return")
def return_borrow(loan_id: int, db: Session = Depends(get_db), current_reader: ReaderAccount = Depends(require_reader)):
    result = create_return_request(
        db,
        current_reader,
        loan_id=loan_id,
        source_type="reader_portal",
        source_actor_type="reader",
        source_actor_id=current_reader.reader_code,
    )
    return _response({
        "request_code": result.request_code,
        "voucher_code": result.voucher_code,
        "status": result.status,
        "expires_at": str(result.expires_at) if result.expires_at else None,
    })


@router.get("/borrow-rules")
def borrow_rules(db: Session = Depends(get_db), current_reader: ReaderAccount = Depends(require_reader)):
    return _response(service.borrow_rules(db, current_reader))


@router.post("/borrows/request")
def request_borrow(req: CreateBorrowRequest, db: Session = Depends(get_db), current_reader: ReaderAccount = Depends(require_reader)):
    result = create_borrow_request(
        db,
        current_reader,
        book_id=req.book_id,
        copy_id=req.copy_id,
        source_type="reader_portal",
        source_actor_type="reader",
        source_actor_id=current_reader.reader_code,
        hold_hours=req.hold_hours,
    )
    return _response({
        "request_code": result.request_code,
        "voucher_code": result.voucher_code,
        "status": result.status,
    })


@router.get("/reservations")
def reservations(status: str | None = None, limit: int = Query(20, le=100), offset: int = 0, db: Session = Depends(get_db), current_reader: ReaderAccount = Depends(require_reader)):
    data = service.reservations(db, current_reader, status=status, limit=limit, offset=offset)
    return _response(data, "暂无数据" if data.get("empty_state") else None)


@router.get("/reservations/summary")
def reservations_summary(db: Session = Depends(get_db), current_reader: ReaderAccount = Depends(require_reader)):
    return _response(service.reservation_summary(db, current_reader))


@router.get("/reservations/pickup-reminders")
def reservation_pickup_reminders(db: Session = Depends(get_db), current_reader: ReaderAccount = Depends(require_reader)):
    return _response(service.pickup_reminders(db, current_reader))


@router.post("/reservations")
def create_reservation(req: CreateReaderReservationRequest, db: Session = Depends(get_db), current_reader: ReaderAccount = Depends(require_reader)):
    return _response(service.create_reader_reservation(db, current_reader, book_id=req.book_id, copy_id=req.copy_id))


@router.post("/reservations/{reservation_id}/cancel")
def cancel_reservation(reservation_id: int, db: Session = Depends(get_db), current_reader: ReaderAccount = Depends(require_reader)):
    return _response(service.cancel_reader_reservation(db, current_reader, reservation_id))


@router.get("/reservations/{reservation_id}/pickup-code")
def pickup_code(reservation_id: int, db: Session = Depends(get_db), current_reader: ReaderAccount = Depends(require_reader)):
    return _response(service.pickup_code(db, current_reader, reservation_id))


@router.get("/reservation-rules")
def reservation_rules(db: Session = Depends(get_db), current_reader: ReaderAccount = Depends(require_reader)):
    return _response(service.reservation_rules(db, current_reader))


@router.get("/notifications")
def notifications(status: str | None = None, type: str | None = None, limit: int = Query(20, le=100), offset: int = 0, db: Session = Depends(get_db), current_reader: ReaderAccount = Depends(require_reader)):
    data = service.notifications(db, current_reader, status=status, notification_type=type, limit=limit, offset=offset)
    return _response(data, "暂无数据" if data.get("empty_state") else None)


@router.get("/notifications/summary")
def notifications_summary(db: Session = Depends(get_db), current_reader: ReaderAccount = Depends(require_reader)):
    return _response(service.notification_summary(db, current_reader))


@router.get("/notifications/overview")
def notifications_overview(db: Session = Depends(get_db), current_reader: ReaderAccount = Depends(require_reader)):
    return _response(service.notification_overview(db, current_reader))


@router.post("/notifications/{notification_id}/read")
def mark_notification_read(notification_id: int, db: Session = Depends(get_db), current_reader: ReaderAccount = Depends(require_reader)):
    return _response(service.mark_notification_read(db, current_reader, notification_id))


@router.post("/notifications/read-all")
def mark_all_notifications_read(db: Session = Depends(get_db), current_reader: ReaderAccount = Depends(require_reader)):
    return _response(service.mark_all_notifications_read(db, current_reader))


@router.delete("/notifications/read")
def clear_read_notifications(db: Session = Depends(get_db), current_reader: ReaderAccount = Depends(require_reader)):
    return _response(service.clear_read_notifications(db, current_reader))


@router.get("/notification-settings")
def notification_settings(db: Session = Depends(get_db), current_reader: ReaderAccount = Depends(require_reader)):
    return _response(service.notification_settings(db, current_reader))


@router.put("/notification-settings")
def update_notification_settings(body: dict[str, object], db: Session = Depends(get_db), current_reader: ReaderAccount = Depends(require_reader)):
    if "key" in body and "enabled" in body:
        updates = {str(body["key"]): bool(body["enabled"])}
    else:
        updates = {key: bool(value) for key, value in body.items() if value is not None}
    return _response(service.update_notification_settings(db, current_reader, updates))


@router.get("/preferences")
def get_preferences(db: Session = Depends(get_db), current_reader: ReaderAccount = Depends(require_reader)):
    return _response(service.get_reader_preferences(db, current_reader))


@router.put("/preferences")
def update_preferences(req: UpdateReaderPreferencesRequest, db: Session = Depends(get_db), current_reader: ReaderAccount = Depends(require_reader)):
    return _response(service.update_reader_preferences(
        db, current_reader,
        favorite_category_codes=req.favorite_category_codes,
        recommendation_source=req.recommendation_source,
    ))


@router.get("/borrows/history")
def borrows_history(limit: int = Query(50, le=200), offset: int = 0, db: Session = Depends(get_db), current_reader: ReaderAccount = Depends(require_reader)):
    return _response(service.borrow_history(db, current_reader, limit=limit, offset=offset))
