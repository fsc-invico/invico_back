__all__ = ["icaro_router"]

from fastapi import APIRouter

from .carga import carga_router
from .ctas_ctes import ctas_ctes_router
from .estructuras import estructuras_router
from .informe_contable import informe_contable_router
from .obras import obras_router
from .proveedores import proveedores_router
from .resumen_rend_obras import resumen_rend_obras_router
from .retenciones import retenciones_router

icaro_router = APIRouter(prefix="/icaro", tags=["ICARO"])


icaro_router.include_router(estructuras_router)
icaro_router.include_router(obras_router)
icaro_router.include_router(ctas_ctes_router)
icaro_router.include_router(proveedores_router)
icaro_router.include_router(carga_router)
icaro_router.include_router(retenciones_router)
icaro_router.include_router(resumen_rend_obras_router)
icaro_router.include_router(informe_contable_router)
