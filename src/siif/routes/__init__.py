__all__ = ["siif_router"]

from fastapi import APIRouter

from .rf602 import rf602_router
from .rf610 import rf610_router

siif_router = APIRouter(prefix="/siif", tags=["SIIF"])


siif_router.include_router(rf602_router)
siif_router.include_router(rf610_router)
