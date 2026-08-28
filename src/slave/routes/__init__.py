__all__ = ["slave_router"]

from fastapi import APIRouter

from .factureros import factureros_router
from .honorarios import honorarios_router

slave_router = APIRouter(prefix="/slave", tags=["SLAVE"])


slave_router.include_router(honorarios_router)
slave_router.include_router(factureros_router)
