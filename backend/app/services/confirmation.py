from typing import Any
from fastapi import HTTPException


def verify_confirmation_gate(user_confirmed: Any) -> None:
    """
    Hard Confirmation Gate:
    Strictly enforces that `user_confirmed` is boolean True (`type(user_confirmed) is bool and user_confirmed is True`).
    Rejects False, None, "true" (str), 1 (int), etc. with HTTP 403 Forbidden.
    """
    if type(user_confirmed) is not bool or user_confirmed is not True:
        raise HTTPException(
            status_code=403,
            detail="Action requires explicit user confirmation",
        )
