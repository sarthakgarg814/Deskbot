from fastapi import APIRouter

from . import hardware, notes, settings, system

api_router = APIRouter(prefix="/api")
api_router.include_router(system.router)
api_router.include_router(notes.router)
api_router.include_router(settings.router)
api_router.include_router(hardware.router)

__all__ = ["api_router"]
