from __future__ import annotations


class BookFlowError(Exception):
    code = "BOOKFLOW_ERROR"

    def __init__(self, message: str, *, details: dict | None = None, code: str | None = None):
        super().__init__(message)
        if code is not None:
            self.code = code
        self.message = message
        self.details = details or {}


class NotFoundError(BookFlowError):
    code = "NOT_FOUND"


class BusinessRuleError(BookFlowError):
    code = "BUSINESS_RULE_ERROR"


class PermissionDeniedError(BookFlowError):
    code = "PERMISSION_DENIED"


class ValidationError(BusinessRuleError):
    code = "VALIDATION_ERROR"
