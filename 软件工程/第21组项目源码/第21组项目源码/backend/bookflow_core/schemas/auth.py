from __future__ import annotations

from pydantic import BaseModel


class LoginRequest(BaseModel):
    account: str
    password: str


class AdminPublic(BaseModel):
    id: int
    admin_code: str
    name: str
    email: str
    is_super_admin: bool
    status: str
    permissions: list[str]


class LoginResponseData(BaseModel):
    access_token: str
    token_type: str = "bearer"
    admin: AdminPublic
