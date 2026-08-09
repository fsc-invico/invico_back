from typing import Annotated, List

from fastapi import APIRouter, Depends

from ...auth.services import AuthorizationDependency
from ..schemas import (
    ReporteFormulacionCargaReport,
    ReporteFormulacionFilter,
    ReporteFormulacionGastosReport,
    ReporteFormulacionLiteFilter,
    ReporteFormulacionPlanillometroReport,
    ReporteFormulacionRecursosReport,
)
from ..services import ReporteFormulacionServiceDependency

control_aporte_empresario_router = APIRouter(prefix="/controlAporteEmpresario")


# -------------------------------------------------
@control_aporte_empresario_router.get(
    "/recursos",
    description="Ejecución de Recursos del año seleccionado",
    response_model=List[ReporteFormulacionRecursosReport],
    response_model_exclude_none=True,
)
async def generate_recursos(
    params: Annotated[ReporteFormulacionFilter, Depends()],
    service: ReporteFormulacionServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.generate_recursos(params=params)


# # -------------------------------------------------
# @control_aporte_empresario_router.get(
#     "/gastos",
#     description="Ejecución de Gastos del año seleccionado",
#     response_model=List[ReporteFormulacionGastosReport],
#     response_model_exclude_none=True,
# )
# async def generate_gastos(
#     params: Annotated[ReporteFormulacionFilter, Depends()],
#     service: ReporteFormulacionServiceDependency,
#     security: AuthorizationDependency,
# ):
#     security.is_admin_or_user_or_raise()
#     return await service.generate_gastos(params=params)


# -------------------------------------------------
@control_aporte_empresario_router.get(
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
