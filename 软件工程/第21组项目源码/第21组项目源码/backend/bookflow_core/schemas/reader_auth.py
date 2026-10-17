from __future__ import annotations

from pydantic import BaseModel


class ReaderLoginRequest(BaseModel):
    account: str
    password: str


class ReaderRegisterRequest(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    code: str | None = None
    password: str | None = None
    confirmPassword: str | None = None
    accepted: bool | None = None


class VerificationCodeRequest(BaseModel):
    account: str
    purpose: str | None = None


class ResetPasswordRequest(BaseModel):
    account: str
    code: str | None = None
    password: str | None = None
    confirmPassword: str | None = None
