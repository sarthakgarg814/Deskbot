from fastapi import APIRouter

from . import camera, hardware, notes, settings, system

api_router = APIRouter(prefix="/api")
api_router.include_router(system.router)
api_router.include_router(notes.router)
api_router.include_router(settings.router)
api_router.include_router(hardware.router)
api_router.include_router(camera.router)

__all__ = ["api_router"]
