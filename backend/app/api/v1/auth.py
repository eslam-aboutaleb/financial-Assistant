from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import (
    DUMMY_PASSWORD_HASH,
    clear_session_cookie,
    create_access_token,
    hash_password,
    set_session_cookie,
    verify_password,
)
from app.database import get_db
from app.models.user import User
from app.schemas.models import UserSignup, UserSignin, Token

router = APIRouter()

@router.post("/signup", response_model=Token, status_code=status.HTTP_201_CREATED)
async def signup(
    payload: UserSignup,
    response: Response,
    session: AsyncSession = Depends(get_db)
):
    existing = (
        await session.execute(select(User).where(User.username == payload.username))
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="An account with this username already exists")

    password_hash = await run_in_threadpool(hash_password, payload.password)
    user = User(
        username=payload.username.strip(),
        password_hash=password_hash,
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail="An account with this username already exists",
        ) from exc
    await session.refresh(user)

    access_token = create_access_token(user.id)
    set_session_cookie(response, access_token)
    return {"access_token": access_token, "token_type": "bearer", "user_id": str(user.id)}

@router.post("/signin", response_model=Token)
async def signin(
    payload: UserSignin,
    response: Response,
    session: AsyncSession = Depends(get_db)
):
    user = (
        await session.execute(select(User).where(User.username == payload.username))
    ).scalar_one_or_none()

    stored_hash = user.password_hash if user is not None else DUMMY_PASSWORD_HASH
    password_matches = await run_in_threadpool(verify_password, payload.password, stored_hash)

    if user is None or not password_matches:
        raise HTTPException(status_code=401, detail="Incorrect username or password")

    access_token = create_access_token(user.id)
    set_session_cookie(response, access_token)
    return {"access_token": access_token, "token_type": "bearer", "user_id": str(user.id)}

@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response):
    clear_session_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
