from __future__ import annotations

import re
from dataclasses import dataclass

import firebase_admin
from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth
from firebase_admin.exceptions import FirebaseError

from app.core.config import settings
from app.core.errors import DomainError
from app.core.firestore import get_firestore

bearer = HTTPBearer(auto_error=False)
HOUSEHOLD_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
NGO_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


@dataclass(frozen=True)
class Principal:
    uid: str
    household_id: str
    role: str


@dataclass(frozen=True)
class NgoPrincipal:
    uid: str
    ngo_id: str
    role: str = "NGO"


def _firebase_app() -> firebase_admin.App:
    try:
        return firebase_admin.get_app()
    except ValueError:
        options = (
            {"projectId": settings.FIREBASE_PROJECT_ID}
            if settings.FIREBASE_PROJECT_ID
            else None
        )
        try:
            return firebase_admin.initialize_app(options=options)
        except Exception as exc:
            raise DomainError(
                "IDENTITY_UNAVAILABLE",
                "Identity verification is unavailable.",
                503,
                retryable=True,
            ) from exc


async def authenticated_uid(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> str:
    if (
        credentials is None
        or credentials.scheme.lower() != "bearer"
        or len(credentials.credentials) > 8_192
    ):
        raise HTTPException(status_code=401)
    try:
        claims = auth.verify_id_token(
            credentials.credentials, app=_firebase_app(), check_revoked=True
        )
    except (
        auth.InvalidIdTokenError,
        auth.ExpiredIdTokenError,
        auth.RevokedIdTokenError,
        auth.UserDisabledError,
        ValueError,
    ):
        raise HTTPException(status_code=401) from None
    except FirebaseError as exc:
        raise DomainError(
            "IDENTITY_UNAVAILABLE", "Identity verification is unavailable.", 503, True
        ) from exc
    except Exception as exc:
        # Missing ADC, project configuration or verifier initialization is an
        # outage, never a local bypass.
        raise DomainError(
            "IDENTITY_UNAVAILABLE", "Identity verification is unavailable.", 503, True
        ) from exc
    uid = claims.get("uid")
    if not isinstance(uid, str) or not uid or len(uid) > 128:
        raise HTTPException(status_code=401)
    return uid


def _ngo_principal(uid: str) -> NgoPrincipal | None:
    try:
        snapshot = get_firestore().collection("ngo_accounts").document(uid).get()
    except DomainError:
        raise
    except Exception as exc:
        raise DomainError(
            "DATA_UNAVAILABLE", "Account access could not be verified.", 503, True
        ) from exc
    data = snapshot.to_dict() if snapshot.exists else None
    if not data or data.get("status") != "ACTIVE":
        return None
    ngo_id = data.get("ngo_id")
    if (
        data.get("uid") != uid
        or data.get("role") != "NGO"
        or data.get("demo_only") is not True
        or not isinstance(ngo_id, str)
        or NGO_ID_PATTERN.fullmatch(ngo_id) is None
    ):
        raise HTTPException(status_code=403)
    return NgoPrincipal(uid=uid, ngo_id=ngo_id)


async def household_uid(uid: str = Depends(authenticated_uid)) -> str:
    """Deny active NGO-only identities from every household account surface."""
    if _ngo_principal(uid) is not None:
        raise HTTPException(status_code=403)
    return uid


async def current_ngo(uid: str = Depends(authenticated_uid)) -> NgoPrincipal:
    principal = _ngo_principal(uid)
    if principal is None:
        raise HTTPException(status_code=403)
    return principal


async def current_principal(
    uid: str = Depends(household_uid),
    household_id: str | None = Header(default=None, alias="X-Household-ID"),
) -> Principal:
    if household_id is None or HOUSEHOLD_ID_PATTERN.fullmatch(household_id) is None:
        raise HTTPException(status_code=403)
    try:
        member_ref = (
            get_firestore()
            .collection("households")
            .document(household_id)
            .collection("members")
            .document(uid)
        )
        membership = member_ref.get()
    except DomainError:
        raise
    except Exception as exc:
        raise DomainError(
            "DATA_UNAVAILABLE", "Household access could not be verified.", 503, True
        ) from exc
    data = membership.to_dict() if membership.exists else None
    if not data or data.get("status") != "ACTIVE" or data.get("uid") != uid:
        raise HTTPException(status_code=403)
    role = data.get("role")
    if role not in {"OWNER", "MEMBER"}:
        raise HTTPException(status_code=403)
    return Principal(uid=uid, household_id=household_id, role=role)
