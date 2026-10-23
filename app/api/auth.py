"""HTTP authentication dependencies."""

import secrets

from fastapi import Header, HTTPException, status
from fastapi import Request


def require_api_key(
    request: Request,
    x_api_key: str | None = Header(None, alias="X-API-Key"),
) -> None:
    """Validate the static API key used by the service."""
    if x_api_key is None or not secrets.compare_digest(
        x_api_key,
        request.app.state.settings.api_key,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
