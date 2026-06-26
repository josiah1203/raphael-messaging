"""API routes for raphael-messaging."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["raphael-messaging"])


@router.get("")
def list_root() -> dict[str, str]:
  return {"service": "raphael-messaging", "status": "stub"}
