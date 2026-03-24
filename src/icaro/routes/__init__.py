__all__ = ["icaro_router"]

from fastapi import APIRouter

from .carga import carga_router

icaro_router = APIRouter(prefix="/icaro", tags=["ICARO"])


icaro_router.include_router(carga_router)
