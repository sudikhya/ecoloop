from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.errors import DomainError, domain_error_handler, http_error_handler
from app.core.middleware import RequestBoundaryMiddleware

app = FastAPI(
    title="EcoLoop Household API",
    description="Versioned, authenticated household commands. Managed assistant access is reported explicitly when unavailable.",
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Household-ID", "Idempotency-Key"],
    max_age=600,
)
app.add_middleware(
    RequestBoundaryMiddleware,
    max_request_bytes=settings.MAX_REQUEST_BYTES,
    max_photo_bytes=settings.MAX_PHOTO_BYTES,
    max_surplus_media_bytes=settings.MAX_SURPLUS_MEDIA_BYTES,
)


app.add_exception_handler(DomainError, domain_error_handler)
app.add_exception_handler(StarletteHTTPException, http_error_handler)


@app.exception_handler(RequestValidationError)
async def request_validation_handler(request: Request, _: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "The request does not match the required schema.",
                "retryable": False,
                "requestID": request.state.request_id,
            }
        },
    )


@app.exception_handler(Exception)
async def safe_unexpected_error_handler(request: Request, _: Exception) -> JSONResponse:
    # Avoid logging exception payloads that could contain user-provided household data.
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "The request could not be completed.",
                "retryable": True,
                "requestID": request.state.request_id,
            }
        },
        headers={"X-Request-ID": request.state.request_id, "Cache-Control": "no-store"},
    )


app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/", tags=["Root"])
async def root():
    return {"service": "ecoloop-household-api", "health": f"{settings.API_V1_STR}/health"}
