__all__ = ["control_router", "reporte_router"]

from fastapi import APIRouter

from .control_aporte_empresario import control_aporte_empresario_router
from .control_banco import control_banco_router
from .control_banco_cruzado import control_banco_cruzado_router
from .control_banco_siif import control_banco_siif_router
from .control_banco_sscc import control_banco_sscc_router
from .control_icaro import control_icaro_router
from .control_icaro_anual import control_icaro_anual_router
from .control_icaro_comprobantes import control_icaro_comprobantes_router
from .control_icaro_pa6 import control_icaro_pa6_router
from .control_obras import control_obras_router
from .control_recursos import control_recursos_router
from .reporte_formulacion import reporte_formulacion_router
from .reporte_planillometro import reporte_planillometro_router

control_router = APIRouter(prefix="/control", tags=["Controles"])


control_router.include_router(control_recursos_router)
control_router.include_router(control_aporte_empresario_router)
control_router.include_router(control_icaro_anual_router)
control_router.include_router(control_icaro_comprobantes_router)
control_router.include_router(control_icaro_pa6_router)
control_router.include_router(control_icaro_router)
control_router.include_router(control_obras_router)
control_router.include_router(control_banco_cruzado_router)
control_router.include_router(control_banco_siif_router)
control_router.include_router(control_banco_sscc_router)
control_router.include_router(control_banco_router)

reporte_router = APIRouter(prefix="/reporte", tags=["Reportes"])
reporte_router.include_router(reporte_planillometro_router)
reporte_router.include_router(reporte_formulacion_router)
