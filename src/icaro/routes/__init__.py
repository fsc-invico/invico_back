__all__ = ["icaro_router"]

from fastapi import APIRouter

from .carga import carga_router
from .obras import obras_router
from .retenciones import retenciones_router

icaro_router = APIRouter(prefix="/icaro", tags=["ICARO"])


icaro_router.include_router(carga_router)
icaro_router.include_router(obras_router)
icaro_router.include_router(retenciones_router)
