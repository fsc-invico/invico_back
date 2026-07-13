from typing import Annotated, List

from fastapi import APIRouter, Depends

from ...auth.services import AuthorizationDependency
from ..schemas import (
    ReportePlanillometroFilter,
    ReportePlanillometroLiteFilter,
    ReportePlanillometroReport,
)
from ..services import ReportePlanillometroServiceDependency

reporte_planillometro_router = APIRouter(prefix="/reportePlanillometro")


# -------------------------------------------------
@reporte_planillometro_router.post(
    "",
    description="Reporte Planillometro",
    response_model=List[ReportePlanillometroReport],
    response_model_exclude_none=True,
)
async def generate(
    params: Annotated[ReportePlanillometroFilter, Depends()],
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
