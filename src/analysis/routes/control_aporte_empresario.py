from typing import Annotated, List

from fastapi import APIRouter, Depends

from ...auth.services import AuthorizationDependency
from ..schemas import (
    ControlAporteEmpresarioFilter,
    ControlAporteEmpresarioLiteFilter,
    ControlAporteEmpresarioReport,
)
from ..services import ControlAporteEmpresarioServiceDependency

control_aporte_empresario_router = APIRouter(prefix="/controlAporteEmpresario")


# -------------------------------------------------
@control_aporte_empresario_router.get(
    "",
    description="Control Cruzado Aporte Empresario (3% INVICO)",
    response_model=List[ControlAporteEmpresarioReport],
    response_model_exclude_none=True,
)
async def generate(
    params: Annotated[ControlAporteEmpresarioFilter, Depends()],
    service: ControlAporteEmpresarioServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.generate(params=params)


# -------------------------------------------------
@control_aporte_empresario_router.get(
    "/recursos",
    description="Ejecución de Recursos del año seleccionado",
    # response_model=List[ReporteFormulacionRecursosReport],
    response_model_exclude_none=True,
)
async def get_recursos(
    params: Annotated[ControlAporteEmpresarioFilter, Depends()],
    service: ControlAporteEmpresarioServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.get_recursos(params=params)


# -------------------------------------------------
@control_aporte_empresario_router.get(
    "/retenciones",
    description="Ejecución de Retenciones del año seleccionado",
    # response_model=List[ReporteFormulacionRecursosReport],
    response_model_exclude_none=True,
)
async def get_retenciones(
    params: Annotated[ControlAporteEmpresarioFilter, Depends()],
    service: ControlAporteEmpresarioServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.get_retenciones(params=params)


# -------------------------------------------------
@control_aporte_empresario_router.get(
    "/export",
    name="Reportes exportables para Formulación Presupuestaria - Google Sheets and Excel",
)
async def export(
    params: Annotated[ControlAporteEmpresarioLiteFilter, Depends()],
    service: ControlAporteEmpresarioServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.export(params)
