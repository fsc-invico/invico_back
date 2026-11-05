from typing import Annotated, List

from fastapi import Depends

from ...auth.services import AuthorizationDependency
from ...utils.router_factory import GenericRouterFactory
from ..schemas import (
    ControlAporteEmpresarioDocument,
    ControlAporteEmpresarioFilter,
    ControlAporteEmpresarioLiteFilter,
    ControlAporteEmpresarioReport,
)
from ..services import (
    ControlAporteEmpresarioService,  # La clase del servicio
    ControlAporteEmpresarioServiceDependency,
)

factory = GenericRouterFactory(
    service_dependency=ControlAporteEmpresarioService,
    report_schema=ControlAporteEmpresarioDocument,
    full_filter_schema=ControlAporteEmpresarioFilter,  # Usa limit/offset
    lite_filter_schema=ControlAporteEmpresarioLiteFilter,  # No usa limit/offset
    prefix="/controlAporteEmpresario",
)

control_aporte_empresario_router = factory.get_router()


# -------------------------------------------------
@control_aporte_empresario_router.get(
    "/generateSIIF",
    description="Control Cruzado Aporte Empresario (3% INVICO)",
    response_model=List[ControlAporteEmpresarioReport],
    response_model_exclude_none=True,
)
async def generate_siif(
    params: Annotated[ControlAporteEmpresarioFilter, Depends()],
    service: ControlAporteEmpresarioServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.generate_siif(params=params)


# -------------------------------------------------
@control_aporte_empresario_router.get(
    "/generateIcaro",
    description="Control Cruzado Aporte Empresario (3% INVICO) SIIF vs ICARO",
    response_model=List[ControlAporteEmpresarioReport],
    response_model_exclude_none=True,
)
async def generate_icaro(
    params: Annotated[ControlAporteEmpresarioFilter, Depends()],
    service: ControlAporteEmpresarioServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.generate_icaro(params=params)


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
    "/retencionesSIIF",
    description="Ejecución SIIF de Retenciones del año seleccionado",
    # response_model=List[ReporteFormulacionRecursosReport],
    response_model_exclude_none=True,
)
async def get_retenciones_from_siif(
    params: Annotated[ControlAporteEmpresarioFilter, Depends()],
    service: ControlAporteEmpresarioServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.get_retenciones_from_siif(params=params)


# -------------------------------------------------
@control_aporte_empresario_router.get(
    "/retencionesIcaro",
    description="Ejecución ICARO de Retenciones del año seleccionado",
    # response_model=List[ReporteFormulacionRecursosReport],
    response_model_exclude_none=True,
)
async def get_retenciones_from_icaro(
    params: Annotated[ControlAporteEmpresarioFilter, Depends()],
    service: ControlAporteEmpresarioServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.get_retenciones_from_icaro(params=params)
