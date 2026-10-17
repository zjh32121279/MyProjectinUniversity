from __future__ import annotations
from datetime import date
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from bookflow_core.core.database import get_db
from bookflow_core.api.deps import require_permission
from bookflow_core.models import BookCopy, OverdueCase
from bookflow_core.schemas import BorrowRequest, CompleteBorrowRequest, ReturnRequest, RenewRequest, ReservationRequest
from bookflow_core.services.circulation_service import borrow_copy, return_copy, renew_borrow, create_reservation
from bookflow_core.services.circulation_query_service import list_loans, list_pending_requests
from bookflow_core.services.circulation_request_service import (
    cancel_service_request,
    complete_return_request,
    get_service_request,
    redeem_borrow_request,
    service_request_to_dict,
)

router = APIRouter(prefix="/circulation", tags=["circulation"])
EMPTY_MESSAGE = "数据库暂无可用数据，请先导入或迁移业务数据。"


def _response(data: dict):
    return {"success": True, "data": data, "message": EMPTY_MESSAGE if data.get("empty_state") else None}

@router.post("/borrow")
def borrow(req: BorrowRequest, db: Session = Depends(get_db), current_admin=Depends(require_permission("circulation:write"))):
    record = borrow_copy(db, reader_code=req.reader_code, copy_code=req.copy_code, actor_id=current_admin.admin_code)
    return {"success": True, "data": {"loan_id": record.id, "due_at": str(record.due_at), "status": record.status}, "message": None}


@router.get("/pending-requests")
def pending_requests(
    reader_id: int | None = None,
    keyword: str | None = None,
    status: str | None = None,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    _current_admin=Depends(require_permission("circulation:write")),
):
    return _response(list_pending_requests(db, reader_id=reader_id, keyword=keyword, status=status, limit=limit, offset=offset))


@router.get("/requests/{request_code}")
def service_request_detail(request_code: str, db: Session = Depends(get_db), current_admin=Depends(require_permission("circulation:write"))):
    return {"success": True, "data": service_request_to_dict(get_service_request(db, request_code)), "message": None}


@router.post("/requests/{request_code}/borrow/complete")
def complete_borrow_request(request_code: str, body: CompleteBorrowRequest | None = None, db: Session = Depends(get_db), current_admin=Depends(require_permission("circulation:write"))):
    row = redeem_borrow_request(db, request_code, admin_code=current_admin.admin_code, voucher_code=body.voucher_code if body else None)
    return {"success": True, "data": service_request_to_dict(row), "message": None}


@router.post("/requests/{request_code}/return/complete")
def complete_reader_return_request(request_code: str, db: Session = Depends(get_db), current_admin=Depends(require_permission("circulation:write"))):
    row = complete_return_request(db, request_code, admin_code=current_admin.admin_code)
    return {"success": True, "data": service_request_to_dict(row), "message": None}


@router.post("/requests/{request_code}/cancel")
def cancel_request(request_code: str, db: Session = Depends(get_db), current_admin=Depends(require_permission("circulation:write"))):
    row = cancel_service_request(db, request_code, actor_type="admin", actor_id=current_admin.admin_code)
    return {"success": True, "data": service_request_to_dict(row), "message": None}


@router.post("/return")
def return_book(req: ReturnRequest, db: Session = Depends(get_db), current_admin=Depends(require_permission("circulation:write"))):
    record = return_copy(db, copy_code=req.copy_code, actor_id=current_admin.admin_code)
    copy = db.get(BookCopy, record.copy_id)
    overdue = db.query(OverdueCase).filter(OverdueCase.loan_id == record.id).order_by(OverdueCase.id.desc()).first()
    overdue_days = max(0, (record.returned_at - record.due_at).days) if record.returned_at else 0
    return {
        "success": True,
        "data": {
            "loan_id": record.id,
            "status": record.status,
            "returned_at": str(record.returned_at),
            "overdue_days": overdue_days,
            "penalty_score": overdue.penalty_score if overdue else 0,
            "copy_status": copy.copy_status if copy else None,
        },
        "message": None,
    }

@router.post("/renew")
def renew(req: RenewRequest, db: Session = Depends(get_db), current_admin=Depends(require_permission("circulation:write"))):
    row = renew_borrow(db, loan_id=req.loan_id, actor_id=current_admin.admin_code)
    return {"success": True, "data": {"renewal_id": row.id, "old_due_at": str(row.old_due_at), "new_due_at": str(row.new_due_at)}, "message": None}

@router.post("/reservations")
def reserve(req: ReservationRequest, db: Session = Depends(get_db), current_admin=Depends(require_permission("reservations:write"))):
    row = create_reservation(db, reader_code=req.reader_code, book_code=req.book_code, actor_id=current_admin.admin_code)
    return {"success": True, "data": {"reservation_id": row.id, "status": row.status, "fulfilled_copy_id": row.fulfilled_copy_id}, "message": None}

@router.get("/borrow-records")
def loans(
    status: str | None = None,
    reader_id: int | None = None,
    book_id: int | None = None,
    copy_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    keyword: str | None = None,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    return _response(list_loans(db, status=status, reader_id=reader_id, book_id=book_id, copy_id=copy_id, start_date=start_date, end_date=end_date, keyword=keyword, limit=limit, offset=offset))

