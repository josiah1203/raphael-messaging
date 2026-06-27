"""Raphael service: raphael-messaging."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from raphael_contracts.errors import ErrorResponse
from raphael_messaging.events import handle_bus_event
from raphael_messaging.routes import router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        from raphael_contracts.kafka import start_consumer

        start_consumer(handle_bus_event, group_id="raphael-messaging")
    except Exception:
        pass
    yield


app = FastAPI(
    title="raphael-messaging",
    description="DMs, group channels, workspace channels",
    version="0.1.0",
    openapi_url="/v1/messaging/openapi.json" if "/v1/messaging" else "/openapi.json",
    lifespan=lifespan,
)

app.include_router(router, prefix="/v1/messaging" if "/v1/messaging" else "")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "raphael-messaging"}


@app.exception_handler(Exception)
async def unhandled(_request, exc: Exception) -> JSONResponse:
    err = ErrorResponse(code="internal_error", message=str(exc))
    return JSONResponse(status_code=500, content=err.model_dump())
