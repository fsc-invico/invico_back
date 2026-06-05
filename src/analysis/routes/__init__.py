__all__ = ["control_router", "reporte_router"]

from fastapi import APIRouter

from .control_icaro_anual import control_icaro_anual_router
from .control_icaro_comprobantes import control_icaro_comprobantes_router
from .control_icaro_pa6 import control_icaro_pa6_router
from .control_recursos import control_recursos_router

control_router = APIRouter(prefix="/control", tags=["Controles"])


control_router.include_router(control_recursos_router)
control_router.include_router(control_icaro_anual_router)
control_router.include_router(control_icaro_comprobantes_router)
control_router.include_router(control_icaro_pa6_router)
