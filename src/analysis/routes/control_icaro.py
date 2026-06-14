__all__ = ["control_icaro_router"]

from typing import Annotated

from fastapi import APIRouter, Depends

from ...auth.services import AuthorizationDependency
from ..schemas import ControlIcaroLiteFilter
from ..services import (
    ControlIcaroServiceDependency,
)

control_icaro_router = APIRouter(prefix="/controlIcaro")


# -------------------------------------------------
@control_icaro_router.post("/export")
async def login_with_cookie(
    params: Annotated[ControlIcaroLiteFilter, Depends()],
    service: ControlIcaroServiceDependency,
    security: AuthorizationDependency,
):
    security.is_admin_or_user_or_raise()
    return await service.export(params=params)
