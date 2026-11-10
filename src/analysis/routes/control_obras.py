from typing import Annotated, List

from fastapi import Depends

from ...auth.services import AuthorizationDependency
from ...utils.router_factory import GenericRouterFactory
from ..schemas import (  # El esquema de parámetros para el filtro
    ControlObrasDocument,
    ControlObrasFullFilter,
    ControlObrasGenerateFilter,
    ControlObrasLiteFilter,
    ControlObrasReport,
)
from ..services import (
    ControlObrasService,
    ControlObrasServiceDependency,
)

factory = GenericRouterFactory(
    service_dependency=ControlObrasService,
    report_schema=ControlObrasDocument,
    full_filter_schema=ControlObrasFullFilter,  # Usa limit/offset
    lite_filter_schema=ControlObrasLiteFilter,  # No usa limit/offset
    prefix="/controlObras",
)

control_obras_router = factory.get_router()


# -------------------------------------------------
@control_obras_router.get(
    "/getIcaro",
    description="Comprobantes cargados en ICARO neto de SIIF's rdeu",
    # response_model=List[ControlHaberesReport],
    response_model_exclude_none=True,
)
async def get_icaro_carga_neto_rdeu(
    params: Annotated[ControlObrasFullFilter, Depends()],
    service: ControlObrasServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.get_icaro_carga_neto_rdeu(params=params)


# -------------------------------------------------
@control_obras_router.get(
    "/getSGF",
    description="Comprobantes SGF's Resumen Rend. Proveedores",
    # response_model=List[ControlHaberesReport],
    response_model_exclude_none=True,
)
async def get_sgf_resumen_rend(
    params: Annotated[ControlObrasFullFilter, Depends()],
    service: ControlObrasServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.get_sgf_resumend_rend(params=params)


# -------------------------------------------------
@control_obras_router.get(
    "/compute",
    description="Computar control obras",
    # response_model=List[RouteReturnSchema],
    response_model_exclude_none=True,
)
async def compute(
    params: Annotated[ControlObrasFullFilter, Depends()],
    service: ControlObrasServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.compute_control_obras(params=params)


# -------------------------------------------------
@control_obras_router.get(
    "/generate",
    description=(
        "Cruce ICARO vs SGF Resumen de Rendiciones calculado on-demand "
        "por el backend (sin persistir; el snapshot lo congela el POST)"
    ),
    response_model=List[ControlObrasReport],
    response_model_exclude_none=True,
)
async def generate(
    params: Annotated[ControlObrasGenerateFilter, Depends()],
    service: ControlObrasServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.generate(params=params)
