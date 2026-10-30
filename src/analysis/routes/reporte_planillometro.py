from typing import Annotated, List

from fastapi import APIRouter, Depends

from ...auth.services import AuthorizationDependency
from ...utils.router_factory import GenericRouterFactory
from ..schemas import (
    ReportePlanillometroDocument,
    ReportePlanillometroFullFilter,
    ReportePlanillometroGenerateFilter,
    ReportePlanillometroLiteFilter,
    ReportePlanillometroReport,
)
from ..services import (
    ReportePlanillometroService,
    ReportePlanillometroServiceDependency,
)

factory = GenericRouterFactory(
    service_dependency=ReportePlanillometroService,
    report_schema=ReportePlanillometroDocument,
    full_filter_schema=ReportePlanillometroFullFilter,  # Usa limit/offset
    lite_filter_schema=ReportePlanillometroLiteFilter,  # No usa limit/offset
    prefix="/reportePlanillometro",
    # El GET Get All omite los campos None: Mongo ya no persiste claves
    # con null y el esquema las rellena con None al leer; no hace falta
    # devolverlas al front.
    response_model_exclude_none=True,
)

reporte_planillometro_router = factory.get_router()


# -------------------------------------------------
@reporte_planillometro_router.get(
    "/generate",
    description="Reporte Planillometro",
    response_model=List[ReportePlanillometroReport],
    response_model_exclude_none=True,
)
async def generate(
    params: Annotated[ReportePlanillometroGenerateFilter, Depends()],
    service: ReportePlanillometroServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.generate(params=params)


# -------------------------------------------------
@reporte_planillometro_router.get(
    "/exportEECC",
    name="Export Planillometro Contabilidad (EECC) to Google Sheets and Excel",
)
async def export(
    params: Annotated[ReportePlanillometroLiteFilter, Depends()],
    service: ReportePlanillometroServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.export_eecc(params)


# -------------------------------------------------
@reporte_planillometro_router.get(
    "/uniqueEstructura",
    description="Get All Estructuras",
    response_model=list[str],
)
async def unique_estructura(
    service: ReportePlanillometroServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.unique_estructura()
