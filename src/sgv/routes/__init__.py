__all__ = ["sgv_router"]

from fastapi import APIRouter

from .obras_desactivadas import obras_desactivadas_router
from .obras_recuperadas import obras_recuperadas_router
from .saldos_barrios_evolucion import saldos_barrios_evolucion_router

sgv_router = APIRouter(prefix="/sgv", tags=["SGV"])


sgv_router.include_router(saldos_barrios_evolucion_router)
sgv_router.include_router(obras_recuperadas_router)
sgv_router.include_router(obras_desactivadas_router)
