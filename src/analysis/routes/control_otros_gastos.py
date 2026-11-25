from typing import Annotated, List

from fastapi import APIRouter, Depends

from ...auth.services import AuthorizationDependency
from ...utils import RouteReturnSchema
from ...utils.router_factory import GenericRouterFactory
from ..schemas import (
    ControlOtrosGastosCruceFilter,
    ControlOtrosGastosCruceGenerateFilter,
    ControlOtrosGastosCruceLiteFilter,
    ControlOtrosGastosCruceSnapshot,
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
    ControlOtrosGastosCruceServiceDependency,
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
        "Google Sheet con las hojas otros_gastos_siif, otros_gastos_sgf, "
        "otros_gastos_cruce_resto y otros_gastos_cruce_fondos_perm en "
        "background"
    ),
)
async def export(
    params: Annotated[ControlOtrosGastosExportFilter, Depends()],
    service: ControlOtrosGastosExportServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.export(params=params)


# Bloque del cruce SIIF <-> SGF: 2 colecciones (pareos y mensual) en un
# solo conjunto de rutas. Patrón generate -> POST de los demás controles.
control_otros_gastos_cruce_router = APIRouter(
    prefix="/otrosGastos/cruce",
    tags=["Otros Gastos"],
)


# -------------------------------------------------
@control_otros_gastos_cruce_router.get(
    "/generate",
    description=(
        "Cruce SIIF <-> SGF on-demand en dos capas: pareo 1:1 del resto "
        "(PAREADO / SIIF_SIN_SGF / SGF_SIN_SIIF) y control mensual de "
        "fondos permanentes. Devuelve {pareos, mensual}; el snapshot lo "
        "congela el POST"
    ),
)
async def generate_cruce(
    params: Annotated[ControlOtrosGastosCruceGenerateFilter, Depends()],
    service: ControlOtrosGastosCruceServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.generate(params=params)


# -------------------------------------------------
@control_otros_gastos_cruce_router.get(
    "",
    name="Get Snapshot Cruce",
    description="Snapshot de AMBAS tablas del cruce (pareos y mensual)",
)
async def get_snapshot_cruce(
    params: Annotated[ControlOtrosGastosCruceFilter, Depends()],
    service: ControlOtrosGastosCruceServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.get_snapshot(params=params)


# -------------------------------------------------
@control_otros_gastos_cruce_router.post(
    "",
    name="Add Many Cruce",
    description=(
        "Congela el snapshot de AMBAS tablas del cruce con borrado "
        "idempotente por ejercicio"
    ),
    response_model=RouteReturnSchema,
    responses={
        400: {"description": "Error en la validación de los datos"},
    },
)
async def add_many_cruce(
    data: ControlOtrosGastosCruceSnapshot,
    service: ControlOtrosGastosCruceServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.add_many(data=data)


# -------------------------------------------------
@control_otros_gastos_cruce_router.delete(
    "",
    name="Delete Many Cruce",
    description="Borra AMBAS tablas del cruce por ejercicio",
    response_model=RouteReturnSchema,
)
async def delete_cruce(
    params: Annotated[ControlOtrosGastosCruceLiteFilter, Depends()],
    service: ControlOtrosGastosCruceServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.delete_many(params=params)
