from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
import uuid

from fastapi import HTTPException, Request, Response, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.user import User

SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "super-secret-key-for-development-only-change-me")
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 1 week
COOKIE_NAME = "omnicare_access_token"

# Dummy hash for timing attack protection
DUMMY_PASSWORD_HASH = "$argon2id$v=19$m=65536,t=3,p=4$dummySalt$dummyHashDigest"  # noqa: S105

ph = PasswordHasher()
_bearer = HTTPBearer(auto_error=False)

def hash_password(password: str) -> str:
    return ph.hash(password)

def verify_password(password: str, hashed: str) -> bool:
    try:
        ph.verify(hashed, password)
        return True
    except VerifyMismatchError:
        return False
    except Exception:
        return False

def _b64url_encode(value: dict) -> str:
    raw = json.dumps(value, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

def _b64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))

def create_access_token(user_id: uuid.UUID) -> str:
    header = _b64url_encode({"alg": "HS256", "typ": "JWT"})
    payload = _b64url_encode(
        {
            "sub": str(user_id),
            "exp": int(time.time()) + (ACCESS_TOKEN_EXPIRE_MINUTES * 60),
        }
    )
    unsigned = f"{header}.{payload}"
    signature = hmac.new(
        SECRET_KEY.encode(), unsigned.encode(), hashlib.sha256
    ).digest()
    encoded_signature = base64.urlsafe_b64encode(signature).rstrip(b"=").decode()
    return f"{unsigned}.{encoded_signature}"

class _InvalidTokenError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason

def _decode_token(token: str) -> uuid.UUID:
    if not isinstance(token, str) or token.count(".") != 2:
        raise _InvalidTokenError("malformed")
    try:
        header, payload, signature = token.split(".")
    except ValueError as exc:
        raise _InvalidTokenError("malformed") from exc

    unsigned = f"{header}.{payload}"
    expected = hmac.new(
        SECRET_KEY.encode(), unsigned.encode(), hashlib.sha256
    ).digest()
    try:
        provided = _b64url_decode(signature)
    except (ValueError, TypeError) as exc:
        raise _InvalidTokenError("bad-signature") from exc
    if not hmac.compare_digest(expected, provided):
        raise _InvalidTokenError("bad-signature")

    try:
        body = json.loads(_b64url_decode(payload))
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise _InvalidTokenError("malformed-payload") from exc

    if not isinstance(body, dict):
        raise _InvalidTokenError("malformed-payload")
    exp = body.get("exp")
    sub = body.get("sub")
    if not isinstance(exp, int) or not isinstance(sub, str):
        raise _InvalidTokenError("malformed-payload")
    if exp < int(time.time()):
        raise _InvalidTokenError("expired")
    try:
        return uuid.UUID(sub)
    except (ValueError, TypeError) as exc:
        raise _InvalidTokenError("malformed-subject") from exc

def _resolve_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None,
) -> str | None:
    cookie_token = request.cookies.get(COOKIE_NAME)
    if credentials is not None:
        return credentials.credentials
    return cookie_token

def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=True,
        samesite="lax",
        secure=False,  # Set True in production
        path="/",
    )

def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=COOKIE_NAME,
        path="/",
        httponly=True,
        samesite="lax",
        secure=False,
    )

async def get_current_user(
    request: Request,
    response: Response,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: AsyncSession = Depends(get_db),
) -> str:
    token = _resolve_token(request, credentials)
    if token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sign in to continue")
    try:
        user_uuid = _decode_token(token)
    except _InvalidTokenError:
        clear_session_cookie(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")  # noqa: B904, E501

    user = (await session.execute(select(User).where(User.id == user_uuid))).scalar_one_or_none()
    if user is None:
        clear_session_cookie(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account not found")

    return str(user.id)
