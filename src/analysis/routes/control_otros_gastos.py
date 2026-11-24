from typing import Annotated, List

from fastapi import APIRouter, Depends

from ...auth.services import AuthorizationDependency
from ...utils.router_factory import GenericRouterFactory
from ..schemas import (
    ControlOtrosGastosExportFilter,
    ControlOtrosGastosGenerateFilter,
    ControlOtrosGastosSgfDocument,
    ControlOtrosGastosSgfFilter,
    ControlOtrosGastosSgfLiteFilter,
    ControlOtrosGastosSgfReport,
    ControlOtrosGastosSiifDocument,
    ControlOtrosGastosSiifFilter,
    ControlOtrosGastosSiifLiteFilter,
    ControlOtrosGastosSiifReport,
)
from ..services import (
    ControlOtrosGastosExportServiceDependency,
    ControlOtrosGastosSgfService,
    ControlOtrosGastosSgfServiceDependency,
    ControlOtrosGastosSiifService,
    ControlOtrosGastosSiifServiceDependency,
)


# -------------------------------------------------
def _sin_ruta_export(router: APIRouter) -> APIRouter:
    """Elimina el /export automático del GenericRouterFactory.

    El export de Otros Gastos es UNIFICADO: una sola ruta
    (``/control/otrosGastos/export``) sube un único Google Sheet con
    las 2 hojas (SIIF y SGF), por lo que los /export por lado no deben
    existir.
    """
    router.routes = [
        ruta
        for ruta in router.routes
        if ruta.name != "Export to Google Sheets and Excel"
    ]
    return router


# 2 conjuntos de rutas (SIIF y SGF), cada uno con su snapshot CRUD en
# su propia colección (control_otros_gastos_siif /
# control_otros_gastos_sgf) + su /generate on-demand. El export por
# lado se quita: es unificado.
factory_siif = GenericRouterFactory(
    service_dependency=ControlOtrosGastosSiifService,
    report_schema=ControlOtrosGastosSiifDocument,
    full_filter_schema=ControlOtrosGastosSiifFilter,
    lite_filter_schema=ControlOtrosGastosSiifLiteFilter,
    prefix="/otrosGastos/siif",
)
control_otros_gastos_siif_router = _sin_ruta_export(factory_siif.get_router())


# -------------------------------------------------
@control_otros_gastos_siif_router.get(
    "/generate",
    description=(
        "Tabla SIIF depurada (otros gastos) calculada on-demand por el "
        "backend: solo es_aprobado, sin MAP, sin obras/haberes/"
        "honorarios/viáticos/débitos bancarios (sin persistir; el "
        "snapshot lo congela el POST)"
    ),
    response_model=List[ControlOtrosGastosSiifReport],
    response_model_exclude_none=True,
)
async def generate_siif(
    params: Annotated[ControlOtrosGastosGenerateFilter, Depends()],
    service: ControlOtrosGastosSiifServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.generate(params=params)


factory_sgf = GenericRouterFactory(
    service_dependency=ControlOtrosGastosSgfService,
    report_schema=ControlOtrosGastosSgfDocument,
    full_filter_schema=ControlOtrosGastosSgfFilter,
    lite_filter_schema=ControlOtrosGastosSgfLiteFilter,
    prefix="/otrosGastos/sgf",
)
control_otros_gastos_sgf_router = _sin_ruta_export(factory_sgf.get_router())


# -------------------------------------------------
@control_otros_gastos_sgf_router.get(
    "/generate",
    description=(
        "Tabla SGF depurada (otros gastos) calculada on-demand por el "
        "backend: resumen_rend_prov deduplicado y sin obras/honorarios/"
        "escribanos (sin persistir; el snapshot lo congela el POST)"
    ),
    response_model=List[ControlOtrosGastosSgfReport],
    response_model_exclude_none=True,
)
async def generate_sgf(
    params: Annotated[ControlOtrosGastosGenerateFilter, Depends()],
    service: ControlOtrosGastosSgfServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.generate(params=params)


# Ruta compartida: ÚNICA de export (Google Sheet único con 2 hojas)
control_otros_gastos_router = APIRouter(
    prefix="/otrosGastos",
    tags=["Otros Gastos"],
)


# -------------------------------------------------
@control_otros_gastos_router.get(
    "/export",
    description=(
        "Export UNIFICADO de Otros Gastos: una sola ruta sube un único "
        "Google Sheet con las hojas otros_gastos_siif y otros_gastos_sgf "
        "en background"
    ),
)
async def export(
    params: Annotated[ControlOtrosGastosExportFilter, Depends()],
    service: ControlOtrosGastosExportServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.export(params=params)
