__all__ = ["control_icaro_router"]

from typing import Annotated

from fastapi import APIRouter, Depends

from ...auth.services import AuthorizationDependency
from ..schemas import ControlIcaroFullFilter, ControlIcaroLiteFilter
from ..services import (
    ControlIcaroServiceDependency,
)

control_icaro_router = APIRouter(prefix="/controlIcaro")


# -------------------------------------------------
@control_icaro_router.get(
    "/computeControlAnual",
    description="Control Anual SIIF vs Icaro",
    # response_model=List[ControlAporteEmpresarioReport],
    response_model_exclude_none=True,
)
async def compute_control_anual(
    params: Annotated[ControlIcaroFullFilter, Depends()],
    service: ControlIcaroServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.compute_control_anual(params=params)


# -------------------------------------------------
@control_icaro_router.get(
    "/computeControlComprobantes",
    description="Control de Comprobantes SIIF vs Icaro",
    # response_model=List[ControlAporteEmpresarioReport],
    response_model_exclude_none=True,
)
async def compute_control_comprobantes(
    params: Annotated[ControlIcaroFullFilter, Depends()],
    service: ControlIcaroServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.compute_control_comprobantes(params=params)


# -------------------------------------------------
@control_icaro_router.get(
    "/computeControlPA6",
    description="Control de Comprobantes PA6 SIIF vs Icaro",
    # response_model=List[ControlAporteEmpresarioReport],
    response_model_exclude_none=True,
)
async def compute_control_pa6(
    params: Annotated[ControlIcaroFullFilter, Depends()],
    service: ControlIcaroServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.compute_control_pa6(params=params)


# -------------------------------------------------
@control_icaro_router.get("/export", name="Export to Google Sheets and Excel")
async def export(
    params: Annotated[ControlIcaroLiteFilter, Depends()],
    service: ControlIcaroServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.export(params=params)
