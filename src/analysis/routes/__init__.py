__all__ = ["control_router", "reporte_router"]

from fastapi import APIRouter

from .control_icaro_anual import control_icaro_anual_router
from .control_recursos import control_recursos_router

control_router = APIRouter(prefix="/control", tags=["Controles"])


control_router.include_router(control_recursos_router)
control_router.include_router(control_icaro_anual_router)
