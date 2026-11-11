from typing import Annotated, List

from fastapi import Depends

from ...auth.services import AuthorizationDependency
from ...utils.router_factory import GenericRouterFactory
from ..schemas import (
    ControlHaberesDocument,
    ControlHaberesFullFilter,
    ControlHaberesGenerateFilter,
    ControlHaberesLiteFilter,
    ControlHaberesReport,
)
from ..services import (
    ControlHaberesService,
    ControlHaberesServiceDependency,
)

factory = GenericRouterFactory(
    service_dependency=ControlHaberesService,
    report_schema=ControlHaberesDocument,
    full_filter_schema=ControlHaberesFullFilter,  # Usa limit/offset
    lite_filter_schema=ControlHaberesLiteFilter,  # No usa limit/offset
    prefix="/controlHaberes",
)

control_haberes_router = factory.get_router()


# -------------------------------------------------
@control_haberes_router.get(
    "/compute",
    description="Control Cruzado Haberes SIIF vs Banco INVICO (SSCC)",
    # response_model=List[ControlAporteEmpresarioReport],
    response_model_exclude_none=True,
)
async def compute_control_haberes(
    params: Annotated[ControlHaberesFullFilter, Depends()],
    service: ControlHaberesServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.compute_control_haberes(params=params)


# -------------------------------------------------
@control_haberes_router.get(
    "/generate",
    description=(
        "Cruce mensual Haberes SIIF vs Banco INVICO (SSCC) calculado "
        "on-demand por el backend (sin persistir; el snapshot lo "
        "congela el POST)"
    ),
    response_model=List[ControlHaberesReport],
    response_model_exclude_none=True,
)
async def generate(
    params: Annotated[ControlHaberesGenerateFilter, Depends()],
    service: ControlHaberesServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.generate(params=params)


# -------------------------------------------------
@control_haberes_router.get(
    "/getSIIFHaberes",
    description="Comprobantes Haberes SIIF neto de Rdeu",
    # response_model=List[ControlHaberesReport],
    response_model_exclude_none=True,
)
async def generate_siif(
    params: Annotated[ControlHaberesFullFilter, Depends()],
    service: ControlHaberesServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.get_siif_comprobantes_haberes_neto_rdeu(params=params)


# -------------------------------------------------
@control_haberes_router.get(
    "/getBancoHaberes",
    description="Registros de Haberes en Banco INVICO (SSCC)",
    # response_model=List[ControlHaberesReport],
    response_model_exclude_none=True,
)
async def generate_banco(
    params: Annotated[ControlHaberesFullFilter, Depends()],
    service: ControlHaberesServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.get_banco_invico(params=params)
