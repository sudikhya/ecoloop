import logging

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class DomainError(Exception):
    def __init__(self, code: str, message: str, status_code: int, retryable: bool = False):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.retryable = retryable


logger = logging.getLogger(__name__)


async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    if exc.status_code >= 500:
        cause = exc.__cause__
        logger.error(
            "domain_error request_id=%s code=%s cause_type=%s cause_code=%s",
            getattr(request.state, "request_id", "unavailable"),
            exc.code,
            type(cause).__name__ if cause is not None else "none",
            getattr(cause, "code", "none") if cause is not None else "none",
        )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "retryable": exc.retryable,
                "requestID": getattr(request.state, "request_id", "unavailable"),
            }
        },
    )


async def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    known = {
        401: ("UNAUTHENTICATED", "A valid Firebase identity is required."),
        403: ("FORBIDDEN", "The requested household membership is not available."),
        404: ("NOT_FOUND", "The requested resource was not found."),
        413: ("PAYLOAD_TOO_LARGE", "The request exceeds the allowed size."),
        422: ("VALIDATION_ERROR", "The request does not match the required schema."),
        429: ("RATE_LIMITED", "The request limit was reached. Try again later."),
    }
    code, message = known.get(exc.status_code, ("REQUEST_FAILED", "The request could not be completed."))
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "retryable": exc.status_code in (429, 503),
                "requestID": getattr(request.state, "request_id", "unavailable"),
            }
        },
        headers=exc.headers,
    )

