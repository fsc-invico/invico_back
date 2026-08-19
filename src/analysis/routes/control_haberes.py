from typing import Annotated

from fastapi import APIRouter, Depends

from ...auth.services import AuthorizationDependency
from ..schemas import (
    ControlHaberesFilter,
    ControlHaberesLiteFilter,
)
from ..services import ControlHaberesServiceDependency

control_haberes_router = APIRouter(prefix="/controlHaberes")


# -------------------------------------------------
@control_haberes_router.get(
    "/getHaberes",
    description="Comprobantes Haberes SIIF neto de Rdeu",
    # response_model=List[ControlHaberesReport],
    response_model_exclude_none=True,
)
async def generate_siif(
    params: Annotated[ControlHaberesFilter, Depends()],
    service: ControlHaberesServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.get_siif_comprobantes_haberes_neto_rdeu(params=params)


# -------------------------------------------------
@control_haberes_router.get(
    "/export",
    name="Reportes exportables para Formulación Presupuestaria - Google Sheets and Excel",
)
async def export(
    params: Annotated[ControlHaberesLiteFilter, Depends()],
    service: ControlHaberesServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.export(params)
