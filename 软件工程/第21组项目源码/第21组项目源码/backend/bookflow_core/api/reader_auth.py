from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from bookflow_core.api.deps import get_current_reader
from bookflow_core.core.database import get_db
from bookflow_core.models import ReaderAccount
from bookflow_core.schemas.reader_auth import ReaderLoginRequest, ReaderRegisterRequest, ResetPasswordRequest, VerificationCodeRequest
from bookflow_core.services.reader_auth_service import (
    authenticate_reader,
    current_reader_to_dict,
    logout_reader,
    register_reader,
    request_reader_verification_code,
    reset_reader_password,
)

router = APIRouter(prefix="/reader-auth", tags=["reader-auth"])


@router.post("/login")
def login(req: ReaderLoginRequest, db: Session = Depends(get_db)):
    return {"success": True, "data": authenticate_reader(db, account=req.account, password=req.password), "message": None}


@router.get("/me")
def me(current_reader: ReaderAccount = Depends(get_current_reader), db: Session = Depends(get_db)):
    return {"success": True, "data": current_reader_to_dict(current_reader, db), "message": None}


@router.post("/logout")
def logout(current_reader: ReaderAccount = Depends(get_current_reader), db: Session = Depends(get_db)):
    return {"success": True, "data": logout_reader(db, current_reader), "message": None}


@router.post("/register")
def register(req: ReaderRegisterRequest, db: Session = Depends(get_db)):
    return {"success": True, "data": register_reader(db, **req.model_dump()), "message": "注册成功"}


@router.post("/verification-code")
def verification_code(req: VerificationCodeRequest, request: Request, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else None
    return {"success": True, "data": request_reader_verification_code(db, account=req.account, purpose=req.purpose or "general", request_ip=ip), "message": "验证码已生成"}


@router.post("/reset-password")
def reset_password(req: ResetPasswordRequest, db: Session = Depends(get_db)):
    return {"success": True, "data": reset_reader_password(db, **req.model_dump()), "message": "密码已重置"}
