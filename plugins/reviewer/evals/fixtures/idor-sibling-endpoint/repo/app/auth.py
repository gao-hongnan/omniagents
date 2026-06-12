"""Bearer-token authentication dependency."""

from fastapi import Header, HTTPException


def get_current_user_id(authorization: str = Header(default="")) -> int:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401)
    return int(authorization.removeprefix("Bearer "))
