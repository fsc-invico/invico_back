from typing import Annotated, List

from fastapi import APIRouter, Depends

from ...auth.services import AuthorizationDependency
from ..schemas import (
    ReporteFormulacionFilter,
    ReporteFormulacionLiteFilter,
    ReporteFormulacionReport,
)
from ..services import ReporteFormulacionServiceDependency

reporte_formulacion_router = APIRouter(prefix="/reporteFormulacion")


# -------------------------------------------------
@reporte_formulacion_router.get(
    "/planillometro",
    description="Planillometro Ejecución Acumulada del Gasto",
    response_model=List[ReporteFormulacionReport],
    response_model_exclude_none=True,
)
async def generate_planillometro(
    params: Annotated[ReporteFormulacionFilter, Depends()],
    service: ReporteFormulacionServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.generate_planillometro(params=params)


# -------------------------------------------------
@reporte_formulacion_router.get(
    "/export",
    name="Reportes exportables para Formulación Presupuestaria - Google Sheets and Excel",
)
async def export(
    params: Annotated[ReporteFormulacionLiteFilter, Depends()],
    service: ReporteFormulacionServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.export(params)
